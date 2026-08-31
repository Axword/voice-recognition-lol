"""Konfiguracja testow e2e audio.

Nie duplikuje tego, co robi tests/conftest.py: jesli srodowisko jest juz
ustawione (LOLVOICE_HOME, LOLVOICE_DDRAGON_FIXTURES), ten plik go nie rusza.
Dodaje tylko to, bez czego katalog e2e nie dziala samodzielnie: katalog tests
w sys.path (dla import audio_support) i sensowne wartosci domyslne.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = REPO_ROOT / "tests"

for entry in (str(REPO_ROOT), str(TESTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import audio_support  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _isolated_home(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Kieruje zapisy aplikacji do katalogu tymczasowego, gdy nikt tego nie zrobil wczesniej."""
    if os.environ.get("LOLVOICE_HOME"):
        return
    home = tmp_path_factory.mktemp("lolvoice-home")
    os.environ["LOLVOICE_HOME"] = str(home)

    from app import config, paths

    paths.refresh()

    # Modele Whispera bywaja w domyslnym katalogu uzytkownika. Podpinamy je do
    # katalogu tymczasowego, zeby test rozpoznawania nie pomijal sie tylko
    # dlatego, ze przestawilismy HOME.
    default_models = _default_models_dir()
    if default_models and default_models.is_dir():
        target = paths.MODELS_DIR
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            try:
                os.symlink(default_models, target, target_is_directory=True)
            except (OSError, NotImplementedError):
                # Symlink na Windows wymaga uprawnien, junction nie.
                try:
                    import _winapi

                    _winapi.CreateJunction(str(default_models), str(target))
                except Exception:
                    pass  # testy rozpoznawania po prostu sie pomina

    paths.ensure_dirs()
    config.reset_cache()


def _default_models_dir() -> Path | None:
    """Katalog modeli sprzed przestawienia LOLVOICE_HOME."""
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        return Path(local) / "LoLVoice" / "models" if local else None
    base = os.environ.get("XDG_DATA_HOME")
    root = Path(base) if base else Path.home() / ".local" / "share"
    return root / "LoLVoice" / "models"


@pytest.fixture(scope="session", autouse=True)
def _ddragon_fixtures() -> None:
    os.environ.setdefault("LOLVOICE_DDRAGON_FIXTURES", str(audio_support.DDRAGON_DIR))


@pytest.fixture(scope="session")
def ffmpeg_available() -> bool:
    return audio_support.ffmpeg_binary() is not None
