"""Local REST API and panel host.

Listens on the loopback interface only. Every call under /api/v1 needs the
session token, either in the ``X-Auth-Token`` header or as ``?token=``.
The token is injected into the HTML served at "/", so the panel authenticates
itself with no copying by hand.
"""

from __future__ import annotations

import asyncio
import secrets
import threading
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from app import config, engines, logging_setup, paths, version
from app.logging_setup import get_logger
from server import runtime, ws

log = get_logger("api")

API_PREFIX = "/api/v1"
TOKEN_HEADER = "X-Auth-Token"
LOOPBACK_HOSTS = {"127.0.0.1", "::1", "::ffff:127.0.0.1", "localhost", "testclient"}

_service: Any = None
_service_error: str | None = None
_service_lock = threading.Lock()


def get_service() -> Any:
    """Lazily import the voice service. Returns None when it is not available."""
    global _service, _service_error
    with _service_lock:
        if _service is not None:
            return _service
        try:
            from controller.service import get_service as _factory

            _service = _factory()
            _service_error = None
            ws.attach_service(_service)
        except Exception as exc:
            _service_error = f"{type(exc).__name__}: {exc}"
            log.warning("Voice service unavailable: %s", _service_error)
            _service = None
        return _service


def service_error() -> str | None:
    return _service_error


def dist_dir() -> Path:
    return paths.bundled_dir() / "webui" / "dist"


def _cached_update_available() -> bool:
    try:
        from server import updater

        cached = updater.cached_result()
        return bool(cached and cached.get("available"))
    except Exception:
        return False


def status_payload() -> dict:
    """The GET /status body, also used for periodic WebSocket frames."""
    payload: dict[str, Any] = {
        "listening": False,
        "game_active": False,
        "champion": None,
        "mode": config.load().recognition_mode,
        "engine_id": config.load().engine_id,
        "engine_name": None,
        "version": version.get_version(),
        "mappings_count": 0,
        "last_command": None,
        "last_heard": None,
        "update_available": _cached_update_available(),
    }
    service = get_service()
    if service is None:
        payload["error"] = _service_error or "voice service unavailable"
        return payload
    try:
        payload.update(service.status() or {})
    except Exception as exc:
        payload["error"] = f"{type(exc).__name__}: {exc}"
    payload.setdefault("version", version.get_version())
    payload["update_available"] = bool(payload.get("update_available")) or _cached_update_available()
    return payload


def trusted_hosts() -> set[str]:
    """Loopback plus anything named in LOLVOICE_TRUSTED_HOSTS.

    The extra entries exist for one case: running the panel in a container, where
    the browser reaches the app through the Docker gateway and therefore never
    looks like 127.0.0.1. Outside that setup leave the variable unset. The token
    is still required either way.
    """
    import os

    raw = os.environ.get("LOLVOICE_TRUSTED_HOSTS", "")
    extra = {item.strip() for item in raw.split(",") if item.strip()}
    return LOOPBACK_HOSTS | extra


def _is_loopback(request_client: Any | None) -> bool:
    if request_client is None:
        # Starlette leaves the client empty for in process test transports.
        return True
    host = getattr(request_client, "host", None) or ""
    allowed = trusted_hosts()
    if host in allowed:
        return True

    # Entries may also be CIDR ranges, which is how the Docker gateway is named
    # without pinning the exact address the daemon happens to hand out.
    import ipaddress

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    for entry in allowed:
        if "/" not in entry:
            continue
        try:
            if address in ipaddress.ip_network(entry, strict=False):
                return True
        except ValueError:
            continue
    return False


def _token_of(request: Request) -> str:
    header = request.headers.get(TOKEN_HEADER)
    if header:
        return header
    return request.query_params.get("token", "")


def _resolve_session(port: int | None, token: str | None) -> tuple[int, str]:
    """Session port and token, from the caller, the environment or the runtime file."""
    import os

    info = runtime.current() or runtime.read_runtime()
    env_token = os.environ.get("LOLVOICE_TOKEN")
    env_port = os.environ.get("LOLVOICE_PORT")
    session_token = token or env_token or (info.token if info else None) or runtime.generate_token()
    if port:
        session_port = int(port)
    elif env_port and env_port.isdigit():
        session_port = int(env_port)
    elif info:
        session_port = info.port
    else:
        session_port = runtime.PREFERRED_PORT
    return session_port, session_token


