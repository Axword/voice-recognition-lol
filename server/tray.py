"""System tray icon.

pystray and Pillow are imported lazily, so this module loads on a headless
box where neither is installed. In that case ``run_tray`` logs the reason and
returns without blocking, and the application keeps running without an icon.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app import config
from app.logging_setup import get_logger

log = get_logger("tray")

ICON_SIZE = 64

STRINGS: dict[str, dict[str, str]] = {
    "pl_PL": {
        "title": "LoL Voice Controller",
        "open_panel": "Otworz panel",
        "start": "Start nasluchu",
        "stop": "Stop nasluchu",
        "open_logs": "Otworz folder logow",
        "check_updates": "Sprawdz aktualizacje",
        "quit": "Zamknij",
    },
    "en_US": {
        "title": "LoL Voice Controller",
        "open_panel": "Open panel",
        "start": "Start listening",
        "stop": "Stop listening",
        "open_logs": "Open log folder",
        "check_updates": "Check for updates",
        "quit": "Quit",
    },
}


def strings(language: str | None = None) -> dict[str, str]:
    if not language:
        try:
            language = config.load().ui_language
        except Exception:
            language = "pl_PL"
    return STRINGS.get(language, STRINGS["pl_PL"])


@dataclass
class TrayActions:
    open_panel: Callable[[], None]
    start_listening: Callable[[], None]
    stop_listening: Callable[[], None]
    open_logs: Callable[[], None]
    check_updates: Callable[[], None]
    quit: Callable[[], None]


def open_log_folder() -> None:
    """Reveal the log directory in the platform file manager."""
    import subprocess
    import sys

    from app import paths

    paths.ensure_dirs()
    target = str(paths.LOG_DIR)
    try:
        if sys.platform == "win32":
            import os

            os.startfile(target)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target])
        else:
            subprocess.Popen(["xdg-open", target])
    except Exception as exc:
        log.warning("Could not open the log folder: %s", exc)


def _build_image() -> Any:
    from PIL import Image, ImageDraw

    from app import paths

    icon_file = paths.bundled_dir() / "assets" / "icon.ico"
    if icon_file.is_file():
        try:
            return Image.open(icon_file)
        except Exception as exc:
            log.debug("Could not load the icon file: %s", exc)

    image = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (17, 18, 20, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse((14, 8, 50, 40), fill=(62, 207, 142, 255))
    draw.rectangle((29, 40, 35, 52), fill=(62, 207, 142, 255))
    draw.rectangle((20, 52, 44, 57), fill=(62, 207, 142, 255))
    return image


def build_menu(actions: TrayActions, language: str | None = None) -> Any:
    import pystray

    text = strings(language)
    return pystray.Menu(
        pystray.MenuItem(text["open_panel"], lambda: actions.open_panel(), default=True),
        pystray.MenuItem(text["start"], lambda: actions.start_listening()),
        pystray.MenuItem(text["stop"], lambda: actions.stop_listening()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(text["open_logs"], lambda: actions.open_logs()),
        pystray.MenuItem(text["check_updates"], lambda: actions.check_updates()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(text["quit"], lambda: actions.quit()),
    )


def create_icon(actions: TrayActions, language: str | None = None) -> Any | None:
    """The pystray icon, or None when the dependency or the display is missing."""
    try:
        import pystray
        from PIL import Image  # noqa: F401
    except Exception as exc:
        log.info("Tray icon unavailable, running without it: %s", exc)
        return None
    try:
        import pystray

        text = strings(language)
        return pystray.Icon("lolvoice", _build_image(), text["title"], build_menu(actions, language))
    except Exception as exc:
        log.info("Tray icon could not be created: %s", exc)
        return None


def run_tray(actions: TrayActions, language: str | None = None, blocking: bool = True) -> Any | None:
    """Run the tray loop. Degrades to a logged no op when pystray is missing."""
    icon = create_icon(actions, language)
    if icon is None:
        return None
    if blocking:
        try:
            icon.run()
        except Exception as exc:
            log.info("Tray loop stopped: %s", exc)
        return icon
    thread = threading.Thread(target=icon.run, name="tray", daemon=True)
    thread.start()
    return icon


def stop_tray(icon: Any | None) -> None:
    if icon is None:
        return
    try:
        icon.stop()
    except Exception as exc:
        log.debug("Tray stop failed: %s", exc)
