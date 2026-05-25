#!/usr/bin/env python3
"""
LoL Voice Assistant - Build Script
Creates standalone EXE with all dependencies
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

# ============ CONFIGURATION ============
APP_NAME = "LoLVoiceAssistant"
MAIN_SCRIPT = "main.py"
ICON_PATH = "assets/icon.ico"  # Change if you have different icon
VERSION = "1.0.0"
COMPANY = "LoL Voice Assistant"
# =======================================


def check_requirements():
    """Check if all required tools are installed."""
    print("🔍 Checking requirements...")
    
    # Check PyInstaller
    try:
        import PyInstaller
        print(f"  ✓ PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("  ✗ PyInstaller not found!")
        print("    Run: pip install pyinstaller")
        return False
    
    # Check if main script exists
    if not os.path.exists(MAIN_SCRIPT):
        print(f"  ✗ Main script '{MAIN_SCRIPT}' not found!")
        return False
    print(f"  ✓ Main script: {MAIN_SCRIPT}")
    
    return True


def clean_build():
    """Remove previous build artifacts."""
    print("\n🧹 Cleaning previous builds...")
    
    dirs_to_remove = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"  ✓ Removed {dir_name}/")
    
    # Remove .spec files
    for f in Path('.').glob('*.spec'):
        f.unlink()
        print(f"  ✓ Removed {f}")


def create_version_file():
    """Create Windows version info file."""
    print("\n📝 Creating version info...")
    
    v = VERSION.split('.')
    while len(v) < 4:
        v.append('0')
    
    version_info = f'''# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({v[0]}, {v[1]}, {v[2]}, {v[3]}),
    prodvers=({v[0]}, {v[1]}, {v[2]}, {v[3]}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'041504B0',
        [StringStruct(u'CompanyName', u'{COMPANY}'),
        StringStruct(u'FileDescription', u'League of Legends Voice Assistant'),
        StringStruct(u'FileVersion', u'{VERSION}'),
        StringStruct(u'InternalName', u'{APP_NAME}'),
        StringStruct(u'LegalCopyright', u'Copyright (c) 2024 {COMPANY}'),
        StringStruct(u'OriginalFilename', u'{APP_NAME}.exe'),
        StringStruct(u'ProductName', u'LoL Voice Assistant'),
        StringStruct(u'ProductVersion', u'{VERSION}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [0x0415, 1200])])
  ]
)
'''
    
    with open('version_info.txt', 'w', encoding='utf-8') as f:
        f.write(version_info)
    print("  ✓ Created version_info.txt")


def create_spec_file():
    """Create PyInstaller spec file."""
    print("\n📋 Creating spec file...")
    
    # Check for icon
    icon_line = f"icon='{ICON_PATH}'," if os.path.exists(ICON_PATH) else "icon=None,"
    
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for LoL Voice Assistant

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all data files
datas = [
    ('assets', 'assets'),
    ('config', 'config'),
    ('gui/translations.py', 'gui'),
    ('resource_helper.py', '.'),
]

# Add version files if they exist
if os.path.exists('version.json'):
    datas.append(('version.json', '.'))
if os.path.exists('version.txt'):
    datas.append(('version.txt', '.'))

# Hidden imports - modules that PyInstaller might miss
hiddenimports = [
    # Standard library
    'json',
    'threading',
    'queue',
    'logging',
    'time',
    'datetime',
    'os',
    'sys',
    'typing',
    'argparse',
    
    # Tkinter
    'tkinter',
    'tkinter.ttk',
    'tkinter.messagebox',
    'tkinter.filedialog',
    
    # Third party
    'numpy',
    'sounddevice',
    'webrtcvad',
    'colorama',
    'requests',
    'psutil',
    'PIL',
    'PIL._tkinter_finder',
    'PIL.Image',
    'PIL.ImageTk',
    
    # Whisper backends
    'pywhispercpp',
    'pywhispercpp.model',
    
    # Windows specific
    'win32api',
    'win32con',
    'win32gui',
    'win32process',
    'pywintypes',
    'win32event',
    
    # Your modules - IMPORTANT!
    'controller',
    'controller.lol_whisp_controller',
    'controls',
    'controls.key_mapping',
    'controls.mapping_manager',
    'game',
    'game.ability_manager',
    'game.lol_data_manager', 
    'game.lol_game_client_api',
    'gui',
    'gui.lol_voice_gui',
    'gui.translations',
    'utils',
    'utils.logger',
    'resource_helper',
]

# Collect submodules for complex packages
hiddenimports += collect_submodules('sounddevice')
hiddenimports += collect_submodules('numpy')

a = Analysis(
    ['{MAIN_SCRIPT}'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'scipy',
        'pandas',
        'notebook',
        'jupyter',
        'IPython',
        'pytest',
        'setuptools',
        'pip',
        'wheel',
        'black',
        'flake8',
        'mypy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='{APP_NAME}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window for GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    {icon_line}
    version='version_info.txt' if os.path.exists('version_info.txt') else None,
    uac_admin=False,  # Don't require admin rights
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='{APP_NAME}',
)
'''
    
    with open(f'{APP_NAME}.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    print(f"  ✓ Created {APP_NAME}.spec")


def run_pyinstaller():
    """Run PyInstaller to build the application."""
    print("\n🔨 Building application...")
    print("  This may take a few minutes...\n")
    
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        f'{APP_NAME}.spec',
        '--clean',
        '--noconfirm',
    ]
    
    result = subprocess.run(cmd, capture_output=False)
    
    return result.returncode == 0


def post_build_cleanup():
    """Clean up after build and show results."""
    print("\n🧹 Post-build cleanup...")
    
    # Remove version info file
    if os.path.exists('version_info.txt'):
        os.remove('version_info.txt')
        print("  ✓ Removed version_info.txt")
    
    # Check if build was successful
    exe_path = Path(f'dist/{APP_NAME}/{APP_NAME}.exe')
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n{'='*60}")
        print(f"✅ BUILD SUCCESSFUL!")
        print(f"{'='*60}")
        print(f"📁 Output: dist/{APP_NAME}/")
        print(f"📦 EXE size: {size_mb:.1f} MB")
        print(f"\n💡 To run: dist/{APP_NAME}/{APP_NAME}.exe")
        print(f"\n📋 Next step: Create installer with Inno Setup")
        return True
    else:
        print(f"\n{'='*60}")
        print(f"❌ BUILD FAILED!")
        print(f"{'='*60}")
        print("Check the output above for errors.")
        return False


def main():
    """Main build process."""
    print(f"""
{'='*60}
🎮 LoL Voice Assistant - Build System
{'='*60}
""")
    
    if not check_requirements():
        sys.exit(1)
    
    clean_build()
    create_version_file()
    create_spec_file()
    
    if run_pyinstaller():
        post_build_cleanup()
    else:
        print("\n❌ PyInstaller failed!")
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Build cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Build error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)