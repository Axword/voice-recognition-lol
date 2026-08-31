#!/usr/bin/env python3
"""Generator fixture'ow audio dla komend glosowych we wszystkich jezykach panelu.

Dla kazdego jezyka nagrywa (edge-tts) wypowiedziane: litery Q W E R, slowo na
Flash i slowo na drugi czar (ghost/teleport itp.). Wyjscie:

    tests/fixtures/audio/commands/{locale}/{slug}.mp3
    tests/fixtures/audio/commands/manifest.json

Manifest: [{locale, file, phrase, expected}], gdzie expected to klawisz przy
domyslnych ustawieniach (flash=d, summoner2=f).

Uzycie:
    python tests/tools/generate_command_fixtures.py            # brakujace
    python tests/tools/generate_command_fixtures.py --force    # wszystko od nowa
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tests" / "tools"))

from generate_audio_fixtures import EdgeEngine, normalize_audio, require_ffmpeg  # noqa: E402

from controls import command_languages as cl  # noqa: E402

OUT_DIR = REPO_ROOT / "tests" / "fixtures" / "audio" / "commands"

VOICES = {
    "pl_PL": "pl-PL-MarekNeural",
    "en_US": "en-US-GuyNeural",
    "de_DE": "de-DE-ConradNeural",
    "fr_FR": "fr-FR-HenriNeural",
    "es_ES": "es-ES-AlvaroNeural",
    "it_IT": "it-IT-DiegoNeural",
    "pt_BR": "pt-BR-AntonioNeural",
    "ru_RU": "ru-RU-DmitryNeural",
    "tr_TR": "tr-TR-AhmetNeural",
    "ko_KR": "ko-KR-InJoonNeural",
    "ja_JP": "ja-JP-KeitaNeural",
    "zh_CN": "zh-CN-YunxiNeural",
    "zh_TW": "zh-TW-YunJheNeural",
    "th_TH": "th-TH-NiwatNeural",
    "vi_VN": "vi-VN-NamMinhNeural",
    "id_ID": "id-ID-ArdiNeural",
    "ar_AE": "ar-AE-HamdanNeural",
    "cs_CZ": "cs-CZ-AntoninNeural",
    "el_GR": "el-GR-NestorasNeural",
    "hu_HU": "hu-HU-TamasNeural",
    "ro_RO": "ro-RO-EmilNeural",
}

# Domyslne klawisze z app.config: flash=d, summoner2=f.
FLASH_KEY = "d"
SUMM2_KEY = "f"


def pick_words(prefix: str) -> list[tuple[str, str]]:
    """(fraza, oczekiwany klawisz) dla jezyka: QWER + flash + drugi czar.

    Litery nagrywamy tak, jak gracz je wymawia w danym jezyku (kju, er, 큐),
    bo goly znak "q" jest dla TTS i Whispera niejednoznaczny.
    """
    letters = cl.LETTERS_BY_LANG.get(prefix, {})
    jobs = []
    for key in ("q", "w", "e", "r"):
        variants = [w for w, k in letters.items() if k == key and len(w) > 1]
        spoken = max(variants, key=len) if variants else None
        jobs.append((spoken or key, key))

    # Najdluzsze slowo: im dluzsza fraza, tym pewniej slyszy ja Whisper.
    extras = cl.EXTRAS_BY_LANG.get(prefix, {})
    flash_words = [w for w, slot in extras.items() if slot == cl.FLASH]
    summ_words = [w for w, slot in extras.items() if slot == cl.SUMM2]
    flash_word = max(flash_words, key=len) if flash_words else "flash"
    summ_word = max(summ_words, key=len) if summ_words else None
    jobs.append((flash_word, FLASH_KEY))
    if summ_word:
        jobs.append((summ_word, SUMM2_KEY))
    return jobs


def pad_audio(ffmpeg: str, source: Path, target: Path) -> None:
    """Cisza przed i po slowie: Whisper gubi klipy krotsze niz ~0.5 s."""
    import subprocess

    target.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source),
        "-af", "adelay=300|300,apad=pad_dur=0.4",
        "-ac", "1", "-ar", "16000", "-c:a", "libmp3lame", "-b:a", "32k",
        str(target),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0 or not target.is_file() or target.stat().st_size == 0:
        raise RuntimeError(f"ffmpeg pad nie przetworzyl {source.name}: {result.stderr.strip()[:200]}")


def slug(phrase: str) -> str:
    safe = "".join(ch if ch.isascii() and (ch.isalnum() or ch == "-") else "" for ch in phrase.replace(" ", "-"))
    digest = hashlib.sha1(phrase.encode("utf-8")).hexdigest()[:8]
    return f"{safe or 'phrase'}-{digest}"


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="nadpisz istniejace pliki")
    parser.add_argument("--locales", default="", help="lista locale po przecinku, domyslnie wszystkie")
    args = parser.parse_args()

    ffmpeg = require_ffmpeg()
    engine = EdgeEngine()
    locales = [loc.strip() for loc in args.locales.split(",") if loc.strip()] or list(VOICES)

    manifest: list[dict] = []
    generated = failed = skipped = 0
    semaphore = asyncio.Semaphore(6)

    async def one(locale: str, phrase: str, expected: str) -> None:
        nonlocal generated, failed, skipped
        target = OUT_DIR / locale / f"{slug(phrase)}.mp3"
        manifest.append(
            {"locale": locale, "file": f"{locale}/{target.name}", "phrase": phrase, "expected": expected}
        )
        if target.is_file() and target.stat().st_size > 0 and not args.force:
            skipped += 1
            return
        async with semaphore:
            with tempfile.TemporaryDirectory() as tmp:
                raw = Path(tmp) / "raw.mp3"
                try:
                    await engine.synthesize(phrase, VOICES[locale], raw)
                    trimmed = Path(tmp) / "trimmed.mp3"
                    normalize_audio(ffmpeg, raw, trimmed)
                    pad_audio(ffmpeg, trimmed, target)
                    generated += 1
                except Exception as exc:
                    failed += 1
                    print(f"  blad: {locale}/{phrase!r}: {type(exc).__name__}: {exc}", file=sys.stderr)

    tasks = []
    for locale in locales:
        prefix = cl.language_prefix(locale)
        for phrase, expected in pick_words(prefix):
            tasks.append(one(locale, phrase, expected))
    await asyncio.gather(*tasks)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest.sort(key=lambda e: (e["locale"], e["file"]))
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    total_kb = sum(f.stat().st_size for f in OUT_DIR.rglob("*.mp3")) / 1024
    print(f"Wygenerowane {generated}, pominiete {skipped}, nieudane {failed}, razem {total_kb:.0f} KB")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
