#!/usr/bin/env python3
"""Jedna komenda, ktora mierzy realna skutecznosc rozpoznawania.

Robi po kolei trzy rzeczy, ktorych nie da sie zrobic bez dostepu do sieci:

1. pobiera model mowy (domyslnie whisper-tiny, okolo 75 MB z huggingface),
2. generuje na nowo probki audio glosami neuronowymi edge-tts,
   bo te zapisane w repo powstaly offline w espeak-ng i brzmia robotycznie,
3. uruchamia testy rozpoznawania i wypisuje skutecznosc per jezyk.

Uzycie:
    python tools/verify_recognition.py
    python tools/verify_recognition.py --engine whisper-base --full

Kazdy krok mozna pominac, jesli juz go wykonales:
    --skip-download  --skip-fixtures
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

REPORT = ROOT / "tests" / "reports" / "recognition_report.json"


def human(size: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def step(number: int, title: str) -> None:
    print(f"\n[{number}/3] {title}")


def download_model(engine_id: str) -> bool:
    from app import engines

    engine = engines.get(engine_id)
    if engine is None:
        print(f"  Nie znam silnika '{engine_id}'. Dostepne: {[e['id'] for e in engines.list_engines()]}")
        return False
    if engine.is_installed():
        print(f"  {engine.name} jest juz na dysku: {engine.local_path()}")
        return True

    print(f"  Pobieram {engine.name}, okolo {human(engine.size_bytes)}")
    last = [0.0]

    def progress(_id: str, done: int, total: int) -> None:
        now = time.time()
        if now - last[0] < 0.5 and done < total:
            return
        last[0] = now
        pct = (done / total * 100) if total else 0
        print(f"\r  {pct:5.1f}%  {human(done)} z {human(total)}", end="", flush=True)

    try:
        path = engines.download(engine_id, progress=progress)
    except Exception as exc:
        print(f"\n  Pobieranie nie powiodlo sie: {type(exc).__name__}: {exc}")
        print("  Sprawdz polaczenie i dostep do huggingface.co, potem uruchom ponownie.")
        return False
    print(f"\n  Zapisano: {path}")
    return True


def regenerate_fixtures(full: bool) -> bool:
    scope = "--all" if full else "--smoke"
    print(f"  Generuje probki edge-tts ({scope})")
    result = subprocess.run(
        [sys.executable, str(ROOT / "tests" / "tools" / "generate_audio_fixtures.py"), scope, "--force"],
        cwd=ROOT,
    )
    if result.returncode != 0:
        print("  Generator zwrocil blad. Probki z repo zostaja nietkniete, testy nadal sie uruchomia,")
        print("  ale wynik bedzie zanizony, bo pliki espeak brzmia inaczej niz ludzki glos.")
        return False
    return True


def run_tests(full: bool) -> int:
    markers = "audio" if not full else "audio or slow"
    cmd = [sys.executable, "-m", "pytest", "-m", markers, "-q", "tests/e2e/test_recognition.py"]
    print(f"  {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=ROOT).returncode


def print_report() -> None:
    if not REPORT.is_file():
        print("\nBrak raportu. Testy zostaly pominiete albo przerwane.")
        return
    data = json.loads(REPORT.read_text(encoding="utf-8"))
    print("\nSkutecznosc rozpoznawania")
    print(f"  Calosc: {data.get('accuracy', 0) * 100:.1f}%")
    for language, entry in sorted((data.get("languages") or {}).items()):
        accuracy = entry.get("accuracy", 0) * 100
        hits = entry.get("hits", 0)
        total = entry.get("total", 0)
        print(f"  {language}: {accuracy:.1f}%  ({hits} z {total})")
    worst = sorted(
        ((name, item.get("accuracy", 0)) for name, item in (data.get("champions") or {}).items()),
        key=lambda pair: pair[1],
    )[:5]
    if worst:
        print("  Najslabsi bohaterowie:")
        for name, accuracy in worst:
            print(f"    {name}: {accuracy * 100:.0f}%")
    print(f"\nPelny raport: {REPORT}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Pobiera model, odswieza probki i mierzy rozpoznawanie.")
    parser.add_argument("--engine", default="whisper-tiny", help="Identyfikator silnika z data/engines.json")
    parser.add_argument("--full", action="store_true", help="Wszyscy bohaterowie zamiast zestawu smoke")
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--skip-fixtures", action="store_true")
    args = parser.parse_args()

    step(1, "Model mowy")
    if args.skip_download:
        print("  pominiete")
    elif not download_model(args.engine):
        return 1

    step(2, "Probki audio")
    if args.skip_fixtures:
        print("  pominiete")
    else:
        regenerate_fixtures(args.full)

    step(3, "Testy rozpoznawania")
    code = run_tests(args.full)
    print_report()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
