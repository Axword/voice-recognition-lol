"""Cienka warstwa zgodnosci wstecznej.

Cale logowanie zyje teraz w app.logging_setup. Ten modul zostaje tylko po to,
zeby stary kod (gui, main) nadal sie importowal.
"""

from __future__ import annotations

import logging
import time

from app.logging_setup import get_logger, setup


def now_str() -> str:
    return time.strftime("%H:%M:%S")


def make_logger(debug: bool = True) -> logging.Logger:
    """Deprecated: uzywaj app.logging_setup.get_logger(name)."""
    setup(debug)
    return get_logger()


__all__ = ["get_logger", "make_logger", "now_str", "setup"]
