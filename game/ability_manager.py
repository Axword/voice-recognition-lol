"""Mapowania glosowe umiejetnosci aktualnego bohatera.

Zrodlo pierwsze to Live Client Data API, bo zna warianty umiejetnosci w trakcie
gry. Gdy endpoint milczy (stary klient, gra w trakcie ladowania), spadamy na
nazwy z Data Dragon, zeby uzytkownik nie zostal bez zadnego mapowania.
"""

from __future__ import annotations

import re

from app import config
from app.logging_setup import get_logger
from game.lol_data_manager import LoLDataManager
from game.lol_game_client_api import LoLGameClientAPI

log = get_logger("abilities")


class AbilityManager:
    def __init__(
        self,
        game_api: LoLGameClientAPI,
        data_manager: LoLDataManager | None = None,
        language: str | None = None,
    ) -> None:
        self.game_api = game_api
        self.language = language or config.load().language
        self._data_manager = data_manager
        self.keybinds = {"Q": "q", "W": "w", "E": "e", "R": "r"}
        self._PL_TRANSLATION = str.maketrans(
            {"ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n", "ó": "o", "ś": "s", "ź": "z", "ż": "z"}
        )
        self.current_abilities: dict[str, dict[str, str]] = {}
        self.voice_mappings: dict[str, str] = {}
        self.display_mappings: dict[str, dict[str, str]] = {}

    @property
    def data_manager(self) -> LoLDataManager:
        """Data Dragon tworzony leniwie, zeby konstruktor nic nie pobieral."""
        if self._data_manager is None:
            self._data_manager = LoLDataManager(language=self.language)
        return self._data_manager

    def set_language(self, language: str) -> None:
        """Przelacza locale nazw umiejetnosci bez restartu."""
        if language == self.language:
            return
        self.language = language
        if self._data_manager is not None:
            self._data_manager.change_language(language)
        self.current_abilities = {}
        self.voice_mappings = {}
        self.display_mappings = {}

    def normalize(self, text: str) -> str:
        text = re.sub(r"[^\w\s]", "", text)
        return text.lower().strip().translate(self._PL_TRANSLATION)

    def _generate_ability_variations(self, ability_name: str) -> list[str]:
        """Tworzy proste wariacje nazwy umiejetnosci do lepszego dopasowania."""
        variations = []

        normalized_full_name = self.normalize(ability_name)
        variations.append(normalized_full_name)

        words = normalized_full_name.split()

        if len(words) > 1:
            for word in words:
                if len(word) >= 4:
                    variations.append(word)

        return list(set(variations))

    def create_voice_mappings_from_api(self, champion_name: str | None = None) -> dict[str, str]:
        """Zwraca mapowania fraza -> klawisz dla aktualnego bohatera.

        Efekt uboczny: uzupelnia self.display_mappings (klawisz -> nazwa i klawisz)
        oraz self.current_abilities, ktore czyta panel.
        Gdy Live Client nie zwraca umiejetnosci, a znamy nazwe bohatera, dane
        biora sie z Data Dragon.
        """
        abilities_data = self.game_api.get_active_player_abilities()

        voice_map: dict[str, str] = {}
        display_map: dict[str, dict[str, str]] = {}

        for key, ability_info in (abilities_data or {}).items():
            if key not in self.keybinds:
                continue
            ability_name = (ability_info or {}).get("displayName")
            if not ability_name:
                continue
            key_binding = self.keybinds[key]
            display_map[key] = {"name": ability_name, "key": key_binding}
            for variation in self._generate_ability_variations(ability_name):
                voice_map[variation] = key_binding

        if not voice_map:
            champion = champion_name or self.game_api.get_current_champion()
            if champion:
                voice_map, display_map = self._mappings_from_data_dragon(champion)

        self.voice_mappings = voice_map
        self.display_mappings = display_map
        self.current_abilities = display_map

        return self.voice_mappings

    def _mappings_from_data_dragon(self, champion_name: str) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
        """Zapasowe zrodlo nazw umiejetnosci, gdy Live Client nic nie zwraca."""
        try:
            abilities = self.data_manager.get_champion_abilities(champion_name)
        except Exception as exc:  # brak sieci nie moze wywrocic petli gry
            log.warning("Data Dragon fallback failed for %s: %s", champion_name, exc)
            return {}, {}

        if not abilities:
            log.warning("No Data Dragon abilities for champion %s", champion_name)
            return {}, {}

        voice_map: dict[str, str] = {}
        display_map: dict[str, dict[str, str]] = {}
        for key, key_binding in self.keybinds.items():
            ability_name = abilities.get(key)
            if not ability_name:
                continue
            display_map[key] = {"name": ability_name, "key": key_binding}
            for variation in self._generate_ability_variations(ability_name):
                voice_map[variation] = key_binding

        log.info("Using Data Dragon ability names for %s (%d phrases)", champion_name, len(voice_map))
        return voice_map, display_map
