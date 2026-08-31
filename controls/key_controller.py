"""Wciskanie klawiszy i klikanie myszka.

pynput jest importowany dopiero przy pierwszym uzyciu, zeby ten modul dal sie
zaimportowac w CI, gdzie nie ma serwera X ani uprawnien do wejsc.
"""

from __future__ import annotations

from typing import Any

from app.logging_setup import get_logger

log = get_logger("keys")


class KeyController:
    def __init__(self, lazy: bool = True) -> None:
        self.mouse: Any | None = None
        self.keyboard: Any | None = None
        self._mouse_module: Any | None = None
        self._available: bool | None = None
        if not lazy:
            self._ensure()

    def _ensure(self) -> bool:
        """Tworzy kontrolery pynput przy pierwszym uzyciu."""
        if self._available is not None:
            return self._available
        try:
            from pynput import keyboard, mouse

            self.mouse = mouse.Controller()
            self.keyboard = keyboard.Controller()
            self._mouse_module = mouse
            self._available = True
        except Exception as exc:  # brak pynput to normalny stan w CI
            log.warning("Input control unavailable: %s", exc)
            self._available = False
        return self._available

    @property
    def available(self) -> bool:
        return self._ensure()

    def press_key(self, key: str) -> bool:
        """Wciska klawisz albo klika prawym. Zwraca False, gdy wejscia sa niedostepne."""
        if not self._ensure():
            log.debug("Skipping key press '%s', input control unavailable", key)
            return False
        if key == "right_click":
            self.mouse.click(self._mouse_module.Button.right, 1)
            return True
        self.keyboard.press(key)
        self.keyboard.release(key)
        return True
