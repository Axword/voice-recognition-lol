"""Shared build settings for PyInstaller, Inno Setup and the release workflow.

Single source of truth for names, paths and the bundle contents. The version
itself lives in version.json, this module only reads it, so a release only has
to rewrite that one file.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent

# Identity. These names are also used by installer.iss and by the winget
# manifest, so changing one of them means changing the release assets too.
APP_NAME = "LoLVoice"
PRODUCT_NAME = "LoL Voice Controller"
EXE_NAME = f"{APP_NAME}.exe"
PUBLISHER = "Axword"
COPYRIGHT = "Copyright (C) 2026 Axword"
DESCRIPTION = "Voice control for League of Legends"
HOMEPAGE = "https://github.com/Axword/voice-recognition-lol"
# Stable installer identity. Must match AppId in installer.iss.
APP_ID = "{9F1D2C4E-6B78-4A31-9E5C-0D3A7F8B2E14}"

MAIN_SCRIPT = "main.py"
ICON_PATH = "assets/icon.ico"
MANIFEST_PATH = "assets/app.manifest"

# Paths
BUILD_DIR = ROOT_DIR / "build"
DIST_DIR = ROOT_DIR / "dist"
APP_DIST_DIR = DIST_DIR / APP_NAME
INSTALLER_DIR = DIST_DIR / "installer"
VERSION_INFO_FILE = BUILD_DIR / "version_info.txt"
INSTALLER_SCRIPT = ROOT_DIR / "installer.iss"
SPEC_FILE = ROOT_DIR / "LoLVoiceAssistant.spec"

# Stable file names. Keeping them identical between releases helps SmartScreen
# build reputation while the binaries are unsigned.
INSTALLER_BASENAME = "LoLVoiceSetup"
INSTALLER_FILE = INSTALLER_DIR / f"{INSTALLER_BASENAME}.exe"

FALLBACK_VERSION = "0.0.0"


def get_version() -> str:
    """Read the version from version.json."""
    try:
        data = json.loads((ROOT_DIR / "version.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return FALLBACK_VERSION
    return str(data.get("version") or FALLBACK_VERSION)


def set_version(version: str) -> None:
    """Write the version back to version.json, keeping the other fields."""
    from datetime import date

    path = ROOT_DIR / "version.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    data["version"] = version
    data["build"] = int(data.get("build") or 0) + 1
    data["date"] = date.today().isoformat()
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def version_tuple(version: str | None = None) -> tuple[int, int, int, int]:
    parts = (version or get_version()).lstrip("vV").split("-")[0].split(".")
    numbers: list[int] = []
    for part in parts[:4]:
        try:
            numbers.append(int(part))
        except ValueError:
            numbers.append(0)
    while len(numbers) < 4:
        numbers.append(0)
    return tuple(numbers[:4])  # type: ignore[return-value]


def portable_zip_path(version: str | None = None) -> Path:
    return DIST_DIR / f"{APP_NAME}-{version or get_version()}-portable.zip"


def bundle_data() -> list[tuple[str, str]]:
    """(source, destination) pairs, only for sources that exist."""
    candidates = [
        ("webui/dist", "webui/dist"),
        ("data/engines.json", "data"),
        ("assets", "assets"),
        ("models", "models"),
        ("version.json", "."),
    ]
    return [(src, dest) for src, dest in candidates if (ROOT_DIR / src).exists()]


HIDDEN_IMPORTS = [
    # Local API
    "fastapi",
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.wsproto_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "pydantic",
    "pydantic.deprecated.decorator",
    # Tray
    "pystray",
    "pystray._win32",
    "PIL",
    "PIL.Image",
    # Voice engine and input
    "numpy",
    "sounddevice",
    "webrtcvad",
    "pywhispercpp",
    "pywhispercpp.model",
    "faster_whisper",
    "ctranslate2",
    "truststore",
    "websockets",
    "pynput",
    "pynput.keyboard._win32",
    "requests",
    "psutil",
    "colorama",
    # Windows integration
    "win32api",
    "win32con",
    "win32event",
    "win32gui",
    "winerror",
    "pywintypes",
    # Application packages
    "app",
    "app.config",
    "app.engines",
    "app.logging_setup",
    "app.paths",
    "app.version",
    "controller",
    "controls",
    "game",
    "server",
]

EXCLUDES = [
    "tkinter",
    "matplotlib",
    "scipy",
    "pandas",
    "notebook",
    "jupyter",
    "IPython",
    "pytest",
    "setuptools",
    "pip",
    "wheel",
    "black",
    "flake8",
    "mypy",
    "ruff",
    "torch",
    "torchvision",
]


def write_version_info(path: Path | None = None, version: str | None = None) -> Path:
    """Write the Windows VERSIONINFO resource consumed by PyInstaller."""
    version = version or get_version()
    numbers = version_tuple(version)
    target = path or VERSION_INFO_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={numbers},
    prodvers={numbers},
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
        u'040904B0',
        [StringStruct(u'CompanyName', u'{PUBLISHER}'),
        StringStruct(u'FileDescription', u'{DESCRIPTION}'),
        StringStruct(u'FileVersion', u'{version}'),
        StringStruct(u'InternalName', u'{APP_NAME}'),
        StringStruct(u'LegalCopyright', u'{COPYRIGHT}'),
        StringStruct(u'OriginalFilename', u'{EXE_NAME}'),
        StringStruct(u'ProductName', u'{PRODUCT_NAME}'),
        StringStruct(u'ProductVersion', u'{version}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [0x0409, 1200])])
  ]
)
""",
        encoding="utf-8",
    )
    return target
