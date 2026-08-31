"""LoL Voice Controller entry point.

Default run: local server, tray icon, panel opened in the browser. Listening
does not start by itself unless start_listening_on_launch is set in settings,
the Start button in the panel is the normal path.
"""

from __future__ import annotations

import argparse
import signal
import sys
import threading
import time
import webbrowser
from typing import Any

from app import logging_setup

log = logging_setup.get_logger("main")

_shutdown = threading.Event()
_tray_icon: Any | None = None
_server: Any | None = None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="lolvoice", description="LoL Voice Controller")
    parser.add_argument("--no-browser", action="store_true", help="do not open the panel at startup")
    parser.add_argument("--port", type=int, default=None, help="port for the local server")
    parser.add_argument("--cli", action="store_true", help="headless mode, no server and no tray")
    parser.add_argument("--debug", action="store_true", help="verbose logging")
    return parser.parse_args(argv)


def request_shutdown(reason: str = "request") -> None:
    if _shutdown.is_set():
        return
    log.info("Shutting down (%s)", reason)
    _shutdown.set()
    if _server is not None:
        _server.should_exit = True
    try:
        from server import tray

        tray.stop_tray(_tray_icon)
    except Exception as exc:
        log.debug("Tray stop skipped: %s", exc)


def _install_signal_handlers() -> None:
    def handler(_signum: int, _frame: Any) -> None:
        request_shutdown("signal")

    for name in ("SIGINT", "SIGTERM"):
        sig = getattr(signal, name, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, handler)
        except (ValueError, OSError):
            pass


def _voice_service() -> Any:
    from server import api

    return api.get_service()


def run_cli(args: argparse.Namespace) -> int:
    """Minimal headless mode: run the service and print status."""
    from app import config

    service = _voice_service()
    if service is None:
        from server import api

        print(f"Voice service unavailable: {api.service_error()}")
        return 1

    settings = config.load()
    print(f"Engine: {settings.engine_id}, mode: {settings.recognition_mode}")
    try:
        service.start()
    except Exception as exc:
        print(f"Could not start listening: {exc}")
        return 1

    print("Listening. Press Ctrl+C to stop.")
    try:
        while not _shutdown.is_set():
            status = service.status() or {}
            print(
                "listening={listening} game={game} champion={champion} heard={heard}".format(
                    listening=status.get("listening"),
                    game=status.get("game_active"),
                    champion=status.get("champion"),
                    heard=status.get("last_heard"),
                )
            )
            _shutdown.wait(5)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            service.stop()
        except Exception as exc:
            log.debug("Stop during shutdown failed: %s", exc)
    return 0


def _start_listening_if_configured() -> None:
    from app import config

    if not config.load().start_listening_on_launch:
        log.info("Listening stays off, waiting for the panel")
        return
    service = _voice_service()
    if service is None:
        log.warning("Cannot start listening, the voice service is unavailable")
        return
    try:
        service.start()
        log.info("Listening started on launch")
    except Exception as exc:
        log.error("Autostart of listening failed: %s", exc)


def run_app(args: argparse.Namespace) -> int:
    global _server, _tray_icon

    import uvicorn

    from server import api, autostart, runtime, single_instance, tray

    guard = single_instance.SingleInstance()
    if not guard.acquire():
        single_instance.focus_running_instance(open_browser=not args.no_browser)
        log.info("Another instance is already running")
        return 0

    info = runtime.start_session(port=args.port)
    try:
        autostart.apply()
    except Exception as exc:
        log.debug("Autostart sync skipped: %s", exc)

    application = api.create_app(port=info.port, token=info.token, on_quit=lambda: request_shutdown("panel"))
    server_config = uvicorn.Config(
        application,
        host=runtime.HOST,
        port=info.port,
        log_level="debug" if args.debug else "warning",
        access_log=args.debug,
    )
    _server = uvicorn.Server(server_config)

    server_thread = threading.Thread(target=_server.run, name="http", daemon=True)
    server_thread.start()

    deadline = time.time() + 10
    while not getattr(_server, "started", False) and time.time() < deadline:
        if not server_thread.is_alive():
            log.error("The local server did not start")
            guard.release()
            return 1
        time.sleep(0.05)

    url = runtime.panel_url(info)
    log.info("Panel available at http://%s:%s", runtime.HOST, info.port)
    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception as exc:
            log.warning("Could not open the browser: %s", exc)

    threading.Thread(target=_start_listening_if_configured, name="autolisten", daemon=True).start()

    actions = tray.TrayActions(
        open_panel=lambda: webbrowser.open(runtime.panel_url(info)),
        start_listening=lambda: _tray_start(),
        stop_listening=lambda: _tray_stop(),
        open_logs=tray.open_log_folder,
        check_updates=lambda: _tray_check_updates(),
        quit=lambda: request_shutdown("tray"),
    )

    _tray_icon = tray.run_tray(actions, blocking=False)
    if _tray_icon is None:
        log.info("Running without a tray icon")

    try:
        while not _shutdown.is_set() and server_thread.is_alive():
            _shutdown.wait(0.5)
    except KeyboardInterrupt:
        request_shutdown("keyboard")

    request_shutdown("exit")
    server_thread.join(timeout=10)

    service = api.get_service()
    if service is not None:
        try:
            service.stop()
        except Exception as exc:
            log.debug("Service stop failed: %s", exc)

    runtime.clear_runtime()
    guard.release()
    log.info("Stopped")
    return 0


def _tray_start() -> None:
    service = _voice_service()
    if service is None:
        log.warning("Cannot start listening, the voice service is unavailable")
        return
    try:
        service.start()
    except Exception as exc:
        log.error("Start from the tray failed: %s", exc)


def _tray_stop() -> None:
    service = _voice_service()
    if service is None:
        return
    try:
        service.stop()
    except Exception as exc:
        log.error("Stop from the tray failed: %s", exc)


def _tray_check_updates() -> None:
    from server import updater, ws

    result = updater.check(force=True)
    ws.get_hub().broadcast({"type": "update", **result})
    log.info("Update check finished, available=%s", result.get("available"))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging_setup.setup(debug=args.debug)
    logging_setup.install_crash_handler()
    _install_signal_handlers()

    log.info("Starting LoL Voice Controller")
    if args.cli:
        return run_cli(args)
    return run_app(args)


if __name__ == "__main__":
    sys.exit(main())
