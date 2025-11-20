"""
Build configuration for LoL Voice Controller
"""

import os
from pathlib import Path

# Version info
VERSION = "1.0.0"
COMPANY = "LoL Voice Controller"
PRODUCT = "LoL Voice Controller"
COPYRIGHT = "Copyright (C) 2024"
DESCRIPTION = "Voice control for League of Legends"

# Paths
ROOT_DIR = Path(__file__).parent
BUILD_DIR = ROOT_DIR / "build"
DIST_DIR = ROOT_DIR / "dist"
INSTALLER_DIR = DIST_DIR / "installer"
APP_DIR = DIST_DIR / "app"

# Files to include
INCLUDE_FILES = [
    ("config.json", "config.json"),
    ("README.md", "README.md"),
]

# Hidden imports for PyInstaller
HIDDEN_IMPORTS = [
    "tkinter",
    "sounddevice",
    "numpy",
    "webrtcvad",
    "requests",
    "colorama",
    "pywhispercpp",
    "faster_whisper",
    "whisper",
]

# Exclude modules to reduce size
EXCLUDES = [
    "matplotlib",
    "pytest",
    "notebook",
    "jupyterlab",
]