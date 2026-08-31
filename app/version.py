"""Single source of truth for the application version."""

from __future__ import annotations

import json
from functools import lru_cache

from app import paths

FALLBACK = "0.0.0-dev"


@lru_cache(maxsize=1)
def get_version() -> str:
    for candidate in (paths.bundled_dir() / "version.json", paths.bundled_dir() / "_internal" / "version.json"):
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
            version = data.get("version")
            if version:
                return str(version)
        except (OSError, json.JSONDecodeError, AttributeError):
            continue
    return FALLBACK


def parse(version: str) -> tuple[int, ...]:
    cleaned = version.lstrip("vV").split("-")[0]
    parts: list[int] = []
    for chunk in cleaned.split("."):
        try:
            parts.append(int(chunk))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def is_newer(candidate: str, current: str) -> bool:
    return parse(candidate) > parse(current)
