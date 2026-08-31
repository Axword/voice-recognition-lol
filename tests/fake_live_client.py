"""In memory stand-in for the Riot Live Client Data API.

Payload shapes follow the real endpoints on https://127.0.0.1:2999, because
game/lol_game_client_api.py and game/ability_manager.py read those exact field
names (summonerName, championName, abilities keyed Q/W/E/R with displayName).
Ability names come from the pinned Data Dragon fixtures, so a fake match looks
like a real one for every one of the 173 champions.

Usage:

    fake = FakeLiveClient(ddragon["pl_PL"], champion="Ahri")
    fake.install(monkeypatch)
    api = LoLGameClientAPI()
    assert api.get_current_champion() == "Ahri"
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

import requests

BASE_URL = "https://127.0.0.1:2999"
LIVE_PREFIX = "/liveclientdata"
ABILITY_KEYS = ("Q", "W", "E", "R")

# Ten summoner names, deliberately mixed: plain ASCII, Polish diacritics,
# a riot id with a tag line and a name with a space.
DEFAULT_NAMES = (
    "Gracz Pierwszy",
    "Bot Lane Enjoyer",
    "Zrodlo Prawdy",
    "Malinowy Krolik",
    "Jungler#EUNE",
    "Nocny Marek",
    "Support Diff",
    "Szybki Wilk",
    "Ostatni Smok",
    "Zimny Prysznic",
)

TEAMS = ("ORDER",) * 5 + ("CHAOS",) * 5
POSITIONS = ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY") * 2


class FakeResponse:
    """The slice of requests.Response that LoLGameClientAPI actually uses."""

    def __init__(self, status_code: int, payload: Any = None, body: str | None = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = body if body is not None else json.dumps(payload, ensure_ascii=False)
        self.content = self.text.encode("utf-8")

    def json(self) -> Any:
        if self._payload is None:
            raise json.JSONDecodeError("Expecting value", self.text, 0)
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} for url", response=self)


class FakeLiveClient:
    """A whole match: ten players, live abilities and an event timeline."""

    def __init__(
        self,
        champions: dict,
        champion: str = "Ahri",
        summoner_name: str = "Gracz Pierwszy",
        active_index: int = 0,
    ) -> None:
        self.champions = champions
        self.summoner_name = summoner_name
        self.active_index = active_index
        self.game_time = 0.0
        self.running = True
        self.mode = "ok"  # ok | offline | http_404 | malformed | empty_abilities
        self.abilities_override: dict | None = None
        self.player_overrides: list[dict] | None = None
        self.events: list[dict] = []
        self._event_id = 0
        self.requests_seen: list[str] = []

        self.roster = self._build_roster(champion)
        self.champion = champion
        self.emit_game_start()

    # --- match construction -------------------------------------------

    def _champion_pool(self, champion: str) -> list[str]:
        names = [name for name in self.champions if name != champion]
        names.sort()
        return [champion, *names[:9]]

    def _build_roster(self, champion: str) -> list[dict]:
        pool = self._champion_pool(champion)
        roster = []
        for index, champion_name in enumerate(pool):
            summoner = self.summoner_name if index == self.active_index else DEFAULT_NAMES[index]
            roster.append(
                {
                    "championName": self._display_name(champion_name),
                    "rawChampionName": f"game_character_displayname_{champion_name}",
                    "isBot": False,
                    "isDead": False,
                    "items": [],
                    "level": 1,
                    "position": POSITIONS[index],
                    "respawnTimer": 0.0,
                    "runes": {"keystone": {"displayName": "Elektrokuracja", "id": 8112}},
                    "scores": {"assists": 0, "creepScore": 0, "deaths": 0, "kills": 0, "wardScore": 0.0},
                    "skinID": 0,
                    "summonerName": summoner,
                    "summonerSpells": {
                        "summonerSpellOne": {"displayName": "Błysk", "rawDisplayName": "SummonerFlash"},
                        "summonerSpellTwo": {"displayName": "Podpalenie", "rawDisplayName": "SummonerDot"},
                    },
                    "team": TEAMS[index],
                }
            )
        return roster

    def _display_name(self, champion_key: str) -> str:
        data = self.champions.get(champion_key) or {}
        return data.get("name") or champion_key

    def _spells(self, champion_key: str) -> list[dict]:
        data = self.champions.get(champion_key) or {}
        return list(data.get("spells") or [])

    # --- state helpers -------------------------------------------------

    @property
    def active_player(self) -> dict:
        return self.roster[self.active_index]

    def set_champion(self, champion: str) -> None:
        """Swap the champion the active player is on and rebuild the roster."""
        self.champion = champion
        self.roster = self._build_roster(champion)
        self.abilities_override = None

    def set_abilities(self, abilities: dict | None) -> None:
        """Force the /activeplayerabilities payload, for Hwei-style variable spells."""
        self.abilities_override = abilities

    def set_summoner_name(self, name: str) -> None:
        self.summoner_name = name
        self.roster[self.active_index]["summonerName"] = name

    def end_game(self) -> None:
        """The client stops answering, exactly like a finished match."""
        self.running = False
        self.emit_event("GameEnd", Result="Win")

    def start_game(self) -> None:
        self.running = True

    # --- events ---------------------------------------------------------

    def emit_event(self, name: str, **fields: Any) -> dict:
        event = {"EventID": self._event_id, "EventName": name, "EventTime": round(self.game_time, 3)}
        event.update(fields)
        self._event_id += 1
        self.events.append(event)
        self.game_time += 1.0
        return event

    def emit_game_start(self) -> dict:
        return self.emit_event("GameStart")

    def emit_first_brick(self, killer: str | None = None) -> dict:
        return self.emit_event("FirstBrick", KillerName=killer or self.summoner_name)

    def emit_kill(self, killer: str, victim: str, assisters: list[str] | None = None) -> dict:
        return self.emit_event(
            "ChampionKill", KillerName=killer, VictimName=victim, Assisters=list(assisters or [])
        )

    def emit_multikill(self, killer: str, streak: int = 2) -> dict:
        return self.emit_event("Multikill", KillerName=killer, KillStreak=streak)

    # --- payloads -------------------------------------------------------

    def gamestats(self) -> dict:
        return {
            "gameMode": "CLASSIC",
            "gameTime": round(self.game_time, 3),
            "mapName": "Map11",
            "mapNumber": 11,
            "mapTerrain": "Default",
        }

    def abilities(self) -> dict:
        if self.abilities_override is not None:
            return self.abilities_override
        if self.mode == "empty_abilities":
            return {}
        spells = self._spells(self.champion)
        data = self.champions.get(self.champion) or {}
        payload: dict[str, Any] = {
            "Passive": {
                "displayName": (data.get("passive") or {}).get("name", ""),
                "id": f"{self.champion}Passive",
                "rawDescription": "",
                "rawDisplayName": "",
            }
        }
        for index, key in enumerate(ABILITY_KEYS):
            if index >= len(spells):
                continue
            spell = spells[index]
            payload[key] = {
                "abilityLevel": 1,
                "displayName": spell.get("name", ""),
                "id": spell.get("id", f"{self.champion}{key}"),
                "rawDescription": f"GeneratedTip_Spell_{spell.get('id', key)}_Description",
                "rawDisplayName": f"generatedtip_spell_{spell.get('id', key)}_displayname",
            }
        return payload

    def activeplayer(self) -> dict:
        return {
            "abilities": self.abilities(),
            "championStats": {"currentHealth": 640.0, "maxHealth": 640.0, "abilityPower": 0.0},
            "currentGold": 500.0,
            "fullRunes": {"keystone": {"displayName": "Elektrokuracja", "id": 8112}},
            "level": 1,
            "summonerName": self.summoner_name,
            "teamRelativeColors": True,
        }

    def playerlist(self) -> list[dict]:
        if self.player_overrides is not None:
            return self.player_overrides
        return self.roster

    def eventdata(self) -> dict:
        return {"Events": list(self.events)}

    # --- routing ---------------------------------------------------------

    ROUTES: ClassVar[dict[str, str]] = {
        f"{LIVE_PREFIX}/gamestats": "gamestats",
        f"{LIVE_PREFIX}/activeplayer": "activeplayer",
        f"{LIVE_PREFIX}/activeplayername": "summoner_name",
        f"{LIVE_PREFIX}/activeplayerabilities": "abilities",
        f"{LIVE_PREFIX}/playerlist": "playerlist",
        f"{LIVE_PREFIX}/eventdata": "eventdata",
    }

    def handle(self, url: str) -> FakeResponse:
        """Answer one GET the way the real client would."""
        path = url.replace(BASE_URL, "") or "/"
        path = path.split("?")[0]
        self.requests_seen.append(path)

        if self.mode == "offline" or not self.running:
            raise requests.ConnectionError(f"Connection refused for {url}")
        if self.mode == "http_404":
            return FakeResponse(404, {"errorCode": "RESOURCE_NOT_FOUND", "message": "Not found"})
        if self.mode == "malformed":
            return FakeResponse(200, None, body="<html>not json</html>")

        handler = self.ROUTES.get(path)
        if handler is None:
            return FakeResponse(404, {"errorCode": "RESOURCE_NOT_FOUND", "message": path})
        value = getattr(self, handler)
        payload = value() if callable(value) else value
        return FakeResponse(200, payload)

    # --- installation -----------------------------------------------------

    def install(self, monkeypatch) -> FakeLiveClient:
        """Point requests.Session.get at this fake, so no socket is opened."""

        def fake_get(_session, url, *_args, **_kwargs):
            if not str(url).startswith(BASE_URL):
                raise requests.ConnectionError(f"Blocked in tests: {url}")
            return self.handle(str(url))

        monkeypatch.setattr(requests.Session, "get", fake_get)
        return self
