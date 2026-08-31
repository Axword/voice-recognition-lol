"""The kill scenario from the plan, end to end against the fake Live Client.

Game starts, the champion is detected, mappings load, the player gets a kill and
then a multikill. Nothing in that burst is allowed to disturb the state the
panel reads or the command matching the user relies on.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fake_live_client import BASE_URL, FakeLiveClient

from app.config import Settings
from controller.lol_whisp_controller import LoLVoiceController
from controller.service import get_service
from controls.mapping_manager import MappingManager
from game.ability_manager import AbilityManager
from game.lol_game_client_api import LoLGameClientAPI

DDRAGON_DIR = Path(__file__).resolve().parent / "fixtures" / "ddragon"
PLAYER = "Gracz Pierwszy"
ENEMY = "Jungler#EUNE"


@pytest.fixture
def champions(ddragon) -> dict:
    return ddragon["pl_PL"]


@pytest.fixture
def fake(champions, monkeypatch) -> FakeLiveClient:
    client = FakeLiveClient(champions, champion="Ahri", summoner_name=PLAYER)
    client.install(monkeypatch)
    return client


@pytest.fixture
def service(fake, data_managers):
    """The real VoiceService with a controller wired to the fake client."""
    voice = get_service()
    voice._settings = Settings(recognition_mode="spells", language="pl_PL")
    voice._mapping_manager = MappingManager(voice._settings)
    api = LoLGameClientAPI()
    voice._controller = LoLVoiceController(
        settings=voice._settings,
        mapping_manager=voice._mapping_manager,
        transcriber=object(),
        game_api=api,
        ability_manager=AbilityManager(api, data_manager=data_managers["pl_PL"], language="pl_PL"),
    )
    return voice


def _ability(champions: dict, champion: str, index: int) -> str:
    return champions[champion]["spells"][index]["name"]


def test_kill_scenario_keeps_the_state_consistent(service, fake, game_loop, champions):
    events: list[dict] = []
    service.set_event_sink(events.append)

    # 1. The game starts and the champion is detected.
    game_loop(service._controller)
    status = service.status()
    assert status["game_active"] is True
    assert status["champion"] == champions["Ahri"]["name"]
    assert status["mode"] == "spells"
    assert status["mappings_count"] > 0
    assert status["error"] is None

    mappings_before = dict(service.mapping_manager.champion_spell_mappings)
    assert service.mapping_manager.match_command(_ability(champions, "Ahri", 0)) == "q"

    # 2. First blood, then the kill and the multikill.
    fake.emit_first_brick(PLAYER)
    kill = fake.emit_kill(PLAYER, ENEMY, assisters=["Support Diff"])
    multi = fake.emit_multikill(PLAYER, streak=2)
    assert kill["KillerName"] == PLAYER
    assert multi["KillStreak"] == 2

    fake.roster[0]["scores"]["kills"] = 2
    fake.roster[1]["isDead"] = True

    # 3. The loop keeps running through the burst.
    game_loop(service._controller, iterations=3)

    status_after = service.status()
    assert status_after["game_active"] is True
    assert status_after["champion"] == champions["Ahri"]["name"]
    assert status_after["mappings_count"] == status["mappings_count"]
    assert service.mapping_manager.champion_spell_mappings == mappings_before

    # 4. Commands still resolve after the burst.
    for index, key in enumerate("qwer"):
        assert service.mapping_manager.match_command(_ability(champions, "Ahri", index)) == key
    assert service.mapping_manager.match_command("flash") == "d"

    # 5. The transcript path still works and reports what it heard.
    assert service.handle_transcript(_ability(champions, "Ahri", 3)) == "r"
    heard = [event for event in events if event["type"] == "heard"]
    assert heard[-1]["matched"] == "r"
    assert set(heard[-1]) == {"type", "text", "matched", "time"}


def test_status_endpoint_reports_the_live_game(service, api_client, game_loop, champions):
    game_loop(service._controller)

    response = api_client.get("/api/v1/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["game_active"] is True
    assert payload["champion"] == champions["Ahri"]["name"]
    assert payload["mappings_count"] > 0

    mappings = api_client.get("/api/v1/champions/current/mappings").json()
    assert mappings["champion"] == champions["Ahri"]["name"]
    assert mappings["mode"] == "spells"
    assert any(row["source"] == "champion" for row in mappings["mappings"])


def test_events_with_unexpected_fields_do_not_raise(service, fake, game_loop, champions):
    fake.emit_event("ChampionKill", KillerName=None, VictimName=12345, Assisters="not-a-list")
    fake.emit_event("Multikill", KillStreak="two")
    fake.emit_event("SomethingRiotAddedLastPatch", Payload={"nested": [1, 2, 3]}, Weird=None)
    fake.emit_event("ChampionKill")  # no killer, no victim at all

    game_loop(service._controller, iterations=2)

    assert service.status()["game_active"] is True
    assert service.mapping_manager.match_command(_ability(champions, "Ahri", 1)) == "w"

    payload = service._controller.game_api.session.get(f"{BASE_URL}/liveclientdata/eventdata").json()
    assert len(payload["Events"]) == 5


def test_kill_then_game_end_resets_the_mappings(service, fake, game_loop, champions):
    game_loop(service._controller)
    fake.emit_kill(PLAYER, ENEMY)
    game_loop(service._controller)
    assert service.status()["champion"] == champions["Ahri"]["name"]

    fake.end_game()
    game_loop(service._controller)

    status = service.status()
    assert status["game_active"] is False
    assert status["champion"] is None
    assert service.mapping_manager.champion_spell_mappings == {}
    assert service.mapping_manager.match_command("escape") == "escape"


def test_kill_burst_with_a_champion_swap(service, fake, game_loop, champions):
    game_loop(service._controller)
    fake.emit_kill(PLAYER, ENEMY)

    fake.set_champion("Garen")
    fake.set_summoner_name(PLAYER)
    game_loop(service._controller, iterations=2)

    assert service.status()["champion"] == champions["Garen"]["name"]
    manager = service.mapping_manager
    assert manager.match_command(_ability(champions, "Garen", 0)) == "q"
    assert manager.normalize(_ability(champions, "Ahri", 0)) not in manager.champion_spell_mappings
