"""Wspolne narzedzia dla testow e2e audio.

Zawiera to, czego potrzebuja oba testy w tests/e2e:

* czytanie manifestu fixture'ow audio (tests/fixtures/audio/{lang}/manifest.json),
* dekodowanie MP3 do PCM 16 kHz mono int16 przez ffmpeg,
* skladanie VoiceService z atrapa klawiatury i mapowaniami bohatera,
* wykrywanie, czy w ogole da sie zaladowac backend Whispera,
* zbieranie wynikow i zapis tests/reports/recognition_report.json.

Modul nie definiuje zadnych fixture'ow pytest. Konfiguracje srodowiska
(LOLVOICE_HOME, LOLVOICE_DDRAGON_FIXTURES) trzyma conftest.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
AUDIO_DIR = REPO_ROOT / "tests" / "fixtures" / "audio"
DDRAGON_DIR = REPO_ROOT / "tests" / "fixtures" / "ddragon"
REPORTS_DIR = REPO_ROOT / "tests" / "reports"
DEFAULT_REPORT = REPORTS_DIR / "recognition_report.json"

LANGUAGES = ("pl_PL", "en_US")
SLOT_KEYS = {"Q": "q", "W": "w", "E": "e", "R": "r"}

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# --- fixture'y audio --------------------------------------------------


@dataclass(frozen=True)
class AudioFixture:
    path: Path
    language: str
    champion: str
    slot: str
    phrase: str
    voice: str

    @property
    def expected_key(self) -> str:
        return SLOT_KEYS[self.slot]

    @property
    def label(self) -> str:
        return f"{self.language}/{self.champion}/{self.slot}"


def manifest_path(language: str, root: Path | None = None) -> Path:
    return (root or AUDIO_DIR) / language / "manifest.json"


def load_fixtures(language: str, root: Path | None = None) -> list[AudioFixture]:
    """Wpisy manifestu, dla ktorych plik MP3 naprawde istnieje i nie jest pusty."""
    path = manifest_path(language, root)
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    fixtures: list[AudioFixture] = []
    for entry in payload.get("files", []):
        audio = REPO_ROOT / entry["file"]
        if not audio.is_file() or audio.stat().st_size == 0:
            continue
        fixtures.append(
            AudioFixture(
                path=audio,
                language=entry.get("language", language),
                champion=entry["champion"],
                slot=entry["slot"],
                phrase=entry["phrase"],
                voice=entry.get("voice", ""),
            )
        )
    return sorted(fixtures, key=lambda f: (f.champion, f.slot))


def available_languages(root: Path | None = None) -> list[str]:
    return [lang for lang in LANGUAGES if manifest_path(lang, root).is_file()]


def fixture_engine(language: str, root: Path | None = None) -> str:
    path = manifest_path(language, root)
    if not path.is_file():
        return "unknown"
    return json.loads(path.read_text(encoding="utf-8")).get("engine", "unknown")


# --- dekodowanie audio ------------------------------------------------


def ffmpeg_binary() -> str | None:
    return shutil.which("ffmpeg")


def decode_pcm(path: Path, sample_rate: int = 16000) -> bytes:
    """MP3 na surowy PCM mono int16 o zadanej czestotliwosci."""
    ffmpeg = ffmpeg_binary()
    if not ffmpeg:
        raise RuntimeError("Nie znaleziono ffmpeg w PATH")
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-f",
        "s16le",
        "-acodec",
        "pcm_s16le",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-",
    ]
    result = subprocess.run(command, capture_output=True)
    if result.returncode != 0 or not result.stdout:
        raise RuntimeError(f"ffmpeg nie zdekodowal {path.name}: {result.stderr.decode(errors='replace')[:300]}")
    return result.stdout


def silence_pcm(seconds: float = 0.5, sample_rate: int = 16000) -> bytes:
    """Cichy bufor PCM, gdy test potrzebuje audio, ale tresc nie ma znaczenia."""
    return b"\x00\x00" * int(sample_rate * seconds)


# --- mapowania bohaterow ----------------------------------------------


def champion_mappings(champion: str, language: str, ddragon_dir: Path | None = None) -> dict[str, str]:
    """Mapowania fraza -> klawisz dla bohatera, prosto z fixture'u Data Dragon."""
    from game.lol_data_manager import LoLDataManager

    manager = LoLDataManager(language=language, fixture_dir=ddragon_dir or DDRAGON_DIR)
    return manager.create_voice_mappings(champion)


# --- serwis pod testy -------------------------------------------------


class RecordingKeyController:
    """Atrapa klawiatury: zapisuje wcisniecia zamiast dotykac pynput."""

    def __init__(self) -> None:
        self.pressed: list[str] = []

    def press_key(self, key: str) -> bool:
        self.pressed.append(key)
        return True

    @property
    def available(self) -> bool:
        return True

    @property
    def last(self) -> str | None:
        return self.pressed[-1] if self.pressed else None

    def reset(self) -> None:
        self.pressed.clear()


def make_service(language: str = "pl_PL", mode: str = "spells"):
    """Swiezy VoiceService z atrapa klawiatury. Zwraca (service, keys)."""
    from app.config import Settings
    from controller.service import VoiceService

    service = VoiceService()
    service.apply_settings(Settings(language=language, recognition_mode=mode))
    keys = RecordingKeyController()
    service._key_controller = keys
    return service, keys


