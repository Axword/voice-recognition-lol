# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for LoL Voice Controller.

onedir build. Everything the application needs at runtime is bundled, and
nothing is ever written back into the install directory: configuration, logs,
caches and downloaded models live under APPDATA and LOCALAPPDATA (app.paths).

Build with `python build.py --app-only`, or directly with
`pyinstaller LoLVoiceAssistant.spec --noconfirm --clean`.
"""

import os
import sys

# PyInstaller defines SPECPATH when it executes this file. Put it on sys.path so
# build_config is importable no matter which directory pyinstaller runs from.
_spec_root = globals().get("SPECPATH") or os.getcwd()
if _spec_root not in sys.path:
    sys.path.insert(0, _spec_root)

import build_config as cfg  # noqa: E402

ROOT = cfg.ROOT_DIR
IS_WINDOWS = sys.platform == "win32"

# Windows resources. Written here so a bare `pyinstaller` call works too.
version_info = cfg.write_version_info() if IS_WINDOWS else None

datas = [(str(ROOT / src), dest) for src, dest in cfg.bundle_data()]

icon = str(ROOT / cfg.ICON_PATH) if (ROOT / cfg.ICON_PATH).exists() else None
manifest = str(ROOT / cfg.MANIFEST_PATH) if (ROOT / cfg.MANIFEST_PATH).exists() else None

a = Analysis(
    [cfg.MAIN_SCRIPT],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=cfg.HIDDEN_IMPORTS,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=cfg.EXCLUDES,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=cfg.APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
    version=str(version_info) if version_info else None,
    manifest=manifest,
    uac_admin=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=cfg.APP_NAME,
)
