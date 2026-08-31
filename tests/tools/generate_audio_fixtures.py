#!/usr/bin/env python3
"""Generator fixture'ow audio: wypowiedziane nazwy umiejetnosci kazdego bohatera.

Zrodlem prawdy sa dumpy Data Dragon z tests/fixtures/ddragon/championFull.{lang}.json.
Wyjscie:

    tests/fixtures/audio/{lang}/{Champion}/{Q|W|E|R}.mp3
    tests/fixtures/audio/{lang}/manifest.json

Kazdy plik to mono 16 kHz MP3 przyciety z ciszy, okolo 1-2 sekund.

Silniki TTS
-----------
Domyslny silnik to edge-tts (glosy pl-PL-MarekNeural i en-US-GuyNeural). Tak
generowany jest pelny zestaw w CI (workflow nightly.yml) i tak powinno sie
generowac lokalnie.

Zapasowy silnik to espeak-ng (--engine espeak). Jest offline i brzydki, ale nie
wymaga sieci. Sluzy do tego, zeby sciezka testow e2e dawala sie uruchomic w
srodowisku bez dostepu do endpointu Microsoftu.

UWAGA dla czytajacego repozytorium: zacommitowany zestaw smoke w
tests/fixtures/audio zostal wygenerowany przez espeak-ng, poniewaz kontener, w
ktorym powstawal, ma zablokowane wyjscie na speech.platform.bing.com (proxy
zwraca 403 na handshake WebSocket). CI regeneruje pelny zestaw przez edge-tts.
Zeby odtworzyc zestaw smoke glosami neuronowymi:

    python tests/tools/generate_audio_fixtures.py --smoke --force

Przyklady
---------
    python tests/tools/generate_audio_fixtures.py --voice-check
    python tests/tools/generate_audio_fixtures.py --smoke
    python tests/tools/generate_audio_fixtures.py --champions Ahri,Jinx --lang pl_PL
    python tests/tools/generate_audio_fixtures.py --all          # pelne ~1400 plikow

Skrypt jest wznawialny: pliki, ktore juz istnieja i nie sa puste, sa pomijane
(chyba ze podano --force). Pliki zerowej dlugosci sa kasowane, zeby nieudana
synteza nie udawala gotowego fixture'a.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

# Za antywirusem lub proxy z podmiana TLS certifi nie zna wystawcy. Magazyn
# systemowy go zna, wiec bierzemy go, gdy truststore jest dostepny.
try:
    import truststore

    truststore.inject_into_ssl()
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parents[2]
DDRAGON_DIR = REPO_ROOT / "tests" / "fixtures" / "ddragon"
AUDIO_DIR = REPO_ROOT / "tests" / "fixtures" / "audio"

SLOTS = ("Q", "W", "E", "R")

VOICES = {
    "pl_PL": "pl-PL-MarekNeural",
    "en_US": "en-US-GuyNeural",
}
ESPEAK_VOICES = {
    "pl_PL": "pl",
    "en_US": "en-us",
}
LANGUAGES = tuple(VOICES)

# Zestaw smoke: bohaterowie o fonetycznie roznych nazwach umiejetnosci,
# z polskimi znakami diakrytycznymi i nazwami wielowyrazowymi.
SMOKE_CHAMPIONS = (
    "Ahri",
    "Aatrox",
    "Jinx",
    "Lux",
    "Yasuo",
    "Zed",
    "Garen",
    "Katarina",
    "Thresh",
    "Hwei",
)

DEFAULT_CONCURRENCY = 6
MAX_ATTEMPTS = 4
BACKOFF_BASE = 1.5

# Przyciecie ciszy z obu koncow, potem mono 16 kHz.
SILENCE_FILTER = (
    "silenceremove=start_periods=1:start_duration=0:start_threshold=-45dB,"
    "areverse,"
    "silenceremove=start_periods=1:start_duration=0:start_threshold=-45dB,"
    "areverse"
)


class TtsUnavailable(RuntimeError):
    """Endpoint TTS jest nieosiagalny albo odmawia obslugi."""


@dataclass(frozen=True)
class Job:
    lang: str
    champion: str
    display_name: str
    slot: str
    phrase: str
    voice: str
    path: Path


# --- dane wejsciowe ---------------------------------------------------


def load_champions(lang: str, ddragon_dir: Path) -> dict[str, dict]:
    """Zwraca {klucz_bohatera: dane} z fixture'u Data Dragon dla danego jezyka."""
    path = ddragon_dir / f"championFull.{lang}.json"
    if not path.is_file():
        raise SystemExit(
            f"Brak fixture'u Data Dragon: {path}\n"
            "Uruchom najpierw tests/tools/refresh_fixtures.py albo wskaz katalog przez --ddragon."
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    data = payload.get("data", payload)
    return data


def build_jobs(
    lang: str,
    ddragon_dir: Path,
    out_dir: Path,
    champions: list[str] | None,
    limit: int | None,
    voice: str,
) -> list[Job]:
    data = load_champions(lang, ddragon_dir)
    keys = sorted(data)

    if champions:
        wanted = {c.strip().lower() for c in champions if c.strip()}
        by_alias: dict[str, str] = {}
        for key, champ in data.items():
            by_alias[key.lower()] = key
            by_alias[str(champ.get("name", "")).lower()] = key
        missing = sorted(w for w in wanted if w not in by_alias)
        if missing:
            raise SystemExit(f"Nieznani bohaterowie: {', '.join(missing)}")
        keys = sorted({by_alias[w] for w in wanted})

    if limit is not None:
        keys = keys[:limit]

    jobs: list[Job] = []
    for key in keys:
        champ = data[key]
        spells = champ.get("spells") or []
        if len(spells) < 4:
            continue
        for index, slot in enumerate(SLOTS):
            phrase = str(spells[index].get("name", "")).strip()
            if not phrase:
                continue
            jobs.append(
                Job(
                    lang=lang,
                    champion=key,
                    display_name=str(champ.get("name", key)),
                    slot=slot,
                    phrase=phrase,
                    voice=voice,
                    path=out_dir / lang / key / f"{slot}.mp3",
                )
            )
    return jobs


# --- narzedzia audio --------------------------------------------------


def require_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit(
            "Nie znaleziono ffmpeg w PATH. Zainstaluj ffmpeg (Windows: winget install Gyan.FFmpeg, "
            "Ubuntu: sudo apt install ffmpeg) i uruchom ponownie."
        )
    return ffmpeg


def normalize_audio(ffmpeg: str, source: Path, target: Path) -> None:
    """Mono 16 kHz MP3 przyciety z ciszy."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp.mp3")
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-af",
        SILENCE_FILTER,
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "32k",
        str(tmp),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0 or not tmp.is_file() or tmp.stat().st_size == 0:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"ffmpeg nie przetworzyl {source.name}: {result.stderr.strip()[:300]}")
    tmp.replace(target)


# --- silniki TTS ------------------------------------------------------


class EdgeEngine:
    """edge-tts: neuronowe glosy Microsoftu, wymaga sieci."""

    name = "edge-tts"

    def __init__(self) -> None:
        try:
            import edge_tts  # noqa: F401
        except ImportError as exc:  # brak pakietu to blad konfiguracji, nie sieci
            raise SystemExit(
                "Brak pakietu edge-tts. Zainstaluj: pip install edge-tts, albo uruchom z --engine espeak."
            ) from exc
        self._trust_extra_ca()

    @staticmethod
    def _trust_extra_ca() -> None:
        """edge-tts trzyma wlasny kontekst SSL na certifi, wiec proxy firmowe trzeba mu dolozyc."""
        bundle = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
        if not bundle or not Path(bundle).is_file():
            return
        try:
            from edge_tts import communicate as edge_communicate

            edge_communicate._SSL_CTX.load_verify_locations(bundle)
        except Exception as exc:  # brak atrybutu w innej wersji edge-tts nie jest bledem krytycznym
            print(f"Uwaga: nie udalo sie dolozyc CA {bundle} do edge-tts ({exc})", file=sys.stderr)

    def voice_for(self, lang: str) -> str:
        return VOICES[lang]

    async def synthesize(self, phrase: str, voice: str, target: Path) -> None:
        import edge_tts

        target.parent.mkdir(parents=True, exist_ok=True)
        communicate = edge_tts.Communicate(phrase, voice)
        try:
            await communicate.save(str(target))
        except Exception as exc:
            target.unlink(missing_ok=True)
            raise _classify_edge_error(exc) from exc
        if not target.is_file() or target.stat().st_size == 0:
            # edge-tts zostawia plik zerowej dlugosci, gdy strumien nie przyszedl.
            target.unlink(missing_ok=True)
            raise TtsUnavailable("edge-tts zwrocil pusty strumien audio")


def _classify_edge_error(exc: Exception) -> Exception:
    text = f"{type(exc).__name__}: {exc}"
    markers = (
        "403",
        "CERTIFICATE_VERIFY_FAILED",
        "Cannot connect",
        "ClientConnector",
        "Temporary failure in name resolution",
        "handshake",
        "Handshake",
        "TimeoutError",
        "NoAudioReceived",
    )
    if any(marker in text for marker in markers):
        return TtsUnavailable(text)
    return exc


class EspeakEngine:
    """espeak-ng: offline, syntetyczny glos, zapasowy tor generowania."""

    name = "espeak-ng"

    def __init__(self) -> None:
        self.binary = shutil.which("espeak-ng") or shutil.which("espeak")
        if not self.binary:
            raise SystemExit(
                "Nie znaleziono espeak-ng w PATH. Zainstaluj (Ubuntu: sudo apt install espeak-ng, "
                "Windows: winget install eSpeak-NG) albo uzyj domyslnego silnika edge."
            )

    def voice_for(self, lang: str) -> str:
        return f"espeak-ng:{ESPEAK_VOICES[lang]}"

    async def synthesize(self, phrase: str, voice: str, target: Path) -> None:
        espeak_voice = voice.split(":", 1)[-1]
        target.parent.mkdir(parents=True, exist_ok=True)
        wav = target.with_suffix(".wav")
        process = await asyncio.create_subprocess_exec(
            self.binary,
            "-v",
            espeak_voice,
            "-s",
            "150",
            "-p",
            "40",
            "-w",
            str(wav),
            phrase,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _out, err = await process.communicate()
        try:
            if process.returncode != 0 or not wav.is_file() or wav.stat().st_size == 0:
                raise RuntimeError(f"espeak-ng nie wygenerowal audio: {err.decode(errors='replace')[:200]}")
            wav.replace(target)
        finally:
            wav.unlink(missing_ok=True)


def make_engine(name: str) -> EdgeEngine | EspeakEngine:
    return EdgeEngine() if name == "edge" else EspeakEngine()


# --- generowanie ------------------------------------------------------


@dataclass
class Stats:
    generated: int = 0
    skipped: int = 0
    failed: int = 0
    total_bytes: int = 0
    failures: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.failures is None:
            self.failures = []


async def run_job(
    job: Job,
    engine,
    ffmpeg: str,
    semaphore: asyncio.Semaphore,
    stats: Stats,
    unreachable: asyncio.Event,
    verbose: bool,
) -> dict | None:
    """Synteza jednego pliku z ponowieniami. Zwraca wpis do manifestu albo None."""
    async with semaphore:
        if unreachable.is_set():
            stats.failed += 1
            return None

        last_error: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            raw = Path(tempfile.gettempdir()) / f"lolvoice-tts-{os.getpid()}-{id(job)}-{attempt}.mp3"
            try:
                await engine.synthesize(job.phrase, job.voice, raw)
                await asyncio.to_thread(normalize_audio, ffmpeg, raw, job.path)
                size = job.path.stat().st_size
                stats.generated += 1
                stats.total_bytes += size
                if verbose:
                    print(f"  ok  {job.lang}/{job.champion}/{job.slot}.mp3  {job.phrase!r}  {size} B")
                return manifest_entry(job, size)
            except TtsUnavailable as exc:
                last_error = exc
                if attempt == MAX_ATTEMPTS:
                    unreachable.set()
                    break
                await asyncio.sleep(BACKOFF_BASE**attempt)
            except Exception as exc:
                last_error = exc
                if attempt == MAX_ATTEMPTS:
                    break
                await asyncio.sleep(BACKOFF_BASE**attempt)
            finally:
                raw.unlink(missing_ok=True)

        stats.failed += 1
        stats.failures.append(f"{job.lang}/{job.champion}/{job.slot}: {last_error}")
        job.path.unlink(missing_ok=True)
        return None


def relative_file(path: Path) -> str:
    """Sciezka wzgledem repo, a gdy plik lezy poza repo (--out), sciezka bezwzgledna."""
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def manifest_entry(job: Job, size: int) -> dict:
    return {
        "file": relative_file(job.path),
        "champion": job.champion,
        "champion_name": job.display_name,
        "slot": job.slot,
        "phrase": job.phrase,
        "voice": job.voice,
        "language": job.lang,
        "bytes": size,
    }


def existing_entry(job: Job) -> dict:
    return manifest_entry(job, job.path.stat().st_size)


def load_manifest(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {entry["file"]: entry for entry in payload.get("files", [])}


def write_manifest(path: Path, lang: str, engine_name: str, entries: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = [entries[key] for key in sorted(entries)]
    payload = {
        "language": lang,
        "voice": VOICES[lang],
        "engine": engine_name,
        "generator": "tests/tools/generate_audio_fixtures.py",
        "sample_rate": 16000,
        "channels": 1,
        "count": len(ordered),
        "files": ordered,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def generate_language(
    lang: str,
    jobs: list[Job],
    engine,
    ffmpeg: str,
    out_dir: Path,
    concurrency: int,
    force: bool,
    stats: Stats,
    unreachable: asyncio.Event,
    verbose: bool,
) -> None:
    manifest_path = out_dir / lang / "manifest.json"
    entries = load_manifest(manifest_path)

    pending: list[Job] = []
    for job in jobs:
        if job.path.is_file() and job.path.stat().st_size == 0:
            job.path.unlink()  # nie udawaj, ze pusty plik jest gotowy
        if job.path.is_file() and not force:
            stats.skipped += 1
            stats.total_bytes += job.path.stat().st_size
            entries[relative_file(job.path)] = existing_entry(job)
            continue
        pending.append(job)

    if pending:
        semaphore = asyncio.Semaphore(concurrency)
        results = await asyncio.gather(
            *(run_job(job, engine, ffmpeg, semaphore, stats, unreachable, verbose) for job in pending)
        )
        for entry in results:
            if entry:
                entries[entry["file"]] = entry

    write_manifest(manifest_path, lang, engine.name, entries)


def human_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


# --- CLI --------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generuje fixture'y audio MP3 z nazwami umiejetnosci bohaterow.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Pelny zestaw (okolo 1400 plikow, oba jezyki):\n"
            "  python tests/tools/generate_audio_fixtures.py --all\n"
        ),
    )
    parser.add_argument(
        "--lang",
        default="all",
        help="Jezyk albo lista po przecinku: pl_PL, en_US, all (domyslnie all).",
    )
    parser.add_argument("--champions", help="Lista bohaterow po przecinku, np. Ahri,Jinx,Lux.")
    parser.add_argument("--limit", type=int, help="Ogranicza liczbe bohaterow (po posortowaniu).")
    parser.add_argument("--smoke", action="store_true", help=f"Zestaw smoke: {', '.join(SMOKE_CHAMPIONS)}.")
    parser.add_argument("--all", action="store_true", help="Wszyscy bohaterowie i oba jezyki.")
    parser.add_argument("--voice-check", action="store_true", help="Generuje jedna probke i konczy.")
    parser.add_argument("--engine", choices=("edge", "espeak"), default="edge", help="Silnik TTS.")
    parser.add_argument("--out", type=Path, default=AUDIO_DIR, help="Katalog wyjsciowy.")
    parser.add_argument("--ddragon", type=Path, default=DDRAGON_DIR, help="Katalog z dumpami Data Dragon.")
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY, help="Rownolegle syntezy.")
    parser.add_argument("--force", action="store_true", help="Nadpisuje istniejace pliki.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Wypisuje kazdy plik.")
    return parser.parse_args(argv)


def resolve_languages(value: str) -> list[str]:
    if value.strip().lower() == "all":
        return list(LANGUAGES)
    langs = [item.strip() for item in value.split(",") if item.strip()]
    unknown = [lang for lang in langs if lang not in LANGUAGES]
    if unknown:
        raise SystemExit(f"Nieznany jezyk: {', '.join(unknown)}. Dostepne: {', '.join(LANGUAGES)}")
    return langs


async def voice_check(engine, ffmpeg: str, out: Path, lang: str) -> int:
    phrase = "Zwodnicza Kula" if lang == "pl_PL" else "Orb of Deception"
    target = out / "_voice-check" / f"{lang}.mp3"
    raw = Path(tempfile.gettempdir()) / f"lolvoice-voice-check-{os.getpid()}.mp3"
    print(f"Probka: {engine.name}, {engine.voice_for(lang)}, tekst {phrase!r}")
    try:
        await engine.synthesize(phrase, engine.voice_for(lang), raw)
        await asyncio.to_thread(normalize_audio, ffmpeg, raw, target)
    except TtsUnavailable as exc:
        print(unreachable_message(engine.name, exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Synteza nie powiodla sie: {exc}", file=sys.stderr)
        return 1
    finally:
        raw.unlink(missing_ok=True)
    print(f"OK, zapisano {target} ({target.stat().st_size} B)")
    return 0


def unreachable_message(engine_name: str, error: object) -> str:
    return (
        f"\nSilnik TTS '{engine_name}' jest nieosiagalny: {error}\n"
        "Nie wygenerowano zadnych plikow (puste pliki sa kasowane, zeby nie udawaly fixture'ow).\n"
        "Co mozna zrobic:\n"
        "  1. Sprawdz polaczenie z siecia i ewentualne proxy firmowe.\n"
        "     Odpowiedz 403 na handshake WebSocket oznacza, ze speech.platform.bing.com\n"
        "     jest zablokowany przez polityke wyjscia, a nie ze edge-tts jest zepsuty.\n"
        "  2. Sprobuj probki: python tests/tools/generate_audio_fixtures.py --voice-check\n"
        "  3. Wygeneruj offline: python tests/tools/generate_audio_fixtures.py --smoke --engine espeak\n"
        "     (gorsza jakosc glosu, ale sciezka e2e jest przechodzona w calosci).\n"
    )


async def async_main(args: argparse.Namespace) -> int:
    ffmpeg = require_ffmpeg()
    engine = make_engine(args.engine)
    languages = resolve_languages(args.lang)

    if args.voice_check:
        return await voice_check(engine, ffmpeg, args.out, languages[0])

    champions = None
    if args.smoke:
        champions = list(SMOKE_CHAMPIONS)
    if args.champions:
        champions = args.champions.split(",")
    if args.all:
        champions = None

    stats = Stats()
    unreachable = asyncio.Event()
    started = time.monotonic()

    plan: dict[str, list[Job]] = {}
    for lang in languages:
        plan[lang] = build_jobs(
            lang=lang,
            ddragon_dir=args.ddragon,
            out_dir=args.out,
            champions=champions,
            limit=args.limit,
            voice=engine.voice_for(lang),
        )

    total = sum(len(jobs) for jobs in plan.values())
    print(
        f"Silnik: {engine.name}, jezyki: {', '.join(languages)}, plikow do rozpatrzenia: {total}, "
        f"rownoleglosc: {args.concurrency}"
    )

    for lang, jobs in plan.items():
        await generate_language(
            lang=lang,
            jobs=jobs,
            engine=engine,
            ffmpeg=ffmpeg,
            out_dir=args.out,
            concurrency=max(1, args.concurrency),
            force=args.force,
            stats=stats,
            unreachable=unreachable,
            verbose=args.verbose,
        )

    elapsed = time.monotonic() - started
    print(
        f"\nPodsumowanie: wygenerowane {stats.generated}, pominiete {stats.skipped}, "
        f"nieudane {stats.failed}, razem {human_bytes(stats.total_bytes)}, czas {elapsed:.1f} s"
    )
    for failure in stats.failures[:10]:
        print(f"  blad: {failure}")
    if len(stats.failures) > 10:
        print(f"  ... i {len(stats.failures) - 10} dalszych bledow")

    if unreachable.is_set():
        print(unreachable_message(engine.name, "przerwano po serii nieudanych prob"), file=sys.stderr)
        return 2
    return 1 if stats.failed else 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return asyncio.run(async_main(args))
    except KeyboardInterrupt:
        print("\nPrzerwano. Skrypt jest wznawialny, uruchom ponownie.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
