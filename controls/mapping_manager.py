"""Dopasowanie wypowiedzianego tekstu do klawisza.

Zrodlem prawdy dla trybu, czulosci i klawiszy summonerow jest obiekt Settings
z app.config. Ten modul nie czyta i nie zapisuje zadnych plikow.
"""

from __future__ import annotations

import difflib
import re

from app import config
from app.config import Settings
from controls import command_languages as cl
from app.logging_setup import get_logger

log = get_logger("mappings")

SOURCE_LETTER = "letter"
SOURCE_CHAMPION = "champion"
SOURCE_EXTRA = "extra"


class MappingManager:
    def __init__(self, settings: Settings | None = None, debug: bool = False) -> None:
        self.debug = debug
        self._settings = settings or config.load()
        self.spell_thresholds = {"low": 0.75, "medium": 0.60, "high": 0.40}
        self.extra_commands_threshold = 0.65
        self.ability_threshold = 0.55

        self._PL_TRANSLATION = str.maketrans(
            {"ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n", "ó": "o", "ś": "s", "ź": "z", "ż": "z"}
        )

        self.champion_spell_mappings: dict[str, str] = {}
        self.command_cache: dict[str, str | None] = {}
        self._rebuild()

    # --- konfiguracja -------------------------------------------------

    @property
    def settings(self) -> Settings:
        return self._settings

    @settings.setter
    def settings(self, value: Settings) -> None:
        self._settings = value
        self._rebuild()

    @property
    def language(self) -> str:
        return self._settings.language

    @property
    def mode(self) -> str:
        return self._mode

    @mode.setter
    def mode(self, value: str) -> None:
        self._mode = value
        self.command_cache.clear()
        self.active_mappings = self._build_active_mappings()

    def _rebuild(self) -> None:
        """Przelicza wszystkie mapowania na podstawie aktualnych ustawien."""
        self._mode = self._settings.recognition_mode
        self.sensitivity = self._settings.spell_sensitivity
        self.ability_mappings_exact = self._generate_ability_exact()
        self.ability_mappings_fuzzy = self._generate_ability_fuzzy()
        self.extra_commands = self._generate_extra_commands()
        self.command_cache.clear()
        self.active_mappings = self._build_active_mappings()

    # --- normalizacja -------------------------------------------------

    def normalize(self, text: str) -> str:
        """Normalizacja tekstu przed dopasowaniem."""
        text = re.sub(r"[^\w\s]", "", text)
        # Przeciagniete gloski ("arrr", "eeee") zwijamy do jednej litery,
        # zadne slowo w komendach nie ma potrojonej litery.
        text = re.sub(r"(.)\1{2,}", r"\1", text)
        return text.lower().strip().translate(self._PL_TRANSLATION)

    # --- slowniki -----------------------------------------------------

    def _active_language_tables(self, tables: dict[str, dict[str, str]]) -> list[dict[str, str]]:
        """Slowniki dla biezacego jezyka albo wszystkie przy wlaczonym scaleniu."""
        if self._settings.merge_command_languages:
            return list(tables.values())
        prefix = cl.language_prefix(self._settings.language)
        chosen = tables.get(prefix)
        return [chosen] if chosen else []

    def _generate_ability_exact(self) -> dict[str, str]:
        """Dokladne mapowania Q, W, E, R dla trybu 'letters'."""
        merged = dict(cl.LETTERS_UNIVERSAL)
        for table in self._active_language_tables(cl.LETTERS_BY_LANG):
            merged.update(table)
        return {self.normalize(k): v for k, v in merged.items()}

    def _generate_ability_fuzzy(self) -> dict[str, str]:
        """Mapowania rozmyte Q, W, E, R dla trybu 'letters'."""
        merged: dict[str, str] = {}
        for table in self._active_language_tables(cl.LETTER_FUZZY_BY_LANG):
            merged.update(table)
        return {self.normalize(k): v for k, v in merged.items()}

    def _generate_extra_commands(self) -> dict[str, str]:
        """Komendy dodatkowe dla biezacego jezyka (albo wszystkich po scaleniu)."""
        flash_key = self._settings.flash_key
        summ2_key = self._settings.summoner2_key

        merged = dict(cl.EXTRAS_UNIVERSAL)
        # Angielskie skroty sa lingua franca LoL-a, wiec przy braku slownika
        # dla danego jezyka zostaje chociaz angielski.
        tables = self._active_language_tables(cl.EXTRAS_BY_LANG)
        if not tables and not self._settings.merge_command_languages:
            tables = [cl.EXTRAS_BY_LANG["en"]]
        for table in tables:
            merged.update(table)

        commands = {}
        for phrase, slot in merged.items():
            if slot == cl.FLASH:
                commands[phrase] = flash_key
            elif slot == cl.SUMM2:
                commands[phrase] = summ2_key
            else:
                commands[phrase] = slot

        # Sama litera skonfigurowanego klawisza tez jest komenda: "d" wciska
        # Flasha, "f" drugi czar. Do tego wymowa litery po polsku i angielsku.
        spoken_letters = {
            "d": ("de", "di"),
            "f": ("ef", "fe"),
            "g": ("gie", "dzi"),
            "t": ("te", "ti"),
        }
        for key in (flash_key, summ2_key):
            if key and len(key) == 1 and key not in commands:
                commands[key] = key
                for spoken in spoken_letters.get(key, ()):
                    commands.setdefault(spoken, key)

        return {self.normalize(k): v for k, v in commands.items()}

    def _build_active_mappings(self) -> dict[str, str]:
        """Sklada aktywny slownik na podstawie trybu."""
        if self._mode == "spells":
            log.debug("Building active mappings for 'spells' mode")
            return {**self.champion_spell_mappings, **self.extra_commands}
        if self._mode != "letters":
            log.warning("Unknown recognition mode '%s', falling back to 'letters'", self._mode)
        else:
            log.debug("Building active mappings for 'letters' mode")
        return {**self.ability_mappings_fuzzy, **self.ability_mappings_exact, **self.extra_commands}

    # --- stan bohatera ------------------------------------------------

    def load_champion_mappings(self, champion_mappings: dict) -> None:
        """Wgrywa mapowania umiejetnosci aktualnego bohatera."""
        self.champion_spell_mappings = {self.normalize(k): v for k, v in champion_mappings.items()}
        self.command_cache.clear()
        self.active_mappings = self._build_active_mappings()
        log.debug("Loaded %d champion spell mappings", len(self.champion_spell_mappings))

    def reset_to_default(self) -> None:
        """Czysci mapowania bohatera po zakonczeniu gry."""
        self.champion_spell_mappings = {}
        self.command_cache.clear()
        self.active_mappings = self._build_active_mappings()

    # --- dopasowanie --------------------------------------------------

    def match_command(self, text: str) -> str | None:
        """Dopasowuje tekst do klawisza.

        Kolejnosc: cache, umiejetnosci wedlug trybu, komendy dodatkowe.
        """
        normalized_command = self.normalize(text)

        if normalized_command in self.command_cache:
            log.debug("Cache hit for '%s'", normalized_command)
            return self.command_cache[normalized_command]

        # Nieznany tryb zachowuje sie jak "letters", tak jak przy budowie mapowan.
        mode = self._mode if self._mode in ("letters", "spells") else "letters"

        if mode == "letters":
            ability_pool = {**self.ability_mappings_fuzzy, **self.ability_mappings_exact}
            ability_threshold = self.ability_threshold
            exact_pool = self.ability_mappings_exact
        else:
            ability_pool = self.champion_spell_mappings
            ability_threshold = self.spell_thresholds.get(self.sensitivity, 0.60)
            exact_pool = self.champion_spell_mappings

        if normalized_command in exact_pool:
            result = exact_pool[normalized_command]
            self.command_cache[normalized_command] = result
            log.debug("Ability exact match: '%s' -> %s", normalized_command, result)
            return result

        # Dokladne trafienie w komendy dodatkowe idzie PRZED rozmytym dopasowaniem
        # umiejetnosci. Inaczej "back" w trybie liter ladowalo w E, a "heal" w Q.
        if normalized_command in self.extra_commands:
            result = self.extra_commands[normalized_command]
            self.command_cache[normalized_command] = result
            log.debug("Extra command exact match: '%s' -> %s", normalized_command, result)
            return result

        best_ability_match = self._find_fuzzy_match(normalized_command, ability_pool, ability_threshold)
        if best_ability_match:
            self.command_cache[normalized_command] = best_ability_match[1]
            log.debug(
                "Ability fuzzy match (threshold=%.2f): '%s' -> '%s' -> %s",
                ability_threshold, normalized_command, best_ability_match[0], best_ability_match[1],
            )
            return best_ability_match[1]

        if normalized_command in self.extra_commands:
            result = self.extra_commands[normalized_command]
            self.command_cache[normalized_command] = result
            log.debug("Extra command exact match: '%s' -> %s", normalized_command, result)
            return result

        best_extra_match = self._find_fuzzy_match(
            normalized_command, self.extra_commands, self.extra_commands_threshold
        )
        if best_extra_match:
            self.command_cache[normalized_command] = best_extra_match[1]
            log.debug(
                "Extra command fuzzy match: '%s' -> '%s' -> %s",
                normalized_command, best_extra_match[0], best_extra_match[1],
            )
            return best_extra_match[1]

        log.debug("No match found for '%s'", normalized_command)
        return None

    def _find_fuzzy_match(self, command: str, mappings: dict, threshold: float) -> tuple | None:
        """Zwraca (dopasowana_frazy, klawisz) albo None."""
        best_match = None
        highest_similarity = 0.0

        for phrase, key in mappings.items():
            if len(phrase) <= 2 and command != phrase:
                continue

            similarity = difflib.SequenceMatcher(None, phrase, command).ratio()

            if similarity >= threshold and similarity > highest_similarity:
                highest_similarity = similarity
                best_match = (phrase, key, similarity)

        if best_match:
            log.debug(
                "Fuzzy matching: '%s' ~= '%s' (similarity %.2f)", command, best_match[0], best_match[2]
            )
            return (best_match[0], best_match[1])

        return None

    # --- widok dla panelu ---------------------------------------------

    def describe_mappings(self) -> list[dict]:
        """Aktywne mapowania w formie [{phrase, key, source}]."""
        rows: list[dict] = []
        seen: set[str] = set()

        def add(source: str, mapping: dict) -> None:
            for phrase, key in mapping.items():
                if phrase in seen:
                    continue
                seen.add(phrase)
                rows.append({"phrase": phrase, "key": key, "source": source})

        if self._mode == "spells":
            add(SOURCE_CHAMPION, self.champion_spell_mappings)
        else:
            add(SOURCE_LETTER, self.ability_mappings_exact)
            add(SOURCE_LETTER, self.ability_mappings_fuzzy)
        add(SOURCE_EXTRA, self.extra_commands)
        return rows

    def set_sensitivity(self, level: str) -> None:
        """Ustawia czulosc dla trybu spells. Zapis do dysku robi warstwa app.config."""
        self.command_cache.clear()
        if level in self.spell_thresholds:
            self.sensitivity = level
            log.debug("Sensitivity set to %s (threshold %.2f)", level, self.spell_thresholds[level])

    def get_statistics(self) -> dict:
        """Statystyki mapowan, uzywane przez panel i logi diagnostyczne."""
        return {
            "mode": self._mode,
            "sensitivity": self.sensitivity,
            "ability_exact": len(self.ability_mappings_exact),
            "ability_fuzzy": len(self.ability_mappings_fuzzy),
            "extra_commands": len(self.extra_commands),
            "champion_spells": len(self.champion_spell_mappings),
            "cache_size": len(self.command_cache),
            "total_active": len(self.active_mappings),
            "spell_threshold": self.spell_thresholds.get(self.sensitivity, 0.60),
        }
