"""Champion detection through the Live Client Data API.

Everything runs against FakeLiveClient, so no socket is opened and no real
League client is needed. The controller game loop is driven one iteration at a
time by the game_loop fixture, which keeps the assertions free of sleeps.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pytest
import requests
from fake_live_client import BASE_URL, FakeLiveClient

from app.config import Settings
from controller.lol_whisp_controller import LoLVoiceController
from controls.mapping_manager import MappingManager
from game.ability_manager import AbilityManager
from game.lol_data_manager import LoLDataManager
from game.lol_game_client_api import LoLGameClientAPI

DDRAGON_DIR = Path(__file__).resolve().parent / "fixtures" / "ddragon"
LANGUAGES = ("pl_PL", "en_US")


@lru_cache(maxsize=4)
def _champion_data(language: str) -> dict:
    payload = json.loads((DDRAGON_DIR / f"championFull.{language}.json").read_text(encoding="utf-8"))
    return payload.get("data", payload)


def _renamed_champions(language: str) -> list[str]:
    """Champions whose in game display name is not their Data Dragon id."""
    return sorted(key for key, data in _champion_data(language).items() if key != data.get("name"))


RENAMED_CASES = [(language, key) for language in LANGUAGES for key in _renamed_champions(language)]
ALL_CHAMPION_CASES = [(language, key) for language in LANGUAGES for key in sorted(_champion_data(language))]


@pytest.fixture
def champions(ddragon) -> dict:
    return ddragon["pl_PL"]


@pytest.fixture
def fake(champions, monkeypatch) -> FakeLiveClient:
    client = FakeLiveClient(champions, champion="Ahri", summoner_name="Gracz Pierwszy")
    client.install(monkeypatch)
    return client


@pytest.fixture
def game_api(fake) -> LoLGameClientAPI:
    return LoLGameClientAPI()


@pytest.fixture
def controller(game_api, data_managers) -> LoLVoiceController:
    settings = Settings(recognition_mode="spells", language="pl_PL")
    mapping_manager = MappingManager(settings)
    ability_manager = AbilityManager(game_api, data_manager=data_managers["pl_PL"], language="pl_PL")
    return LoLVoiceController(
        settings=settings,
        mapping_manager=mapping_manager,
        transcriber=object(),
        game_api=game_api,
        ability_manager=ability_manager,
    )


def _ability_name(champions: dict, champion: str, index: int) -> str:
    return champions[champion]["spells"][index]["name"]


# --- the fake itself ---------------------------------------------------


def test_fake_serves_every_documented_endpoint(fake, game_api):
    session = game_api.session
    stats = session.get(f"{BASE_URL}/liveclientdata/gamestats").json()
    assert {"gameMode", "gameTime", "mapName"} <= set(stats)

    active = session.get(f"{BASE_URL}/liveclientdata/activeplayer").json()
    assert active["summonerName"] == "Gracz Pierwszy"
    assert set(active["abilities"]) >= {"Q", "W", "E", "R", "Passive"}

    players = session.get(f"{BASE_URL}/liveclientdata/playerlist").json()
    assert len(players) == 10
    assert len({player["championName"] for player in players}) == 10
    for player in players:
        assert {"summonerName", "championName", "team", "scores"} <= set(player)

    abilities = session.get(f"{BASE_URL}/liveclientdata/activeplayerabilities").json()
    for key in ("Q", "W", "E", "R"):
        assert abilities[key]["displayName"]

    events = session.get(f"{BASE_URL}/liveclientdata/eventdata").json()
    assert events["Events"][0]["EventName"] == "GameStart"


def test_fake_event_timeline_shape(fake):
    fake.emit_first_brick("Gracz Pierwszy")
    fake.emit_kill("Gracz Pierwszy", "Jungler#EUNE", assisters=["Support Diff"])
    fake.emit_multikill("Gracz Pierwszy", streak=2)

    names = [event["EventName"] for event in fake.eventdata()["Events"]]
    assert names == ["GameStart", "FirstBrick", "ChampionKill", "Multikill"]

    kill = fake.eventdata()["Events"][2]
    assert kill["KillerName"] == "Gracz Pierwszy"
    assert kill["VictimName"] == "Jungler#EUNE"
    assert kill["Assisters"] == ["Support Diff"]
    assert isinstance(kill["EventID"], int)
    assert isinstance(kill["EventTime"], float)


# --- detection ---------------------------------------------------------


def test_active_player_is_resolved_out_of_the_player_list(fake, game_api, champions):
    assert game_api.is_game_active() is True
    assert game_api.get_active_player_name() == "Gracz Pierwszy"
    assert game_api.get_current_champion() == champions["Ahri"]["name"]


def test_detection_picks_the_right_player_when_not_first(champions, monkeypatch):
    client = FakeLiveClient(champions, champion="Garen", summoner_name="Ostatni Smok", active_index=8)
    client.install(monkeypatch)
    api = LoLGameClientAPI()
    assert api.get_active_player_name() == "Ostatni Smok"
    assert api.get_current_champion() == client.roster[8]["championName"]


def test_mappings_load_on_detection(controller, game_loop, champions):
    game_loop(controller)
    assert controller.game_active is True
    assert controller.current_champion_name == champions["Ahri"]["name"]

    manager = controller.mapping_manager
    assert manager.champion_spell_mappings
    for index, key in enumerate("qwer"):
        assert manager.match_command(_ability_name(champions, "Ahri", index)) == key


def test_mappings_rebuild_when_the_champion_changes(controller, fake, game_loop, champions):
    game_loop(controller)
    assert controller.mapping_manager.match_command(_ability_name(champions, "Ahri", 0)) == "q"

    fake.set_champion("Garen")
    fake.set_summoner_name("Gracz Pierwszy")
    game_loop(controller)

    assert controller.current_champion_name == champions["Garen"]["name"]
    assert controller.mapping_manager.match_command(_ability_name(champions, "Garen", 3)) == "r"
    assert controller.mapping_manager.command_cache != {"stale": None}


def test_variable_abilities_are_picked_up_without_a_champion_change(controller, fake, game_loop):
    """Hwei style: the champion stays, the Live Client ability names change."""
    game_loop(controller)
    first = dict(controller.mapping_manager.champion_spell_mappings)

    fake.set_abilities(
        {
            "Passive": {"displayName": "Znak Malarza"},
            "Q": {"abilityLevel": 1, "displayName": "Niszczycielski Ogień", "id": "HweiQQ"},
            "W": {"abilityLevel": 1, "displayName": "Przemijający Przepływ", "id": "HweiWQ"},
            "E": {"abilityLevel": 1, "displayName": "Ponure Oblicze", "id": "HweiEQ"},
            "R": {"abilityLevel": 1, "displayName": "Spirala Rozpaczy", "id": "HweiR"},
        }
    )
    game_loop(controller)

    manager = controller.mapping_manager
    assert manager.champion_spell_mappings != first
    assert manager.match_command("Niszczycielski Ogień") == "q"
    assert manager.match_command("Spirala Rozpaczy") == "r"


def test_mappings_reset_when_the_game_ends(controller, fake, game_loop, champions):
    game_loop(controller)
    assert controller.current_champion_name is not None

    fake.end_game()
    game_loop(controller)

    assert controller.game_active is False
    assert controller.current_champion_name is None
    assert controller.mapping_manager.champion_spell_mappings == {}
    assert controller.mapping_manager.match_command("flash") == "d"


def test_status_reflects_the_detected_champion(controller, game_loop, champions):
    game_loop(controller)
    status = controller.get_status()
    assert status["champion"] == champions["Ahri"]["name"]
    assert status["game_active"] is True
    assert status["mappings_count"] > 0
    assert status["language"] == "pl_PL"
    assert status["last_update"]


# --- hostile input ------------------------------------------------------


def test_missing_summoner_name_is_survived(controller, fake, game_loop):
    payload = fake.activeplayer()
    payload.pop("summonerName")
    fake.activeplayer = lambda: payload  # type: ignore[method-assign]

    game_loop(controller)
    assert controller.game_active is True
    assert controller.current_champion_name is None


def test_player_missing_from_the_player_list(controller, fake, game_loop):
    fake.set_summoner_name("Ktos Zupelnie Inny")
    fake.player_overrides = [
        {"summonerName": "Kto Inny", "championName": "Garen"},
        {"championName": "Ahri"},
    ]
    game_loop(controller)
    assert controller.current_champion_name is None


@pytest.mark.parametrize(
    "name",
    [
        "Zażółć Gęślą Jaźń",
        "梅西#KR1",
        "gg wp \U0001f608\U0001f3ae",  # emoji, escaped so the source stays plain text
        "\U0001f9d9‍♂️ Mid",  # emoji with a zero width joiner
        "  ",
        "a" * 300,
        "<script>alert(1)</script>",
        "Ⓤⓝⓘⓒⓞⓓⓔ",
    ],
)
def test_unusual_player_names_do_not_crash(champions, monkeypatch, data_managers, name, game_loop):
    client = FakeLiveClient(champions, champion="Ahri", summoner_name=name)
    client.install(monkeypatch)
    api = LoLGameClientAPI()
    settings = Settings(recognition_mode="spells", language="pl_PL")
    controller = LoLVoiceController(
        settings=settings,
        mapping_manager=MappingManager(settings),
        transcriber=object(),
        game_api=api,
        ability_manager=AbilityManager(api, data_manager=data_managers["pl_PL"], language="pl_PL"),
    )

    game_loop(controller)
    assert api.get_active_player_name() == name
    assert controller.current_champion_name == champions["Ahri"]["name"]
    assert controller.mapping_manager.match_command(_ability_name(champions, "Ahri", 0)) == "q"


def test_empty_ability_payload_falls_back_to_data_dragon(champions, monkeypatch, data_managers):
    client = FakeLiveClient(champions, champion="Ahri")
    client.set_abilities({})
    client.install(monkeypatch)
    api = LoLGameClientAPI()
    manager = AbilityManager(api, data_manager=data_managers["pl_PL"], language="pl_PL")

    mappings = manager.create_voice_mappings_from_api("Ahri")
    assert mappings
    assert set(mappings.values()) <= {"q", "w", "e", "r"}
    assert manager.display_mappings["Q"]["name"] == _ability_name(champions, "Ahri", 0)


def test_ability_payload_without_display_names(champions, monkeypatch, data_managers):
    client = FakeLiveClient(champions, champion="Ahri")
    client.set_abilities({"Q": {}, "W": {"displayName": ""}, "E": None, "R": {"displayName": None}})
    client.install(monkeypatch)
    api = LoLGameClientAPI()
    manager = AbilityManager(api, data_manager=data_managers["pl_PL"], language="pl_PL")

    mappings = manager.create_voice_mappings_from_api("Ahri")
    assert mappings  # Data Dragon fallback keeps the user with some mapping.


def test_http_404_is_treated_as_no_game(controller, fake, game_loop):
    fake.mode = "http_404"
    assert controller.game_api.is_game_active() is False
    assert controller.game_api.get_current_champion() is None
    game_loop(controller)
    assert controller.game_active is False
    assert controller.current_champion_name is None


def test_connection_refused_is_treated_as_no_game(controller, fake, game_loop):
    fake.mode = "offline"
    assert controller.game_api.is_game_active() is False
    assert controller.game_api.get_active_player_name() is None
    assert controller.game_api.get_all_players() is None
    assert controller.game_api.get_active_player_abilities() is None
    game_loop(controller)
    assert controller.game_active is False


def test_malformed_json_does_not_kill_the_game_loop(controller, fake, game_loop):
    fake.mode = "malformed"
    with pytest.raises(json.JSONDecodeError):
        controller.game_api.get_active_player_name()
    game_loop(controller)
    assert controller.current_champion_name is None


def test_blocked_outbound_request(fake):
    session = requests.Session()
    with pytest.raises(requests.ConnectionError):
        session.get("https://ddragon.leagueoflegends.com/api/versions.json")


# --- display name against Data Dragon id ----------------------------------
#
# The Live Client reports the name the player sees ("Wukong", "Kha'Zix",
# "Nunu & Willump"), Data Dragon keys champions by id ("MonkeyKing", "Khazix",
# "Nunu"). LoLDataManager.resolve_champion_key bridges the two, so the fallback
# path works for every champion, not only the ones whose names happen to match.


@pytest.mark.parametrize(("language", "champion_key"), RENAMED_CASES, ids=lambda value: value)
def test_data_dragon_fallback_for_champions_whose_display_name_differs(
    language, champion_key, monkeypatch, data_managers
):
    champion_pool = _champion_data(language)
    display_name = champion_pool[champion_key]["name"]
    expected = {
        key: champion_pool[champion_key]["spells"][index]["name"]
        for index, key in enumerate(("Q", "W", "E", "R"))
    }

    client = FakeLiveClient(champion_pool, champion=champion_key)
    client.set_abilities({})  # Live Client silent, exactly the case the fallback is for
    client.install(monkeypatch)
    api = LoLGameClientAPI()
    manager = AbilityManager(api, data_manager=data_managers[language], language=language)

    assert api.get_current_champion() == display_name
    assert display_name != champion_key

    mappings = manager.create_voice_mappings_from_api(display_name)
    assert mappings
    for key, ability_name in expected.items():
        assert manager.display_mappings[key]["name"] == ability_name
        assert mappings[manager.normalize(ability_name)] == key.lower()


@pytest.mark.parametrize(
    ("display_name", "expected_key"),
    [
        ("Wukong", "MonkeyKing"),
        ("Kha'Zix", "Khazix"),
        ("Dr. Mundo", "DrMundo"),
        ("Nunu & Willump", "Nunu"),
        ("Aurelion Sol", "AurelionSol"),
        ("Renata Glasc", "Renata"),
        ("MonkeyKing", "MonkeyKing"),
    ],
)
def test_resolve_champion_key_maps_display_names_to_ids(display_name, expected_key, data_managers):
    manager: LoLDataManager = data_managers["pl_PL"]
    assert manager.resolve_champion_key(display_name) == expected_key
    assert manager.get_champion_abilities(display_name)["Q"]


@pytest.mark.parametrize(("language", "champion_key"), ALL_CHAMPION_CASES, ids=lambda value: value)
def test_every_champion_resolves_to_itself_from_its_display_name(language, champion_key, data_managers):
    """The prefix rule must not produce false matches for any of the 173 ids."""
    manager: LoLDataManager = data_managers[language]
    display_name = _champion_data(language)[champion_key]["name"]
    assert manager.resolve_champion_key(display_name) == champion_key
    assert manager.resolve_champion_key(champion_key) == champion_key


def test_resolve_champion_key_rejects_what_is_not_a_champion(data_managers):
    manager: LoLDataManager = data_managers["pl_PL"]
    assert manager.resolve_champion_key("") is None
    assert manager.resolve_champion_key("Nie Ma Takiego Bohatera") is None
    assert manager.get_champion_abilities("Nie Ma Takiego Bohatera") == {}
    assert manager.get_champion_sub_abilities("Nie Ma Takiego Bohatera") == {}


def test_sub_abilities_resolve_through_the_display_name(data_managers):
    manager: LoLDataManager = data_managers["pl_PL"]
    by_id = manager.get_champion_sub_abilities("Hwei")
    by_display = manager.get_champion_sub_abilities(_champion_data("pl_PL")["Hwei"]["name"])
    assert by_id == by_display
    assert any(by_id[key] for key in ("Q", "W", "E"))
