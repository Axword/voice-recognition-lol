"""Rotating file logging, crash dumps and an in-memory tail for the web panel."""

from __future__ import annotations

import collections
import logging
import logging.handlers
import platform
import sys
import time
import traceback
import zipfile
from io import BytesIO
from typing import Optional

from app import paths

LOGGER_NAME = "lolvoice"
_MAX_BYTES = 2 * 1024 * 1024
_BACKUPS = 5
_configured = False

_tail: collections.deque[dict] = collections.deque(maxlen=500)


class _TailHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        _tail.append(
            {
                "time": time.strftime("%H:%M:%S", time.localtime(record.created)),
                "level": record.levelname,
                "name": record.name,
                "message": record.getMessage(),
            }
        )


def get_logger(name: Optional[str] = None) -> logging.Logger:
    return logging.getLogger(LOGGER_NAME if not name else f"{LOGGER_NAME}.{name}")


def setup(debug: bool = False) -> logging.Logger:
    global _configured
    logger = logging.getLogger(LOGGER_NAME)
    if _configured:
        return logger

    paths.ensure_dirs()
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S")

    file_handler = logging.handlers.RotatingFileHandler(
        paths.LOG_DIR / "lolvoice.log", maxBytes=_MAX_BYTES, backupCount=_BACKUPS, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    if sys.stderr is not None:
        stream = logging.StreamHandler()
        stream.setFormatter(fmt)
        logger.addHandler(stream)

    logger.addHandler(_TailHandler())
    _configured = True
    return logger


def tail(limit: int = 200) -> list[dict]:
    items = list(_tail)
    return items[-limit:]


def install_crash_handler() -> None:
    previous = sys.excepthook

    def hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            previous(exc_type, exc_value, exc_tb)
            return
        paths.ensure_dirs()
        stamp = time.strftime("%Y%m%d-%H%M%S")
        target = paths.LOG_DIR / f"crash-{stamp}.log"
        try:
            with target.open("w", encoding="utf-8") as handle:
                handle.write(system_info())
                handle.write("\n")
                traceback.print_exception(exc_type, exc_value, exc_tb, file=handle)
        except OSError:
            pass
        get_logger().critical("Unhandled exception, crash dump written to %s", target)
        previous(exc_type, exc_value, exc_tb)

    sys.excepthook = hook


def system_info() -> str:
    from app import version

    lines = [
        f"app_version: {version.get_version()}",
        f"platform: {platform.platform()}",
        f"python: {sys.version.split()[0]}",
        f"frozen: {bool(getattr(sys, 'frozen', False))}",
        f"config_dir: {paths.CONFIG_DIR}",
        f"data_dir: {paths.DATA_DIR}",
    ]
    try:
        from app import engines

        lines.append(f"engine: {engines.active_engine_id()}")
    except Exception:  # noqa: BLE001 - diagnostics must never fail
        pass
    return "\n".join(lines)


def build_log_archive() -> bytes:
    """Zip every log file plus a system summary, for the panel download button."""
    paths.ensure_dirs()
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("system-info.txt", system_info())
        for entry in sorted(paths.LOG_DIR.glob("*.log*")):
            try:
                archive.write(entry, f"logs/{entry.name}")
            except OSError:
                continue
    return buffer.getvalue()
