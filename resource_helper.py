"""
Resource path helper for PyInstaller compatibility
Handles paths for both development and bundled EXE
"""

import os
import sys
import shutil
import json


def get_base_path() -> str:
    """Get base path - works for both dev and PyInstaller bundle."""
    if getattr(sys, 'frozen', False):
        # Running as compiled EXE
        return sys._MEIPASS
    else:
        # Running as script
        return os.path.dirname(os.path.abspath(__file__))


def resource_path(relative_path: str) -> str:
    """
    Get absolute path to resource.
    Works for dev and PyInstaller.
    
    Usage:
        icon_path = resource_path("assets/icon.png")
        translation_path = resource_path("gui/translations/pl_PL.json")
    """
    base = get_base_path()
    return os.path.join(base, relative_path)


def get_user_data_dir() -> str:
    """
    Get user data directory for writable files (config, logs).
    Returns path in AppData on Windows.
    """
    if sys.platform == 'win32':
        app_data = os.getenv('APPDATA', os.path.expanduser('~'))
        user_dir = os.path.join(app_data, 'LoLVoiceAssistant')
    else:
        user_dir = os.path.join(os.path.expanduser('~'), '.lol_voice_assistant')
    
    os.makedirs(user_dir, exist_ok=True)
    return user_dir


def get_config_path() -> str:
    """
    Get path to config file.
    - In dev: config/config.json (local)
    - In EXE: AppData/LoLVoiceAssistant/config.json (writable)
    """
    if getattr(sys, 'frozen', False):
        # EXE mode - use user directory (writable)
        return os.path.join(get_user_data_dir(), 'config.json')
    else:
        # Dev mode - use local config
        return 'config/config.json'


def get_logs_dir() -> str:
    """Get logs directory path."""
    if getattr(sys, 'frozen', False):
        logs_dir = os.path.join(get_user_data_dir(), 'logs')
    else:
        logs_dir = 'logs'
    
    os.makedirs(logs_dir, exist_ok=True)
    return logs_dir


def ensure_default_config():
    """
    Ensure config file exists with default values.
    Copies bundled default config if user config doesn't exist.
    """
    config_path = get_config_path()
    
    if not os.path.exists(config_path):
        # Create directory if needed
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        # Default config
        default_config = {
            "language": "pl_PL",
            "ui_language": "en_US",
            "recognition_mode": "letters",
            "spell_sensitivity": "medium",
            "flash_key": "D",
            "recognition_accuracy_threshold": 0.75,
            "min_score_threshold": 15.0
        }
        
        # Try to copy from bundled config first
        bundled_config = resource_path('config/config.json')
        if os.path.exists(bundled_config):
            try:
                shutil.copy2(bundled_config, config_path)
                return config_path
            except Exception:
                pass
        
        # Write default config
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
    
    return config_path


def is_frozen() -> bool:
    """Check if running as PyInstaller bundle."""
    return getattr(sys, 'frozen', False)