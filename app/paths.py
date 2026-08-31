"""Per-user data locations.

Nothing is ever written next to the executable. On Windows this follows the
platform rules: roaming configuration in APPDATA, machine-local data (logs,
caches, downloaded models) in LOCALAPPDATA.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "LoLVoice"


def _windows_roaming() -> Path:
    return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")


def _windows_local() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")


def _config_root() -> Path:
    override = os.environ.get("LOLVOICE_HOME")
    if override:
        return Path(override) / "config"
    if sys.platform == "win32":
        return _windows_roaming() / APP_NAME
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / APP_NAME


def _data_root() -> Path:
    override = os.environ.get("LOLVOICE_HOME")
    if override:
        return Path(override) / "data"
    if sys.platform == "win32":
        return _windows_local() / APP_NAME
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / APP_NAME


CONFIG_DIR = _config_root()
DATA_DIR = _data_root()

CONFIG_FILE = CONFIG_DIR / "config.json"
LOG_DIR = DATA_DIR / "logs"
CACHE_DIR = DATA_DIR / "cache"
MODELS_DIR = DATA_DIR / "models"
RUNTIME_FILE = DATA_DIR / "runtime.json"


def bundled_dir() -> Path:
    """Directory holding read-only resources shipped with the application."""
    frozen = getattr(sys, "_MEIPASS", None)
    if frozen:
        return Path(frozen)
    return Path(__file__).resolve().parent.parent


def ensure_dirs() -> None:
    for directory in (CONFIG_DIR, DATA_DIR, LOG_DIR, CACHE_DIR, MODELS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def refresh() -> None:
    """Recompute locations, used by tests that move LOLVOICE_HOME around."""
    global CONFIG_DIR, DATA_DIR, CONFIG_FILE, LOG_DIR, CACHE_DIR, MODELS_DIR, RUNTIME_FILE
    CONFIG_DIR = _config_root()
    DATA_DIR = _data_root()
    CONFIG_FILE = CONFIG_DIR / "config.json"
    LOG_DIR = DATA_DIR / "logs"
    CACHE_DIR = DATA_DIR / "cache"
    MODELS_DIR = DATA_DIR / "models"
    RUNTIME_FILE = DATA_DIR / "runtime.json"