def create_app(port: int | None = None, token: str | None = None, on_quit: Callable[[], None] | None = None) -> FastAPI:
    session_port, session_token = _resolve_session(port, token)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):  # type: ignore[no-untyped-def]
        ws.get_hub().bind_loop(asyncio.get_running_loop())
        ws.get_hub().set_status_provider(status_payload)
        yield
        await ws.get_hub().shutdown()

    application = FastAPI(
        title="LoL Voice Controller",
        version=version.get_version(),
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    application.state.token = session_token
    application.state.port = session_port
    application.state.on_quit = on_quit

    origins = [f"http://127.0.0.1:{session_port}", f"http://localhost:{session_port}"]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
        allow_headers=[TOKEN_HEADER, "Content-Type"],
    )

    @application.middleware("http")
    async def guard(request: Request, call_next):  # type: ignore[no-untyped-def]
        if not _is_loopback(request.client):
            log.warning("Rejected a request from %s", getattr(request.client, "host", "unknown"))
            return JSONResponse({"detail": "Forbidden"}, status_code=403)
        path = request.url.path
        if path.startswith(API_PREFIX) and request.method != "OPTIONS":
            expected = application.state.token or ""
            given = _token_of(request)
            if not expected or not secrets.compare_digest(given, expected):
                return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return await call_next(request)

    widened = trusted_hosts() - LOOPBACK_HOSTS
    if widened:
        log.warning("Accepting requests from beyond loopback: %s", ", ".join(sorted(widened)))

    _register_routes(application)
    _register_panel(application)

    return application


