"""REST API against the contract in docs/CONTRACTS.md.

Everything runs on the Starlette TestClient. No socket leaves the process: the
voice service gets a dummy controller instead of a microphone, and the update
check is answered by a stubbed GitHub.
"""

from __future__ import annotations

import io
import json
import sys
import zipfile

import pytest
import requests
from fastapi.testclient import TestClient

from app import config, paths
from server import api as server_api

TOKEN = "test-token"
API = "/api/v1"

SETTINGS_KEYS = {
    "recognition_mode",
    "spell_sensitivity",
    "language",
    "merge_command_languages",
    "combo_enabled",
    "ui_language",
    "flash_key",
    "summoner2_key",
    "engine_id",
    "audio_device",
    "start_with_windows",
    "start_listening_on_launch",
    "theme",
    "skipped_version",
    "check_updates",
}

STATUS_KEYS = {
    "listening",
    "game_active",
    "champion",
    "mode",
    "engine_id",
    "engine_name",
    "version",
    "mappings_count",
    "last_command",
    "last_heard",
    "update_available",
}


class DummyController:
    """Stands in for LoLVoiceController, so nothing opens an audio stream."""

    def __init__(self) -> None:
        self.is_listening = False
        self.game_active = False
        self.current_champion_name = None
        self.transcriber = object()
        self.settings = None

    def start_listening(self) -> bool:
        self.is_listening = True
        return True

    def stop_listening(self) -> None:
        self.is_listening = False


@pytest.fixture
def dummy_service(lolvoice_home):
    from controller.service import get_service

    service = get_service()
    service._controller = DummyController()
    return service


# --- auth ---------------------------------------------------------------


def test_missing_token_is_rejected(api_app):
    with TestClient(api_app) as client:
        assert client.get(f"{API}/status").status_code == 401


def test_wrong_token_is_rejected(api_app):
    with TestClient(api_app) as client:
        response = client.get(f"{API}/status", headers={"X-Auth-Token": "nope"})
        assert response.status_code == 401
        assert response.json()["detail"] == "Unauthorized"


def test_valid_token_in_header_and_query(api_app):
    with TestClient(api_app) as client:
        assert client.get(f"{API}/status", headers={"X-Auth-Token": TOKEN}).status_code == 200
        assert client.get(f"{API}/status", params={"token": TOKEN}).status_code == 200


def test_non_loopback_origin_is_forbidden(api_app):
    with TestClient(api_app, client=("203.0.113.7", 4444)) as client:
        response = client.get(f"{API}/status", headers={"X-Auth-Token": TOKEN})
        assert response.status_code == 403
        assert response.json()["detail"] == "Forbidden"


