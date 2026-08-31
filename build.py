#!/usr/bin/env python3
"""Build script for LoL Voice Controller.

Three stages, each of which can be run on its own:

    python build.py --app-only        PyInstaller onedir build into dist/LoLVoice
    python build.py --installer-only  Inno Setup installer into dist/installer
    python build.py --portable-only   portable ZIP into dist
    python build.py                   all three

The web panel is expected in webui/dist. Build it first with `npm ci` and
`npm run build` in webui/, or pass --with-webui to have this script do it.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import build_config as cfg

ISCC_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
    Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
]


def log(message: str) -> None:
    print(f"[build] {message}", flush=True)


def fail(message: str) -> None:
    print(f"[build] error: {message}", file=sys.stderr, flush=True)
    raise SystemExit(1)


def check_environment(need_installer: bool) -> None:
    if not (cfg.ROOT_DIR / cfg.MAIN_SCRIPT).exists():
        fail(f"entry point {cfg.MAIN_SCRIPT} not found")
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        fail("PyInstaller is missing, run: pip install -r requirements-dev.txt")
    if need_installer and not find_iscc():
        fail("Inno Setup compiler (ISCC.exe) not found, install Inno Setup 6")


def find_iscc() -> Path | None:
    found = shutil.which("iscc") or shutil.which("ISCC")
    if found:
        return Path(found)
    for candidate in ISCC_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def run(command: list[str], cwd: Path | None = None) -> None:
    log(" ".join(str(part) for part in command))
    result = subprocess.run(command, cwd=str(cwd) if cwd else None, check=False)
    if result.returncode != 0:
        fail(f"command failed with exit code {result.returncode}")


def build_webui() -> None:
    webui = cfg.ROOT_DIR / "webui"
    if not (webui / "package.json").exists():
        fail("webui/package.json not found")
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        fail("npm not found on PATH")
    log("building the web panel")
    run([npm, "ci"], cwd=webui)
    run([npm, "run", "build"], cwd=webui)


def clean() -> None:
    log("cleaning previous build output")
    for directory in (cfg.BUILD_DIR, cfg.DIST_DIR):
        if directory.exists():
            shutil.rmtree(directory)


def build_app(version: str) -> None:
    if not (cfg.ROOT_DIR / "webui" / "dist").exists():
        log("warning: webui/dist is missing, the panel will not be bundled")
    cfg.write_version_info(version=version)
    log(f"running PyInstaller for version {version}")
    run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            str(cfg.SPEC_FILE),
            "--noconfirm",
            "--clean",
            "--distpath",
            str(cfg.DIST_DIR),
            "--workpath",
            str(cfg.BUILD_DIR / "pyinstaller"),
        ],
        cwd=cfg.ROOT_DIR,
    )
    if not cfg.APP_DIST_DIR.exists():
        fail(f"expected output directory {cfg.APP_DIST_DIR} was not produced")
    size = sum(path.stat().st_size for path in cfg.APP_DIST_DIR.rglob("*") if path.is_file())
    log(f"application built, {size / (1024 * 1024):.1f} MB in {cfg.APP_DIST_DIR}")


def build_installer(version: str) -> None:
    if not cfg.APP_DIST_DIR.exists():
        fail("no application build found, run with --app-only first")
    iscc = find_iscc()
    if not iscc:
        fail("Inno Setup compiler (ISCC.exe) not found")
    cfg.INSTALLER_DIR.mkdir(parents=True, exist_ok=True)
    log("compiling the installer")
    run(
        [
            str(iscc),
            f"/DMyAppVersion={version}",
            f"/O{cfg.INSTALLER_DIR}",
            f"/F{cfg.INSTALLER_BASENAME}",
            str(cfg.INSTALLER_SCRIPT),
        ],
        cwd=cfg.ROOT_DIR,
    )
    if not cfg.INSTALLER_FILE.exists():
        fail(f"installer was not produced at {cfg.INSTALLER_FILE}")
    log(f"installer ready: {cfg.INSTALLER_FILE}")


def build_portable(version: str) -> None:
    if not cfg.APP_DIST_DIR.exists():
        fail("no application build found, run with --app-only first")
    target = cfg.portable_zip_path(version)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    log(f"packing the portable ZIP: {target.name}")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(cfg.APP_DIST_DIR.rglob("*")):
            if path.is_file():
                archive.write(path, Path(cfg.APP_NAME) / path.relative_to(cfg.APP_DIST_DIR))
        # Marker file: the application keeps its data next to the executable
        # when it finds this, instead of using APPDATA.
        archive.writestr(f"{cfg.APP_NAME}/portable.txt", "Portable mode. Data is kept in this folder.\n")
    log(f"portable ZIP ready: {target} ({target.stat().st_size / (1024 * 1024):.1f} MB)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build LoL Voice Controller.")
    stage = parser.add_mutually_exclusive_group()
    stage.add_argument("--app-only", action="store_true", help="only run PyInstaller")
    stage.add_argument("--installer-only", action="store_true", help="only compile the installer")
    stage.add_argument("--portable-only", action="store_true", help="only pack the portable ZIP")
    parser.add_argument("--with-webui", action="store_true", help="run npm ci and npm run build in webui/ first")
    parser.add_argument("--version", help="override the version, defaults to version.json")
    parser.add_argument("--no-clean", action="store_true", help="keep previous build output")
    args = parser.parse_args(argv)

    version = args.version or cfg.get_version()
    do_app = args.app_only or not (args.installer_only or args.portable_only)
    do_installer = args.installer_only or not (args.app_only or args.portable_only)
    do_portable = args.portable_only or not (args.app_only or args.installer_only)

    if do_installer and os.name != "nt":
        fail("the installer can only be built on Windows")

    check_environment(need_installer=do_installer)

    if args.with_webui:
        build_webui()

    if do_app:
        if not args.no_clean:
            clean()
        build_app(version)
    if do_installer:
        build_installer(version)
    if do_portable:
        build_portable(version)

    log("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