def load_champion(service, champion: str, language: str, ddragon_dir: Path | None = None) -> dict[str, str]:
    mappings = champion_mappings(champion, language, ddragon_dir)
    service.mapping_manager.load_champion_mappings(mappings)
    return mappings


# --- backend Whispera -------------------------------------------------


def whisper_status() -> tuple[bool, str]:
    """(gotowy, powod). Powod jest komunikatem dla pytest.skip, gdy gotowy jest False."""
    try:
        from app import engines, paths
    except Exception as exc:
        return False, f"nie udalo sie zaimportowac app.engines: {exc}"

    # Autouse lolvoice_home zostawia po tescie moduly paths/config wycelowane w
    # skasowany katalog tymczasowy. Sesyjne fixture'y startuja przed jego
    # kolejnym setupem, wiec wracamy do wartosci z aktualnego srodowiska.
    paths.refresh()
    from app import config

    config.reset_cache()

    try:
        engine = engines.resolve_active()
    except Exception as exc:
        return False, (
            f"zaden silnik mowy nie jest zainstalowany ({exc}). "
            "Pobierz model, np. python -c \"from app import engines; engines.download('whisper-tiny')\""
        )

    if engine.backend == "pywhispercpp":
        try:
            import pywhispercpp  # noqa: F401
        except ImportError:
            return False, "brak backendu pywhispercpp (pip install pywhispercpp)"
    elif engine.backend == "faster-whisper":
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            return False, "brak backendu faster-whisper (pip install faster-whisper)"
    else:
        return False, f"nieznany backend silnika: {engine.backend}"

    return True, f"silnik {engine.id} ({engine.backend})"


def load_transcriber():
    """Zaladowany Transcriber albo RuntimeError z czytelnym powodem."""
    from controller.transcriber import Transcriber

    transcriber = Transcriber()
    transcriber.load()
    return transcriber


# --- raport -----------------------------------------------------------


@dataclass
class Result:
    language: str
    champion: str
    slot: str
    phrase: str
    heard: str
    expected_key: str
    matched: str | None

    @property
    def ok(self) -> bool:
        return self.matched == self.expected_key

    def as_dict(self) -> dict:
        return {
            "slot": self.slot,
            "phrase": self.phrase,
            "heard": self.heard,
            "expected_key": self.expected_key,
            "matched": self.matched,
            "ok": self.ok,
        }


@dataclass
class ReportCollector:
    """Zbiera wyniki rozpoznawania i zapisuje recognition_report.json."""

    tier: str = "smoke"
    engine: str = "unknown"
    fixture_engine: str = "unknown"
    results: list[Result] = field(default_factory=list)

    def add(self, result: Result) -> None:
        """Dopisuje wynik. Powtorka dla tej samej probki nadpisuje poprzedni wpis,
        wiec poziom pelny nie dolicza sie do wynikow poziomu smoke."""
        key = (result.language, result.champion, result.slot)
        for index, existing in enumerate(self.results):
            if (existing.language, existing.champion, existing.slot) == key:
                self.results[index] = result
                return
        self.results.append(result)

    @staticmethod
    def _accuracy(results: list[Result]) -> float:
        if not results:
            return 0.0
        return round(sum(1 for r in results if r.ok) / len(results), 4)

    def accuracy_for(self, language: str) -> float:
        return self._accuracy([r for r in self.results if r.language == language])

    def count_for(self, language: str) -> int:
        return sum(1 for r in self.results if r.language == language)

    def as_dict(self) -> dict:
        languages: dict[str, dict] = {}
        for language in sorted({r.language for r in self.results}):
            per_language = [r for r in self.results if r.language == language]
            champions: dict[str, dict] = {}
            for champion in sorted({r.champion for r in per_language}):
                per_champion = [r for r in per_language if r.champion == champion]
                champions[champion] = {
                    "accuracy": self._accuracy(per_champion),
                    "total": len(per_champion),
                    "correct": sum(1 for r in per_champion if r.ok),
                    "slots": {r.slot: r.as_dict() for r in sorted(per_champion, key=lambda r: r.slot)},
                }
            languages[language] = {
                "accuracy": self._accuracy(per_language),
                "total": len(per_language),
                "correct": sum(1 for r in per_language if r.ok),
                "champions": champions,
            }

        return {
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "tier": self.tier,
            "speech_engine": self.engine,
            "fixture_engine": self.fixture_engine,
            "accuracy": self._accuracy(self.results),
            "total": len(self.results),
            "correct": sum(1 for r in self.results if r.ok),
            "languages": languages,
        }

    def write(self, path: Path | None = None) -> Path:
        target = path or report_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.as_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return target


def report_path() -> Path:
    """tests/reports/recognition_report.json, chyba ze LOLVOICE_AUDIO_REPORT mowi inaczej."""
    override = os.environ.get("LOLVOICE_AUDIO_REPORT")
    if override:
        candidate = Path(override)
        return candidate if candidate.is_absolute() else REPO_ROOT / candidate
    return DEFAULT_REPORT
