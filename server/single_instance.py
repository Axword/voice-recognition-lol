"""One running copy at a time.

Windows uses a named mutex through ctypes, so pywin32 is not required.
Everywhere else a lock file holds the pid and liveness is checked against it,
which also covers a Windows build where the mutex call is unavailable.
"""

from __future__ import annotations

import os
import sys
import webbrowser
from pathlib import Path

from app import paths
from app.logging_setup import get_logger

log = get_logger("single_instance")

MUTEX_NAME = "Global\\LoLVoiceSingleInstance"
ERROR_ALREADY_EXISTS = 183


def _lock_file() -> Path:
    return paths.DATA_DIR / "instance.lock"


def pid_alive(pid: int) -> bool:
    """Best effort liveness check for a recorded pid."""
    if pid <= 0 or pid == os.getpid():
        return pid == os.getpid()
    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            handle = kernel32.OpenProcess(0x1000, False, int(pid))
            if not handle:
                return False
            # OpenProcess succeeds for an exited process as long as any open
            # handle keeps the process object alive, so ask for the exit code.
            STILL_ACTIVE = 259
            exit_code = ctypes.c_ulong(0)
            queried = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            kernel32.CloseHandle(handle)
            return bool(queried) and exit_code.value == STILL_ACTIVE
        except Exception:
            pass
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


class SingleInstance:
    """Acquire once at startup, release on shutdown."""

    def __init__(self, mutex_name: str = MUTEX_NAME) -> None:
        self.mutex_name = mutex_name
        self._handle: int | None = None
        self._lock_path: Path | None = None
        self.acquired = False

    def _acquire_mutex(self) -> bool | None:
        if sys.platform != "win32":
            return None
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            handle = kernel32.CreateMutexW(None, False, self.mutex_name)
            last_error = ctypes.get_last_error() if hasattr(ctypes, "get_last_error") else kernel32.GetLastError()
            if not handle:
                return None
            if last_error == ERROR_ALREADY_EXISTS:
                kernel32.CloseHandle(handle)
                return False
            self._handle = handle
            return True
        except Exception as exc:
            log.debug("Named mutex unavailable: %s", exc)
            return None

    def _acquire_lock_file(self) -> bool:
        paths.ensure_dirs()
        path = _lock_file()
        try:
            recorded = int(path.read_text(encoding="utf-8").strip() or 0)
        except (OSError, ValueError):
            recorded = 0
        if recorded and recorded != os.getpid() and pid_alive(recorded):
            return False
        try:
            path.write_text(str(os.getpid()), encoding="utf-8")
        except OSError as exc:
            log.warning("Could not write the lock file: %s", exc)
            return True
        self._lock_path = path
        return True

    def acquire(self) -> bool:
        result = self._acquire_mutex()
        if result is False:
            self.acquired = False
            return False
        self.acquired = self._acquire_lock_file()
        return self.acquired

    def release(self) -> None:
        if self._handle:
            try:
                import ctypes

                ctypes.windll.kernel32.CloseHandle(self._handle)  # type: ignore[attr-defined]
            except Exception:
                pass
            self._handle = None
        if self._lock_path is not None:
            try:
                if self._lock_path.read_text(encoding="utf-8").strip() == str(os.getpid()):
                    self._lock_path.unlink(missing_ok=True)
            except OSError:
                pass
            self._lock_path = None
        self.acquired = False

    def __enter__(self) -> SingleInstance:
        self.acquire()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.release()


def focus_running_instance(open_browser: bool = True) -> bool:
    """Open the panel of the instance already running. True when a URL was found."""
    from server import runtime

    info = runtime.read_runtime()
    if info is None:
        log.warning("Another instance holds the lock but left no runtime descriptor")
        return False
    url = runtime.panel_url(info)
    log.info("Another instance is running, opening its panel")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception as exc:
            log.warning("Could not open the browser: %s", exc)
            return False
    return True