def test_panel_index_is_served_without_a_token(api_app):
    with TestClient(api_app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert TOKEN in response.text
        assert "window.__LOLVOICE__" in response.text


# --- status and listening -------------------------------------------------


def test_status_shape(api_client, dummy_service):
    payload = api_client.get(f"{API}/status").json()
    assert set(payload) >= STATUS_KEYS
    assert payload["mode"] == config.load().recognition_mode
    assert isinstance(payload["mappings_count"], int)
    assert isinstance(payload["listening"], bool)
    assert payload["version"]


def test_listening_start_and_stop(api_client, dummy_service):
    started = api_client.post(f"{API}/listening/start").json()
    assert set(started) >= {"listening"}
    assert started["listening"] is True
    assert api_client.get(f"{API}/status").json()["listening"] is True

    stopped = api_client.post(f"{API}/listening/stop").json()
    assert stopped["listening"] is False
    assert api_client.get(f"{API}/status").json()["listening"] is False


def test_listening_start_reports_a_failure_instead_of_raising(api_client, dummy_service):
    def boom() -> bool:
        raise RuntimeError("no audio device")

    dummy_service._controller.start_listening = boom
    payload = api_client.post(f"{API}/listening/start").json()
    assert payload["listening"] is False


# --- settings -------------------------------------------------------------


def test_settings_get_returns_the_full_model(api_client):
    payload = api_client.get(f"{API}/settings").json()
    assert set(payload) == SETTINGS_KEYS


def test_settings_put_applies_a_partial_patch_and_persists(api_client, dummy_service):
    before = api_client.get(f"{API}/settings").json()

    response = api_client.put(f"{API}/settings", json={"spell_sensitivity": "high", "flash_key": "f"})
    assert response.status_code == 200
    updated = response.json()
    assert set(updated) == SETTINGS_KEYS
    assert updated["spell_sensitivity"] == "high"
    assert updated["flash_key"] == "f"
    assert updated["language"] == before["language"]
    assert updated["engine_id"] == before["engine_id"]

    on_disk = json.loads(paths.CONFIG_FILE.read_text(encoding="utf-8"))
    assert on_disk["spell_sensitivity"] == "high"
    assert on_disk["flash_key"] == "f"

    config.reset_cache()
    assert config.load().flash_key == "f"


def test_settings_put_reaches_the_service(api_client, dummy_service):
    api_client.put(f"{API}/settings", json={"recognition_mode": "letters"})
    assert dummy_service.mapping_manager.mode == "letters"
    assert api_client.get(f"{API}/status").json()["mode"] == "letters"


@pytest.mark.parametrize(
    "patch",
    [
        {"recognition_mode": "telepathy"},
        {"spell_sensitivity": "maximum"},
        {"theme": "neon"},
        {"check_updates": "maybe"},
    ],
)
def test_settings_put_rejects_an_invalid_value(api_client, patch):
    """An unknown value is a client error, and nothing is written."""
    before = api_client.get(f"{API}/settings").json()
    on_disk_before = paths.CONFIG_FILE.read_text(encoding="utf-8")

    response = api_client.put(f"{API}/settings", json=patch)
    assert response.status_code == 422

    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert detail
    field = next(iter(patch))
    assert any(field in map(str, entry.get("loc", ())) for entry in detail)
    assert all("url" not in entry for entry in detail)

    assert api_client.get(f"{API}/settings").json() == before
    assert paths.CONFIG_FILE.read_text(encoding="utf-8") == on_disk_before

    config.reset_cache()
    assert config.load().model_dump() == before


def test_settings_put_rejects_an_invalid_value_without_touching_the_service(api_client, dummy_service):
    before_mode = dummy_service.mapping_manager.mode
    assert api_client.put(f"{API}/settings", json={"recognition_mode": "telepathy"}).status_code == 422
    assert dummy_service.mapping_manager.mode == before_mode


def test_settings_put_with_an_empty_body_changes_nothing(api_client):
    before = api_client.get(f"{API}/settings").json()
    assert api_client.put(f"{API}/settings", json={}).json() == before


# --- engines ---------------------------------------------------------------


def test_engines_report_install_state(api_client):
    payload = api_client.get(f"{API}/engines").json()
    assert set(payload) == {"engines"}
    assert payload["engines"]
    for engine in payload["engines"]:
        assert {"id", "name", "installed", "active", "size_bytes", "requires_cuda"} <= set(engine)
        assert isinstance(engine["installed"], bool)
        assert isinstance(engine["active"], bool)
    assert sum(1 for engine in payload["engines"] if engine["active"]) <= 1


def test_engine_activate_updates_the_settings(api_client, dummy_service):
    engines = api_client.get(f"{API}/engines").json()["engines"]
    target = engines[-1]["id"]
    payload = api_client.post(f"{API}/engines/{target}/activate").json()
    assert payload == {"engine_id": target}
    assert config.load().engine_id == target


def test_engine_cancel(api_client):
    assert api_client.post(f"{API}/engines/whisper-tiny/cancel").json() == {"cancelled": True}


def test_engine_download_starts_a_worker(api_client, monkeypatch):
    from app import engines

    calls: list[str] = []
    monkeypatch.setattr(engines, "download", lambda engine_id, progress=None: calls.append(engine_id))
    payload = api_client.post(f"{API}/engines/whisper-tiny/download").json()
    assert payload == {"started": True}


# --- audio ------------------------------------------------------------------


def test_audio_devices_shape(api_client, dummy_service, monkeypatch):
    monkeypatch.setattr(
        type(dummy_service), "list_audio_devices", lambda _self: [{"id": "1", "name": "Mic", "default": True}]
    )
    payload = api_client.get(f"{API}/audio/devices").json()
    assert set(payload) >= {"devices"}
    for device in payload["devices"]:
        assert set(device) == {"id", "name", "default"}


def test_audio_devices_without_hardware(api_client, dummy_service):
    payload = api_client.get(f"{API}/audio/devices").json()
    assert isinstance(payload["devices"], list)


def test_audio_test_shape(api_client, dummy_service, monkeypatch):
    monkeypatch.setattr(
        type(dummy_service), "test_microphone", lambda _self, seconds=3: {"level": 0.25, "transcript": "flash"}
    )
    payload = api_client.post(f"{API}/audio/test", json={"seconds": 1}).json()
    assert payload == {"level": 0.25, "transcript": "flash"}


def test_audio_test_survives_a_missing_microphone(api_client, dummy_service, monkeypatch):
    sounddevice = pytest.importorskip("sounddevice")

    def no_input_device(*_args, **_kwargs):
        raise RuntimeError("Error querying device: no input device available")

    monkeypatch.setattr(sounddevice, "rec", no_input_device)
    payload = api_client.post(f"{API}/audio/test", json={"seconds": 1}).json()
    assert set(payload) >= {"level", "transcript"}
    assert payload["level"] == 0.0
    assert payload["transcript"] == ""


# --- mappings ----------------------------------------------------------------


def test_current_mappings_shape(api_client, dummy_service):
    payload = api_client.get(f"{API}/champions/current/mappings").json()
    assert {"champion", "mode", "mappings"} <= set(payload)
    assert payload["mappings"]
    for row in payload["mappings"]:
        assert set(row) == {"phrase", "key", "source"}
        assert row["source"] in {"champion", "letter", "extra"}


# --- logs ---------------------------------------------------------------------


def test_logs_listing_shape(api_client):
    from app import logging_setup

    logging_setup.get_logger("test").warning("something happened")
    payload = api_client.get(f"{API}/logs", params={"limit": 10}).json()
    assert set(payload) == {"files", "tail"}
    assert isinstance(payload["files"], list)
    for entry in payload["files"]:
        assert set(entry) == {"name", "size", "modified"}
    for line in payload["tail"]:
        assert set(line) == {"time", "level", "name", "message"}


def test_logs_download_returns_a_zip_with_system_info(api_client):
    (paths.LOG_DIR / "lolvoice.log").write_text("hello\n", encoding="utf-8")

    response = api_client.get(f"{API}/logs/download")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "attachment" in response.headers["content-disposition"]
    assert response.content

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert "system-info.txt" in names
        assert "logs/lolvoice.log" in names
        info = archive.read("system-info.txt").decode("utf-8")
        assert "app_version:" in info
        assert str(paths.DATA_DIR) in info


# --- updates --------------------------------------------------------------------


RELEASE = {
    "tag_name": "v9.9.9",
    "assets": [
        {"name": "Setup.exe", "browser_download_url": "https://example.invalid/Setup.exe"},
        {"name": "latest.json", "browser_download_url": "https://example.invalid/latest.json"},
    ],
}
MANIFEST = {
    "version": "9.9.9",
    "url": "https://example.invalid/LoLVoiceSetup-9.9.9.exe",
    "sha256": "0" * 64,
    "notes": "Nowa wersja",
}


class _StubResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        return None


@pytest.fixture
def github(monkeypatch):
    """Answers the two GitHub calls the updater makes. Nothing hits the network."""
    seen: list[str] = []

    def fake_get(url, **_kwargs):
        seen.append(url)
        if url.endswith("latest.json"):
            return _StubResponse(MANIFEST)
        if "api.github.com" in url:
            return _StubResponse(RELEASE)
        raise requests.ConnectionError(f"Blocked in tests: {url}")

    monkeypatch.setattr(requests, "get", fake_get)
    return seen


def test_update_check_against_a_stubbed_github(api_client, github):
    payload = api_client.get(f"{API}/update/check", params={"force": "true", "token": TOKEN}).json()
    assert set(payload) == {"current", "latest", "available", "url", "notes"}
    assert payload["latest"] == "9.9.9"
    assert payload["available"] is True
    assert payload["url"] == MANIFEST["url"]
    assert payload["notes"] == "Nowa wersja"
    assert any("api.github.com" in url for url in github)


def test_update_check_is_cached(api_client, github):
    api_client.get(f"{API}/update/check", params={"force": "true", "token": TOKEN})
    calls = len(github)
    payload = api_client.get(f"{API}/update/check", params={"token": TOKEN}).json()
    assert len(github) == calls
    assert payload["latest"] == "9.9.9"
    assert api_client.get(f"{API}/status").json()["update_available"] is True


def test_update_check_survives_an_unreachable_github(api_client, monkeypatch):
    def fake_get(url, **_kwargs):
        raise requests.ConnectionError("no route to host")

    monkeypatch.setattr(requests, "get", fake_get)
    payload = api_client.get(f"{API}/update/check", params={"force": "true", "token": TOKEN}).json()
    assert payload["available"] is False
    assert payload["latest"] is None


def test_update_check_honours_a_skipped_version(api_client, github):
    api_client.put(f"{API}/settings", json={"skipped_version": "9.9.9"})
    payload = api_client.get(f"{API}/update/check", params={"force": "true", "token": TOKEN}).json()
    assert payload["latest"] == "9.9.9"
    assert payload["available"] is False


def test_update_install_does_not_start_without_a_real_installer(api_client, github):
    payload = api_client.post(f"{API}/update/install").json()
    assert set(payload) >= {"started"}
    assert payload["started"] is False
    if sys.platform == "win32":
        # Na Windows przechodzi do pobierania, ktore conftest blokuje.
        assert payload["reason"] == "download_failed"
    else:
        assert payload["reason"] == "unsupported_platform"


# --- quit -------------------------------------------------------------------------


def test_quit_calls_the_callback(lolvoice_home):
    called: list[bool] = []
    app = server_api.create_app(port=21999, token=TOKEN, on_quit=lambda: called.append(True))
    with TestClient(app) as client:
        client.headers.update({"X-Auth-Token": TOKEN})
        assert client.post(f"{API}/app/quit").json() == {"ok": True}
