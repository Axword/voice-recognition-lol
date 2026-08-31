"""Update check against GitHub Releases and silent installer handover.

The release must carry an asset named ``latest.json`` shaped like
``{"version": "1.2.3", "url": "...Setup.exe", "sha256": "...", "notes": "..."}``.
Results are cached for a day so the panel can ask on every open without
hammering the API.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from app import config, paths, version
from app.logging_setup import get_logger

log = get_logger("updater")

REPO = os.environ.get("LOLVOICE_REPO", "Axword/voice-recognition-lol")
RELEASES_API = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET_NAME = "latest.json"
CACHE_TTL_SECONDS = 24 * 60 * 60
INSTALLER_FLAGS = ("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART")
REQUEST_TIMEOUT = 20

_lock = threading.Lock()


def _cache_file() -> Path:
    return paths.DATA_DIR / "update-cache.json"


def _read_cache() -> dict | None:
    try:
        data = json.loads(_cache_file().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if time.time() - float(data.get("checked_at", 0)) > CACHE_TTL_SECONDS:
        return None
    payload = data.get("result")
    return payload if isinstance(payload, dict) else None


def _write_cache(result: dict) -> None:
    try:
        paths.ensure_dirs()
        _cache_file().write_text(
            json.dumps({"checked_at": time.time(), "result": result}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        log.debug("Could not cache update result: %s", exc)


def cached_result() -> dict | None:
    """The last check result if it is still fresh. Never touches the network."""
    return _read_cache()


def _empty(current: str, reason: str | None = None) -> dict:
    result: dict[str, Any] = {
        "current": current,
        "latest": None,
        "available": False,
        "url": None,
        "notes": None,
    }
    if reason:
        result["reason"] = reason
    return result


def _fetch_manifest() -> dict | None:
    import requests

    headers = {"Accept": "application/vnd.github+json", "User-Agent": "LoLVoice"}
    response = requests.get(RELEASES_API, headers=headers, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    release = response.json()
    for asset in release.get("assets", []):
        if asset.get("name") == ASSET_NAME:
            manifest = requests.get(
                asset["browser_download_url"], headers={"User-Agent": "LoLVoice"}, timeout=REQUEST_TIMEOUT
            )
            manifest.raise_for_status()
            data = manifest.json()
            return data if isinstance(data, dict) else None
    log.info("Release %s carries no %s asset", release.get("tag_name"), ASSET_NAME)
    return None


def check(force: bool = False) -> dict:
    """Current version against the published one. Never raises."""
    current = version.get_version()
    settings = config.load()
    if not settings.check_updates and not force:
        return _empty(current, "disabled")

    with _lock:
        if not force:
            cached = _read_cache()
            if cached is not None:
                cached["current"] = current
                return cached

        try:
            manifest = _fetch_manifest()
        except Exception as exc:
            log.info("Update check failed: %s", exc)
            return _empty(current, "unreachable")

        if not manifest or not manifest.get("version"):
            result = _empty(current, "no_manifest")
            _write_cache(result)
            return result

        latest = str(manifest["version"])
        available = version.is_newer(latest, current)
        if settings.skipped_version and settings.skipped_version == latest:
            available = False
        result = {
            "current": current,
            "latest": latest,
            "available": available,
            "url": manifest.get("url"),
            "notes": manifest.get("notes"),
            "sha256": manifest.get("sha256"),
        }
        _write_cache(result)
        if available:
            log.info("Update available: %s", latest)
        return result


def _download_installer(url: str, sha256: str | None) -> Path:
    import requests

    suffix = ".exe" if url.lower().endswith(".exe") else Path(url).suffix or ".exe"
    handle, temp_path = tempfile.mkstemp(prefix="lolvoice-update-", suffix=suffix)
    os.close(handle)
    target = Path(temp_path)
    digest = hashlib.sha256()
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with target.open("wb") as out:
            for chunk in response.iter_content(chunk_size=256 * 1024):
                if not chunk:
                    continue
                out.write(chunk)
                digest.update(chunk)
    if sha256 and digest.hexdigest().lower() != str(sha256).lower():
        target.unlink(missing_ok=True)
        raise ValueError("Checksum mismatch for the downloaded installer")
    return target


def install(on_exit: Any | None = None) -> dict:
    """Download, verify and hand over to the silent installer."""
    if sys.platform != "win32":
        return {"started": False, "reason": "unsupported_platform"}

    result = check(force=True)
    if not result.get("available") or not result.get("url"):
        return {"started": False, "reason": "no_update"}

    try:
        installer = _download_installer(str(result["url"]), result.get("sha256"))
    except Exception as exc:
        log.error("Update download failed: %s", exc)
        return {"started": False, "reason": "download_failed"}

    try:
        subprocess.Popen([str(installer), *INSTALLER_FLAGS], close_fds=True)
    except OSError as exc:
        log.error("Could not launch the installer: %s", exc)
        return {"started": False, "reason": "launch_failed"}

    log.info("Installer launched, the application will close")
    if callable(on_exit):
        threading.Timer(1.0, on_exit).start()
    return {"started": True}


def skip(target_version: str) -> None:
    """Remember that the user does not want this version."""
    config.update({"skipped_version": target_version})
