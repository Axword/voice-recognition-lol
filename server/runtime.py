"""Session identity for the local server: token, port, runtime file, panel URL.

The panel and the tray both need to know where the API listens and which token
unlocks it. That pair lives in ``app.paths.RUNTIME_FILE`` for the lifetime of the
process, so a second launch can find the first one and open its panel.
"""

from __future__ import annotations

import json
import os
import secrets
import socket
import time
from dataclasses import asdict, dataclass

from app import paths
from app.logging_setup import get_logger

log = get_logger("runtime")

HOST = "127.0.0.1"
PREFERRED_PORT = 21337
PORT_ATTEMPTS = 40


@dataclass
class RuntimeInfo:
    port: int
    token: str
    pid: int
    started_at: float

    def to_dict(self) -> dict:
        return asdict(self)


_current: RuntimeInfo | None = None


def generate_token() -> str:
    """A fresh session token. Never persisted beyond the runtime file."""
    return secrets.token_urlsafe(32)


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((HOST, port))
        except OSError:
            return False
    return True


def find_free_port(preferred: int = PREFERRED_PORT) -> int:
    """Try the preferred port, then walk upwards, then let the OS choose."""
    if preferred and _port_is_free(preferred):
        return preferred
    start = preferred or PREFERRED_PORT
    for offset in range(1, PORT_ATTEMPTS):
        candidate = start + offset
        if candidate > 65535:
            break
        if _port_is_free(candidate):
            return candidate
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((HOST, 0))
        return int(probe.getsockname()[1])


def write_runtime(port: int, token: str, pid: int | None = None) -> RuntimeInfo:
    """Persist the session descriptor and remember it in process."""
    global _current
    info = RuntimeInfo(
        port=int(port),
        token=token,
        pid=int(pid if pid is not None else os.getpid()),
        started_at=time.time(),
    )
    paths.ensure_dirs()
    tmp = paths.RUNTIME_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(info.to_dict(), indent=2), encoding="utf-8")
    tmp.replace(paths.RUNTIME_FILE)
    _current = info
    log.info("Runtime descriptor written for port %s", info.port)
    return info


def read_runtime() -> RuntimeInfo | None:
    """The descriptor written by whichever instance is running, if any."""
    try:
        raw = json.loads(paths.RUNTIME_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        return RuntimeInfo(
            port=int(raw["port"]),
            token=str(raw["token"]),
            pid=int(raw.get("pid", 0)),
            started_at=float(raw.get("started_at", 0.0)),
        )
    except (KeyError, TypeError, ValueError):
        return None


def clear_runtime() -> None:
    global _current
    _current = None
    try:
        paths.RUNTIME_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def current() -> RuntimeInfo | None:
    """The descriptor for this process, set once the server session starts."""
    return _current


def start_session(port: int | None = None, token: str | None = None) -> RuntimeInfo:
    """Pick a port, mint a token and publish both."""
    chosen_port = port if port else find_free_port()
    return write_runtime(chosen_port, token or generate_token())


def panel_url(info: RuntimeInfo | None = None, with_token: bool = True) -> str:
    """URL the browser should open. Includes the token so nothing is copied by hand."""
    target = info or current() or read_runtime()
    if target is None:
        return f"http://{HOST}:{PREFERRED_PORT}/"
    if with_token:
        return f"http://{HOST}:{target.port}/?token={target.token}"
    return f"http://{HOST}:{target.port}/"
