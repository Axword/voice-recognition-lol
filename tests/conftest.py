"""Shared fixtures.

Every test runs against its own LOLVOICE_HOME, so nothing ever touches the real
user profile. The Data Dragon fixtures are loaded once per session and reused,
because parsing 173 champions twice per test would dominate the runtime.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
DDRAGON_DIR = FIXTURES_DIR / "ddragon"
REPORTS_DIR = Path(__file__).resolve().parent / "reports"
LANGUAGES = ("pl_PL", "en_US")
TEST_TOKEN = "test-token"


def ddragon_version() -> str:
    """Patch string pinned in tests/fixtures/VERSION, also used by the CI cache key."""
    return (FIXTURES_DIR / "VERSION").read_text(encoding="utf-8").strip()


def _reset_app_state() -> None:
    """Drop every cached singleton that remembers a path or a settings object."""
    from app import config, paths
    from controller import service

    paths.refresh()
    config.reset_cache()
    service.reset_service()

    from server import api, runtime

    api._service = None
    api._service_error = None
    runtime._current = None


# --- isolation --------------------------------------------------------


@pytest.fixture(autouse=True)
def lolvoice_home(tmp_path, monkeypatch):
    """Isolated data root for a single test.

    The working directory moves too: app.config migrates legacy settings from
    relative paths (config/config.json, config.json), and the repository ships
    both of those files.
    """
    home = tmp_path / "lolvoice-home"
    home.mkdir()
    workdir = tmp_path / "cwd"
    workdir.mkdir()

    monkeypatch.setenv("LOLVOICE_HOME", str(home))
    monkeypatch.setenv("LOLVOICE_DDRAGON_FIXTURES", str(DDRAGON_DIR))
    monkeypatch.delenv("LOLVOICE_TOKEN", raising=False)
    monkeypatch.delenv("LOLVOICE_PORT", raising=False)
    monkeypatch.chdir(workdir)

    _reset_app_state()
    from app import paths

    paths.ensure_dirs()
    yield home
    _reset_app_state()


@pytest.fixture
def workdir(lolvoice_home) -> Path:
    """The temporary current working directory, where legacy config files live."""
    return Path.cwd()


# --- Data Dragon ------------------------------------------------------


@pytest.fixture(scope="session")
def ddragon() -> dict:
    """{language: {champion: data}} from the pinned Data Dragon fixtures."""
    loaded: dict[str, dict] = {}
    for language in LANGUAGES:
        payload = json.loads((DDRAGON_DIR / f"championFull.{language}.json").read_text(encoding="utf-8"))
        loaded[language] = payload.get("data", payload)
    return loaded


@pytest.fixture(scope="session")
def champion_names(ddragon) -> list[str]:
    return sorted(ddragon["en_US"].keys())


@pytest.fixture(scope="session")
def data_managers(tmp_path_factory) -> dict:
    """One LoLDataManager per language, reading the fixtures, never the network."""
    from game.lol_data_manager import LoLDataManager

    cache_root = tmp_path_factory.mktemp("ddragon-cache")
    managers = {}
    for language in LANGUAGES:
        manager = LoLDataManager(language=language, fixture_dir=DDRAGON_DIR, cache_dir=cache_root / language)
        manager.fetch_champion_data()
        managers[language] = manager
    return managers


# --- settings ---------------------------------------------------------


@pytest.fixture
def settings(lolvoice_home):
    """Factory for Settings objects, optionally persisted to the isolated home."""
    from app import config

    def make(persist: bool = False, **overrides):
        value = config.Settings(**overrides)
        if persist:
            config.save(value)
        return value

    return make


# --- HTTP -------------------------------------------------------------


@pytest.fixture
def api_app(lolvoice_home):
    from server import api

    return api.create_app(port=21999, token=TEST_TOKEN)


@pytest.fixture
def api_client(api_app):
    """Starlette TestClient with the session token already attached."""
    from fastapi.testclient import TestClient

    with TestClient(api_app) as client:
        client.headers.update({"X-Auth-Token": TEST_TOKEN})
        yield client


# --- game loop --------------------------------------------------------


@pytest.fixture
def game_loop():
    """Runs LoLVoiceController._periodic_game_state_update a fixed number of times.

    The real loop sleeps and spins in a background thread. Replacing the sleep
    lets the test drive it synchronously, one iteration at a time, with no
    timing assumptions.
    """
    from controller import lol_whisp_controller

    def pump(controller, iterations: int = 1) -> None:
        state = {"count": 0}

        def fake_sleep(_seconds: float) -> None:
            state["count"] += 1
            if state["count"] >= iterations:
                controller.is_listening = False

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(lol_whisp_controller.time, "sleep", fake_sleep)
            controller.is_listening = True
            try:
                controller._periodic_game_state_update(interval_seconds=0)
            finally:
                controller.is_listening = False

    return pump


@pytest.fixture
def reports_dir() -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR
