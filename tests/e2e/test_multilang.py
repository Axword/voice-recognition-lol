# -*- coding: utf-8 -*-
"""Rozpoznawanie komend we wszystkich jezykach panelu na prawdziwych MP3.

Fixture'y robi tests/tools/generate_command_fixtures.py (edge-tts): litery
Q W E R plus slowo na Flash i drugi czar w kazdym jezyku. Kazdy plik przechodzi
przez prawdziwego Whispera i przez MappingManager tego jezyka.

Progi sa celowo niskie: jedyny przetestowany z zywym graczem jezyk to polski,
a model tiny slabiej radzi sobie z pojedynczymi slowami w jezykach o malej
ilosci danych treningowych (tajski, wietnamski, arabski). Test pilnuje, zeby
kazdy jezyk dzialal chociaz czesciowo i zeby nie bylo regresji do zera.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import audio_support as support
from app.config import Settings
from controls.mapping_manager import MappingManager

pytestmark = pytest.mark.audio

COMMANDS_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "audio" / "commands"
MANIFEST = COMMANDS_DIR / "manifest.json"

# Minimalna liczba trafien na 6 fraz. Kalibrowane na whisper-tiny.
REQUIRED_HITS = {
    "pl_PL": 3, "en_US": 3, "de_DE": 3, "fr_FR": 2, "es_ES": 3,
    "it_IT": 3, "pt_BR": 2, "ru_RU": 2, "tr_TR": 2, "cs_CZ": 2,
    "el_GR": 1, "hu_HU": 2, "ro_RO": 2, "id_ID": 2,
    "ko_KR": 2, "ja_JP": 2, "zh_CN": 2, "zh_TW": 2,
    "th_TH": 1, "vi_VN": 1, "ar_AE": 1,
}


def _load_manifest() -> dict[str, list[dict]]:
    if not MANIFEST.is_file():
        return {}
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    grouped: dict[str, list[dict]] = {}
    for entry in entries:
        grouped.setdefault(entry["locale"], []).append(entry)
    return grouped


GROUPS = _load_manifest()


@pytest.fixture(scope="module")
def transcriber():
    if support.ffmpeg_binary() is None:
        pytest.skip("brak ffmpeg w PATH")
    ready, reason = support.whisper_status()
    if not ready:
        pytest.skip(f"rozpoznawanie mowy niedostepne: {reason}")
    try:
        return support.load_transcriber()
    except Exception as exc:
        pytest.skip(f"nie udalo sie zaladowac modelu: {exc}")


@pytest.mark.skipif(not GROUPS, reason="brak fixture'ow, uruchom tests/tools/generate_command_fixtures.py")
@pytest.mark.parametrize("locale", sorted(GROUPS))
def test_commands_recognized_per_language(locale: str, transcriber) -> None:
    entries = GROUPS[locale]
    mapping = MappingManager(Settings(language=locale))
    mapping.mode = "letters"

    hits = 0
    report = []
    for entry in entries:
        path = COMMANDS_DIR / entry["file"]
        if not path.is_file():
            report.append(f"  BRAK PLIKU {entry['file']}")
            continue
        pcm = support.decode_pcm(path)
        heard = transcriber.transcribe_pcm(pcm, locale)
        matched = mapping.match_command(heard) if heard else None
        ok = matched == entry["expected"]
        hits += ok
        report.append(
            f"  {'OK ' if ok else 'MISS'} {entry['phrase']!r} -> uslyszano {heard!r} -> {matched!r}"
            f" (oczekiwano {entry['expected']!r})"
        )

    required = REQUIRED_HITS.get(locale, 1)
    detail = "\n".join(report)
    assert hits >= required, (
        f"{locale}: {hits}/{len(entries)} trafien, wymagane co najmniej {required}\n{detail}"
    )
