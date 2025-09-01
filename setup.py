#!/usr/bin/env python3
"""
Setup script for LoL Voice Controller
Generates executable and includes language support
"""

import sys
import os
from cx_Freeze import setup, Executable

# Dependencies
build_exe_options = {
    "packages": [
        "tkinter", "speech_recognition", "pynput", "requests", 
        "json", "threading", "time", "difflib", "pyperclip",
        "googletrans", "datetime", "os", "typing"
    ],
    "excludes": [],
    "include_files": [
        "lol_data_manager.py",
        "lol_voice_controller_v2.py", 
        "lol_voice_gui.py",
        "lol_game_client_api.py",
        "requirements.txt"
    ],
    "build_exe": "build_exe",
    "optimize": 2,
    "zip_include_packages": "*",
    "zip_exclude_packages": ""
}

# Base for Windows
base = None
if sys.platform == "win32":
    base = "Win32GUI"

# Executables
executables = [
    Executable(
        "lol_voice_gui.py", 
        base=base,
        target_name="LoL_Voice_Controller.exe",
        icon="icon.ico" if os.path.exists("icon.ico") else None
    ),
    Executable(
        "lol_voice_controller_v2.py",
        base=None,
        target_name="LoL_Voice_Console.exe"
    )
]

setup(
    name="LoL Voice Controller",
    version="2.0",
    description="Voice control system for League of Legends",
    options={"build_exe": build_exe_options},
    executables=executables
)
