# LoL Voice  Controller v0.2

Voice control system for League of Legends with automatic champion detection.

## Features

- 🎯 Automatic champion detection
- 🌍 Multi-language support (PL, EN, DE, ES, FR, IT, PT, RU, KO, ZH, JA, TR)
- 🔄 Auto-updates for champion and item data
- 🎮 Voice commands for abilities, summoner spells, and items
- ⚡ Combo system (say "Q and W" or "Q i W")
- 🛒 Item buying by voice ("znajdź pierścień dorana")
- 🖱️ Right-click attack command

## Installation

1. Install Python 3.8+
2. Install requirements: `pip install -r requirements.txt`
3. Run GUI: `python lol_voice_gui.py`
4. Or run console: `python lol_voice_controller_v2.py`

## Building Executable

### Method 1: Easy PyInstaller (Recommended)
Run `build_easy.bat` - automatically installs PyInstaller and builds both executables.

### Method 2: Manual PyInstaller
Run `build_simple.bat` - requires PyInstaller to be already installed.

### Method 3: cx_Freeze with Fallback
Run `build_installer.bat` - tries cx_Freeze first, then PyInstaller if it fails.

### Manual Build
```bash
# Install PyInstaller
python -m pip install pyinstaller

# Build GUI
python -m PyInstaller --onefile --windowed --name=LoL_Voice_Controller --add-data="lol_data_manager.py;." --add-data="lol_voice_controller_v2.py;." --add-data="lol_game_client_api.py;." --add-data="requirements.txt;." lol_voice_gui.py

# Build Console
python -m PyInstaller --onefile --console --name=LoL_Voice_Console --add-data="lol_data_manager.py;." --add-data="lol_game_client_api.py;." --add-data="requirements.txt;." lol_voice_controller_v2.py
```

## Usage

1. Start League of Legends
2. Launch voice controller
3. Select language and configure keybinds
4. Start voice control
5. Say ability names naturally

## Voice Commands

- **Abilities**: Say champion ability names
- **Summoner Spells**: "flash", "heal", "ignite"
- **Items**: "znajdź [item name]"
- **Combo**: "Q and W" or "Q i W"
- **Attack**: "attack" (right-click)
- **Shop**: "shop" or "sklep"

## Configuration

- Language selection
- Flash keybind (F/D)
- Summoner 2 keybind (D/F)
- Auto-update toggle