def _register_routes(application: FastAPI) -> None:
    hub = ws.get_hub()

    @application.get(f"{API_PREFIX}/status")
    def read_status() -> dict:
        return status_payload()

    @application.post(f"{API_PREFIX}/listening/start")
    def listening_start() -> dict:
        service = get_service()
        if service is None:
            return {"listening": False, "error": service_error() or "voice service unavailable"}
        try:
            service.start()
        except Exception as exc:
            log.error("Start failed: %s", exc)
            return {"listening": False, "error": f"{type(exc).__name__}: {exc}"}
        return {"listening": bool(status_payload().get("listening"))}

    @application.post(f"{API_PREFIX}/listening/stop")
    def listening_stop() -> dict:
        service = get_service()
        if service is None:
            return {"listening": False, "error": service_error() or "voice service unavailable"}
        try:
            service.stop()
        except Exception as exc:
            log.error("Stop failed: %s", exc)
            return {"listening": False, "error": f"{type(exc).__name__}: {exc}"}
        return {"listening": bool(status_payload().get("listening"))}

    @application.get(f"{API_PREFIX}/settings")
    def read_settings() -> dict:
        return config.load().model_dump()

    @application.put(f"{API_PREFIX}/settings")
    def write_settings(patch: dict = Body(default_factory=dict)) -> dict:
        before = config.load()
        try:
            updated = config.update(patch or {})
        except ValidationError as exc:
            # Zly typ albo wartosc spoza listy to blad wejscia, nie awaria serwera.
            raise HTTPException(status_code=422, detail=exc.errors(include_url=False)) from exc
        if updated.start_with_windows != before.start_with_windows:
            try:
                from server import autostart

                autostart.set_enabled(updated.start_with_windows)
            except Exception as exc:
                log.warning("Autostart update failed: %s", exc)
        service = get_service()
        if service is not None:
            try:
                service.apply_settings(updated)
            except Exception as exc:
                log.warning("Applying settings to the service failed: %s", exc)
        return updated.model_dump()

    @application.get(f"{API_PREFIX}/engines")
    def read_engines() -> dict:
        return {"engines": engines.list_engines()}

    @application.post(API_PREFIX + "/engines/{engine_id}/download")
    def engine_download(engine_id: str) -> dict:
        def progress(eid: str, done: int, total: int) -> None:
            percent = int(done * 100 / total) if total else 0
            hub.broadcast(
                {"type": "download", "engine_id": eid, "downloaded": done, "total": total, "percent": percent}
            )

        def worker() -> None:
            try:
                engines.download(engine_id, progress)
                hub.broadcast({"type": "download", "engine_id": engine_id, "percent": 100, "done": True})
            except InterruptedError:
                hub.broadcast({"type": "download", "engine_id": engine_id, "cancelled": True})
            except Exception as exc:
                log.error("Download of %s failed: %s", engine_id, exc)
                hub.broadcast({"type": "download", "engine_id": engine_id, "error": str(exc)})

        threading.Thread(target=worker, name=f"download-{engine_id}", daemon=True).start()
        return {"started": True}

    @application.post(API_PREFIX + "/engines/{engine_id}/cancel")
    def engine_cancel(engine_id: str) -> dict:
        engines.cancel_download(engine_id)
        return {"cancelled": True}

    @application.post(API_PREFIX + "/engines/{engine_id}/activate")
    def engine_activate(engine_id: str) -> dict:
        updated = config.update({"engine_id": engine_id})
        service = get_service()
        if service is not None:
            try:
                service.reload_engine()
            except Exception as exc:
                log.warning("Engine reload failed: %s", exc)
        return {"engine_id": updated.engine_id}

    @application.get(f"{API_PREFIX}/audio/devices")
    def audio_devices() -> dict:
        service = get_service()
        if service is None:
            return {"devices": [], "error": service_error() or "voice service unavailable"}
        try:
            return {"devices": list(service.list_audio_devices() or [])}
        except Exception as exc:
            log.warning("Device listing failed: %s", exc)
            return {"devices": [], "error": f"{type(exc).__name__}: {exc}"}

    @application.post(f"{API_PREFIX}/audio/test")
    def audio_test(payload: dict = Body(default_factory=dict)) -> dict:
        service = get_service()
        seconds = float(payload.get("seconds", 3) or 3)
        if service is None:
            return {"level": 0.0, "transcript": "", "error": service_error() or "voice service unavailable"}
        try:
            result = service.test_microphone(seconds) or {}
        except Exception as exc:
            log.warning("Microphone test failed: %s", exc)
            return {"level": 0.0, "transcript": "", "error": f"{type(exc).__name__}: {exc}"}
        return {"level": float(result.get("level", 0.0)), "transcript": str(result.get("transcript", ""))}

    @application.get(f"{API_PREFIX}/champions/current/mappings")
    def current_mappings() -> dict:
        service = get_service()
        if service is None:
            return {
                "champion": None,
                "mode": config.load().recognition_mode,
                "mappings": [],
                "error": service_error() or "voice service unavailable",
            }
        status = status_payload()
        try:
            mappings = list(service.mappings() or [])
        except Exception as exc:
            log.warning("Mapping listing failed: %s", exc)
            mappings = []
        return {
            "champion": status.get("champion"),
            "mode": status.get("mode", config.load().recognition_mode),
            "mappings": mappings,
        }

    @application.get(f"{API_PREFIX}/logs")
    def read_logs(limit: int = 200) -> dict:
        files = []
        try:
            for entry in sorted(paths.LOG_DIR.glob("*.log*")):
                stat = entry.stat()
                files.append({"name": entry.name, "size": stat.st_size, "modified": stat.st_mtime})
        except OSError as exc:
            log.warning("Could not list log files: %s", exc)
        return {"files": files, "tail": logging_setup.tail(limit)}

    @application.get(f"{API_PREFIX}/logs/download")
    def download_logs() -> Response:
        archive = logging_setup.build_log_archive()
        stamp = time.strftime("%Y%m%d-%H%M%S")
        return Response(
            content=archive,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="lolvoice-logs-{stamp}.zip"'},
        )

    @application.get(f"{API_PREFIX}/update/check")
    def update_check(force: bool = False) -> dict:
        from server import updater

        result = updater.check(force=force)
        hub.broadcast({"type": "update", **result})
        return {
            "current": result.get("current"),
            "latest": result.get("latest"),
            "available": bool(result.get("available")),
            "url": result.get("url"),
            "notes": result.get("notes"),
        }

    @application.post(f"{API_PREFIX}/update/install")
    def update_install() -> dict:
        from server import updater

        return updater.install(on_exit=application.state.on_quit)

    @application.post(f"{API_PREFIX}/app/quit")
    def app_quit() -> dict:
        callback = application.state.on_quit
        if callable(callback):
            threading.Timer(0.3, callback).start()
        else:
            import os
            import signal

            threading.Timer(0.3, lambda: os.kill(os.getpid(), signal.SIGINT)).start()
        return {"ok": True}

    @application.websocket("/ws/status")
    async def status_socket(websocket: WebSocket) -> None:
        expected = application.state.token or ""
        given = websocket.query_params.get("token", "") or websocket.headers.get(TOKEN_HEADER, "")
        if expected and not secrets.compare_digest(given, expected):
            await websocket.close(code=4401)
            return
        await ws.status_endpoint(websocket)


