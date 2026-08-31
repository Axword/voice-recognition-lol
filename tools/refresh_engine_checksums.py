#!/usr/bin/env python3
"""Uzupelnia pole sha256 w data/engines.json.

UWAGA: skrypt wymaga dostepu do sieci (huggingface.co) i pobiera pelne modele,
lacznie okolo 700 MB. Nie uruchamia sie w CI, to narzedzie do reczego odswiezenia
rejestru po podmianie adresow modeli.

Uzycie:
    python3 tools/refresh_engine_checksums.py            # tylko brakujace sumy
    python3 tools/refresh_engine_checksums.py --all      # przelicz wszystkie
    python3 tools/refresh_engine_checksums.py --id whisper-tiny
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY = REPO_ROOT / "data" / "engines.json"
CHUNK = 1024 * 1024


def sha256_of_url(url: str) -> tuple[str, int]:
    """Strumieniowo liczy sume kontrolna i rozmiar, bez zapisu na dysk."""
    import requests

    digest = hashlib.sha256()
    size = 0
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        for chunk in response.iter_content(chunk_size=CHUNK):
            if not chunk:
                continue
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh sha256 hashes in data/engines.json")
    parser.add_argument("--all", action="store_true", help="recompute even when sha256 is already set")
    parser.add_argument("--id", dest="engine_id", help="only this engine id")
    parser.add_argument("--registry", default=str(REGISTRY), help="path to engines.json")
    args = parser.parse_args(argv)

    registry_path = Path(args.registry)
    data = json.loads(registry_path.read_text(encoding="utf-8"))

    changed = 0
    for engine in data.get("engines", []):
        if args.engine_id and engine.get("id") != args.engine_id:
            continue
        url = engine.get("url")
        if not url:
            print(f"skip {engine['id']}: no download url")
            continue
        if engine.get("sha256") and not args.all:
            print(f"skip {engine['id']}: sha256 already set")
            continue

        print(f"downloading {engine['id']} from {url}")
        try:
            digest, size = sha256_of_url(url)
        except Exception as exc:  # narzedzie ma raportowac, nie wywracac sie
            print(f"error {engine['id']}: {exc}", file=sys.stderr)
            continue

        engine["sha256"] = digest
        if size and engine.get("size_bytes") != size:
            print(f"  size_bytes {engine.get('size_bytes')} -> {size}")
            engine["size_bytes"] = size
        print(f"  sha256 {digest}")
        changed += 1

    if changed:
        registry_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"updated {changed} engine(s) in {registry_path}")
    else:
        print("nothing to update")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
