"""Start with Windows, through the per user Run key. No op on other systems."""

from __future__ import annotations

import sys

from app.logging_setup import get_logger

log = get_logger("autostart")

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "LoLVoice"


def supported() -> bool:
    return sys.platform == "win32"


def _command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    from app import paths

    entry = paths.bundled_dir() / "main.py"
    return f'"{sys.executable}" "{entry}"'


def is_enabled() -> bool:
    if not supported():
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return bool(value)
    except OSError:
        return False


def set_enabled(enabled: bool) -> bool:
    """Returns the state actually in effect after the call."""
    if not supported():
        log.debug("Autostart is available on Windows only")
        return False
    import winreg

    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, _command())
                log.info("Autostart enabled")
            else:
                try:
                    winreg.DeleteValue(key, VALUE_NAME)
                    log.info("Autostart disabled")
                except FileNotFoundError:
                    pass
        return enabled
    except OSError as exc:
        log.warning("Could not change the autostart entry: %s", exc)
        return is_enabled()


def apply(settings: object | None = None) -> bool:
    """Sync the registry with settings.start_with_windows."""
    if settings is None:
        from app import config

        settings = config.load()
    wanted = bool(getattr(settings, "start_with_windows", False))
    if not supported():
        return False
    if is_enabled() == wanted:
        return wanted
    return set_enabled(wanted)