PLACEHOLDER = """<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<title>LoL Voice Controller</title>
<style>
:root {{
  --bg:#111214; --surface:#17181b; --border:#2a2c30;
  --text:#e8e6e3; --text-muted:#9a9894; --accent:#3ecf8e; --radius:8px;
}}
body {{
  margin:0; background:var(--bg); color:var(--text);
  font-family:system-ui, sans-serif; display:flex; min-height:100vh;
  align-items:center; justify-content:center;
}}
main {{
  background:var(--surface); border:1px solid var(--border);
  border-radius:var(--radius); padding:32px; max-width:520px;
}}
h1 {{ font-size:20px; margin:0 0 12px; }}
p {{ color:var(--text-muted); line-height:1.5; margin:8px 0; }}
code {{ color:var(--accent); font-family:ui-monospace, monospace; }}
</style>
</head>
<body>
<main>
<h1>Panel nie jest zbudowany</h1>
<p>Tryb deweloperski. Serwer dziala, brakuje tylko plikow panelu w katalogu <code>webui/dist</code>.</p>
<p>Zbuduj panel poleceniem <code>npm run build</code> w katalogu <code>webui</code>, potem odswiez te strone.</p>
<p>API odpowiada pod <code>/api/v1/status</code>. Wersja: <code>{version}</code>.</p>
</main>
<script>window.__LOLVOICE__ = {session};</script>
</body>
</html>
"""


def _session_script(application: FastAPI) -> str:
    import json

    return json.dumps(
        {
            "token": application.state.token,
            "port": application.state.port,
            "version": version.get_version(),
            "apiBase": API_PREFIX,
        }
    )


def _inject_token(html: str, session_json: str) -> str:
    script = f'<script>window.__LOLVOICE__ = {session_json};</script>'
    if "</head>" in html:
        return html.replace("</head>", f"{script}</head>", 1)
    if "<body>" in html:
        return html.replace("<body>", f"<body>{script}", 1)
    return script + html


def _register_panel(application: FastAPI) -> None:
    dist = dist_dir()

    @application.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        session_json = _session_script(application)
        index_file = dist_dir() / "index.html"
        if index_file.is_file():
            try:
                html = index_file.read_text(encoding="utf-8")
            except OSError as exc:
                log.error("Could not read the panel index: %s", exc)
                return HTMLResponse(PLACEHOLDER.format(version=version.get_version(), session=session_json))
            return HTMLResponse(_inject_token(html, session_json))
        return HTMLResponse(PLACEHOLDER.format(version=version.get_version(), session=session_json))

    if dist.is_dir():
        application.mount("/", StaticFiles(directory=str(dist), html=False), name="panel")
        log.info("Serving the panel from %s", dist)
    else:
        log.info("Panel build not found, serving the development placeholder")


_default_app: FastAPI | None = None


def default_app() -> FastAPI:
    """App instance for ``uvicorn server.api:app``, built on first access only."""
    global _default_app
    if _default_app is None:
        _default_app = create_app()
    return _default_app


def __getattr__(name: str) -> Any:
    if name == "app":
        return default_app()
    raise AttributeError(name)
