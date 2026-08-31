"""Start bez konsoli: wersja okienkowa nie ma stdout ani stderr.

Windows nie daje konsoli aplikacji uruchomionej kliknieciem ikony, wiec
sys.stdout jest None. Biblioteki tego nie sprawdzaja: formatter uvicorna wola
isatty() na stdout, przez co wywracala sie konfiguracja logowania, a z nia
start calej aplikacji.

Testy chodza w podprocesie, bo pytest przechwytuje wyjscie i podstawia wlasny
sys.stdout, wiec w samym tescie nie da sie wiernie odtworzyc braku konsoli.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

PREAMBLE = """
import sys
sys.path.insert(0, r"{root}")
sys.stdout = None
sys.stderr = None
sys.stdin = None
result = "brak wyniku"
"""

EPILOGUE = """
open(r"{out}", "w", encoding="utf-8").write(result)
"""


def run_headless(tmp_path: Path, body: str) -> str:
    """Uruchamia body w procesie bez strumieni standardowych, zwraca wynik."""
    out = tmp_path / "result.txt"
    script = (
        PREAMBLE.format(root=REPO_ROOT)
        + textwrap.dedent(body)
        + EPILOGUE.format(out=out)
    )
    process = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert process.returncode == 0, f"podproces padl: {process.stderr[-600:]}"
    return out.read_text(encoding="utf-8")


def test_uvicorn_formatter_crashes_without_the_guard(tmp_path):
    """Kontrola negatywna: dokladnie ten wyjatek widzial uzytkownik."""
    result = run_headless(
        tmp_path,
        """
        import uvicorn.logging
        try:
            uvicorn.logging.DefaultFormatter(fmt="%(message)s")
            result = "brak bledu"
        except AttributeError as exc:
            result = f"AttributeError: {exc}"
        """,
    )
    assert "isatty" in result, result


def test_uvicorn_formatter_works_after_the_guard(tmp_path):
    result = run_headless(
        tmp_path,
        """
        import main
        import uvicorn.logging
        main.ensure_std_streams()
        formatter = uvicorn.logging.DefaultFormatter(fmt="%(message)s")
        result = f"use_colors={formatter.use_colors}"
        """,
    )
    assert result == "use_colors=False", result


def test_streams_are_usable_again(tmp_path):
    result = run_headless(
        tmp_path,
        """
        import main
        main.ensure_std_streams()
        missing = [n for n in ("stdout", "stderr", "stdin") if getattr(sys, n) is None]
        sys.stdout.write("nie moze rzucic")
        sys.stdout.flush()
        result = f"missing={missing} isatty={sys.stdout.isatty()}"
        """,
    )
    assert result == "missing=[] isatty=False", result


def test_uvicorn_config_survives_a_headless_start(tmp_path):
    """Caly tor z main.run_app: konfiguracja serwera bez konsoli."""
    result = run_headless(
        tmp_path,
        """
        import main
        import uvicorn
        main.ensure_std_streams()
        config = uvicorn.Config(
            "main:main",
            host="127.0.0.1",
            port=8123,
            log_level="warning",
            access_log=False,
            log_config=None,
        )
        result = f"port={config.port}"
        """,
    )
    assert result == "port=8123", result


def test_existing_streams_are_left_alone(tmp_path):
    """Z konsola funkcja nie moze niczego podmieniac."""
    out = tmp_path / "result.txt"
    script = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, r"{REPO_ROOT}")
        import main
        before = (sys.stdout, sys.stderr, sys.stdin)
        main.ensure_std_streams()
        same = before == (sys.stdout, sys.stderr, sys.stdin)
        open(r"{out}", "w", encoding="utf-8").write(str(same))
        """
    )
    process = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert process.returncode == 0, process.stderr[-600:]
    assert out.read_text(encoding="utf-8") == "True"
