# controls/mapping_manager.py

import difflib
import re
import json
import random
from typing import Optional, Union

class MappingManager:
    def __init__(self, language="pl_PL", debug=True):
        self.language = language
        self.debug = debug
        self.config = self._load_config()
        self.mode = self.config.get("recognition_mode", "letters")
        self.sensitivity = self.config.get("spell_sensitivity", "medium")
        self.spell_thresholds = {
            "low": 0.75,
            "medium": 0.60,
            "high": 0.40
        }
        self.extra_commands_threshold = 0.65

        self._PL_TRANSLATION = str.maketrans(
            {"ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n", "ó": "o", "ś": "s", "ź": "z", "ż": "z"}
        )
        
        self.ability_mappings_exact = self._generate_ability_exact()
        self.ability_mappings_fuzzy = self._generate_ability_fuzzy()
        self.extra_commands = self._generate_extra_commands()
        self.champion_spell_mappings = {}
        self.command_cache = {}
        self.active_mappings = self._build_active_mappings()


    def _load_config(self) -> dict:
        try:
            with open("config/config.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            import os
            os.makedirs("config", exist_ok=True)
            default_config = {
                "recognition_mode": "letters",
                "spell_sensitivity": "medium"
            }
            with open("config/config.json", "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2)
            return default_config

    def normalize(self, text: str) -> str:
        """Normalize text for matching."""
        text = re.sub(r'[^\w\s]', '', text)
        return text.lower().strip().translate(self._PL_TRANSLATION)

    def _generate_ability_exact(self) -> dict:
        """
        Exact mappings for Q, W, E, R - used in 'letters' mode
        """
        return {
            "q": "q", "kju": "q", "ku": "q", "kiu": "q", "ok": "q",
            "w": "w", "wu": "w", "vu": "w", "wow": "w", "bo": "w",
            "e": "e", "je": "e", "a": "e", "tak": "e", "ale": "e",
            "r": "r", "er": "r", "ar": "r", "ult": "r", "ulti": "r",
        }

    def _generate_ability_fuzzy(self) -> dict:
        """
        Fuzzy mappings for Q, W, E, R - used in 'letters' mode
        """
        return {
            # Q fuzzy
            "ciu": "q", "tiu": "q", "czu": "q", "chcial": "q", "dlaczego": "q",
            "dzien dobry": "q", "ka": "q", "thank you": "q",
            
            # W fuzzy
            "buch": "w", "wluch": "w", "wy": "w", "ty": "w",
            "low": "w", "wol": "w", "lol": "w", "wuf": "w", "luf": "w",
            "wiem": "w", "zim": "w", "wiesz": "w", "zbyt": "w",
            
            # E fuzzy
            "eh": "e", "eee": "e", "bye": "e", "ej": "e",
            
            # R fuzzy
            "uld": "r", "olt": "r", "olde": "r", "wojt": "r",
            "ultymat": "r", "ul": "r", "ur": "r", "rka": "r", "ultimate": "r",
        }

    def _generate_extra_commands(self) -> dict:
        """
        Extra commands available in all modes.
        """
        flash_key = self.config.get("flash_key", "d")
        summ2_key = self.config.get("summoner2_key", "f")
        
        commands = {
            "flash": flash_key, "flasz": flash_key, "blysk": flash_key, "flas": flash_key,
            "bo jest": flash_key, "zlasz": flash_key, "klasz": flash_key, "slasz": flash_key,
            
            "heal": summ2_key, "hil": summ2_key, "leczenie": summ2_key, "uzdrowienie": summ2_key,
            "barrier": summ2_key, "bariera": summ2_key, "shield": summ2_key, "tarcza": summ2_key,
            "cleanse": summ2_key, "oczyszczenie": summ2_key, "clean": summ2_key,
            "ignite": summ2_key, "podpalenie": summ2_key, "ignajt": summ2_key,
            "exhaust": summ2_key, "wyczerpanie": summ2_key,
            "ghost": summ2_key, "duch": summ2_key,
            "teleport": summ2_key, "teleportacja": summ2_key, "tp": summ2_key,
            "smite": summ2_key, "karanie": summ2_key, "smajt": summ2_key,
            
            "stop": "s", "zatrzymaj": "s", "stoj": "s", "halt": "s",
            "back": "b", "baza": "b", "recall": "b", "powrot": "b", "base": "b",
            "shop": "p", "sklep": "p",
            
            "escape": "escape", "esc": "escape", "anuluj": "escape", "cancel": "escape",
            "random": "random", "losowa": "random", "cokolwiek": "random", "losowo": "random",
            
            "niewygodnie mi sie siedzi": "escape",
            "niewdzieczna gowno gra": "escape",
            "no i wylaczam streama": "escape",
        }
        
        return {self.normalize(k): v for k, v in commands.items()}

    def _build_active_mappings(self) -> dict:
        """Builds the active mappings based on the current mode."""
        if self.mode == "letters":
            if self.debug: print("DEBUG: Building active mappings for 'letters' (PRO) mode.")
            return {**self.ability_mappings_fuzzy, **self.ability_mappings_exact, **self.extra_commands}
        elif self.mode == "spells":
            if self.debug: print("DEBUG: Building active mappings for 'spells' (CONTENT) mode.")
            return {**self.champion_spell_mappings, **self.extra_commands}
        else:
            if self.debug: print(f"DEBUG: Unknown mode '{self.mode}'. Falling back to 'letters' mode.")
            return {**self.ability_mappings_fuzzy, **self.ability_mappings_exact, **self.extra_commands}

    def load_champion_mappings(self, champion_mappings: dict):
        """Loads champion spell mappings."""
        self.champion_spell_mappings = {self.normalize(k): v for k, v in champion_mappings.items()}
        self.command_cache.clear()
        if self.debug:
            print(f"DEBUG: Loaded {len(self.champion_spell_mappings)} champion spell mappings")

    def reset_to_default(self):
        """Resets mappings."""
        self.champion_spell_mappings = {}
        self.command_cache.clear()

    def match_command(self, text: str) -> Optional[str]:
        """
        Główna funkcja dopasowania komend.
        Kolejność:
        1. Sprawdź cache
        2. Sprawdź umiejętności (zależnie od trybu) - PRIORYTET
        3. Sprawdź extra commands (ZAWSZE aktywne)
        4. Sprawdź specjalne komendy (random)
        """
        normalized_command = self.normalize(text)
        
        if normalized_command in self.command_cache:
            if self.debug:
                print(f"DEBUG: Cache hit for '{normalized_command}'")
            return self.command_cache[normalized_command]
        
        if self.mode == "letters":            
            if normalized_command in self.ability_mappings_exact:
                result = self.ability_mappings_exact[normalized_command]
                self.command_cache[normalized_command] = result
                if self.debug:
                    print(f"DEBUG: Ability exact match: '{normalized_command}' -> {result}")
                return result
            
            combined_abilities = {**self.ability_mappings_fuzzy, **self.ability_mappings_exact}
            best_ability_match = self._find_fuzzy_match(
                normalized_command,
                combined_abilities,
                0.55
            )
            if best_ability_match:
                self.command_cache[normalized_command] = best_ability_match[1]
                if self.debug:
                    print(f"DEBUG: Ability fuzzy match: '{normalized_command}' -> "
                        f"'{best_ability_match[0]}' -> {best_ability_match[1]}")
                return best_ability_match[1]
                
        elif self.mode == "spells":
            if normalized_command in self.champion_spell_mappings:
                result = self.champion_spell_mappings[normalized_command]
                self.command_cache[normalized_command] = result
                if self.debug:
                    print(f"DEBUG: Champion spell exact match: '{normalized_command}' -> {result}")
                return result
            
            threshold = self.spell_thresholds.get(self.sensitivity, 0.60)
            best_spell_match = self._find_fuzzy_match(
                normalized_command,
                self.champion_spell_mappings,
                threshold
            )
            if best_spell_match:
                self.command_cache[normalized_command] = best_spell_match[1]
                if self.debug:
                    print(f"DEBUG: Champion spell fuzzy match (threshold={threshold:.2f}): "
                        f"'{normalized_command}' -> '{best_spell_match[0]}' -> {best_spell_match[1]}")
                return best_spell_match[1]

        if normalized_command in self.extra_commands:
            result = self.extra_commands[normalized_command]
            self.command_cache[normalized_command] = result
            if self.debug:
                print(f"DEBUG: Extra command exact match: '{normalized_command}' -> {result}")
            return result
        
        best_extra_match = self._find_fuzzy_match(
            normalized_command, 
            self.extra_commands, 
            self.extra_commands_threshold
        )
        if best_extra_match:
            self.command_cache[normalized_command] = best_extra_match[1]
            if self.debug:
                print(f"DEBUG: Extra command fuzzy match: '{normalized_command}' -> "
                    f"'{best_extra_match[0]}' -> {best_extra_match[1]}")
            return best_extra_match[1]

        if self.debug:
            print(f"DEBUG: No match found for '{normalized_command}'")
        return None

    def _find_fuzzy_match(self, command: str, mappings: dict, threshold: float) -> Optional[tuple]:
        """
        Pomocnicza funkcja do szukania fuzzy match.
        Zwraca tuple (matched_phrase, key) lub None.
        """
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
            if self.debug:
                print(f"DEBUG: Fuzzy matching: '{command}' ~= '{best_match[0]}' "
                      f"(similarity: {best_match[2]:.2f})")
            return (best_match[0], best_match[1])
        
        return None

    def set_sensitivity(self, level: str):
        """Ustawia czułość rozpoznawania dla trybu spells."""
        self.command_cache.clear()
        if level in self.spell_thresholds:
            self.sensitivity = level
            self.config["spell_sensitivity"] = level
            self._save_config()
            if self.debug:
                print(f"DEBUG: Sensitivity set to {level} (threshold: {self.spell_thresholds[level]})")

    def _save_config(self):
        """Zapisuje konfigurację."""
        try:
            with open("config/config.json", "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            if self.debug:
                print(f"DEBUG: Error saving config: {e}")

    def get_statistics(self) -> dict:
        """Zwraca statystyki mapowań."""
        return {
            "mode": self.mode,
            "sensitivity": self.sensitivity,
            "ability_exact": len(self.ability_mappings_exact),
            "ability_fuzzy": len(self.ability_mappings_fuzzy),
            "extra_commands": len(self.extra_commands),
            "champion_spells": len(self.champion_spell_mappings),
            "cache_size": len(self.command_cache),
            "total_active": len(self.active_mappings),
            "spell_threshold": self.spell_thresholds.get(self.sensitivity, 0.60)
        }