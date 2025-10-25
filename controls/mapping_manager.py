# controls/mapping_manager.py

import difflib
import re
import json
from typing import Optional

class MappingManager:
    def __init__(self, language="pl_PL", debug=True):
        self.language = language
        self.debug = debug
        self.config = self._load_config()
        
        self.mode = self.config.get("recognition_mode", "letters")
        self.accuracy_threshold = self.config.get("recognition_accuracy_threshold", 0.85)

        self._PL_TRANSLATION = str.maketrans(
            {"ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n", "ó": "o", "ś": "s", "ź": "z", "ż": "z"}
        )
        
        self.letter_mappings = self._generate_letter_mappings()
        self.default_core_mappings = self._generate_default_core_mappings()
        self.champion_spell_mappings = {}
        
        self.active_mappings = self._build_active_mappings()

    def _load_config(self) -> dict:
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            default_config = {"recognition_mode": "letters", "recognition_accuracy_threshold": 0.85}
            with open("config.json", "w", encoding="utf-8") as f: json.dump(default_config, f, indent=2)
            return default_config

    def normalize(self, text: str) -> str:
        text = re.sub(r'[^\w\s]', '', text)
        return text.lower().strip().translate(self._PL_TRANSLATION)

    def _generate_letter_mappings(self) -> dict:
        """Tylko mapowania dla Q, W, E, R i ich wariantów."""
        return {
            "q": "q", "kju": "q", "ku": "q", "kiu": "q", "ciu": "q", "tiu": "q", "czu": "q", "2": "q", 
            "thank you": "q", 'chciał': 'q', "dlaczego": "q", "kół": "qe",
            "w": "w", "wu": "w", "vu": "w", "wow": "w", "wów": "w", "buch": "w", "włuch": "w", "wy": "w", "ty": "w",
            "łow": "w", "woł": "w", "łoł": "w", "wuf": "w", "łuf": "w", "wiem": "w", "zim": "w", "wiesz": "w",
            "zbyt": "w", "bo": "w",
            "e": "e", "je": "e", "a": "e", "eh": "e", "eee": "e", "tak": "e", "ale": "e", "bye": "e",
            "r": "r", "er": "r", "ar": "r", "ult": "r", "uld": "r", "olt": "r", "olde": "r", "wójt": "r",
            "r": "r", "er": "r", "ar": "r", "ult": "r", "ulti": "r",
            "uld": "r", "olt": "r", "olde": "r", "ultymat": "r",
            "ul": "r", "ur": "r", "rka": "r",
        }

    def _generate_default_core_mappings(self) -> dict:
        """
        Wszystkie inne komendy globalne - przywrócone z Twojej listy.
        Klucze są od razu normalizowane dla spójności.
        """
        flash_key = "d"
        summ2_key = "f"
        
        mappings = {
            "flash": flash_key, "flasz": flash_key, "blysk": flash_key, "flas": flash_key,
            "heal": summ2_key, "leczenie": summ2_key, "hil": summ2_key, "uzdrowienie": summ2_key,
            "barrier": summ2_key, "bariera": summ2_key, "shield": summ2_key, "tarcza": summ2_key,
            "cleanse": summ2_key, "oczyszczenie": summ2_key, "clean": summ2_key,
            "ignite": summ2_key, "podpalenie": summ2_key,
            "exhaust": summ2_key, "wyczerpanie": summ2_key,
            "ghost": summ2_key, "duch": summ2_key,
            "teleport": summ2_key, "teleportacja": summ2_key, "tp": summ2_key,
            "smite": summ2_key, "karanie": summ2_key,

            # Akcje w grze
            "attack": "right_click", "atak": "right_click", "auto": "right_click",
            "stop": "s", "zatrzymaj": "s", "halt": "s",
            "back": "b", "recall": "b", "base": "b", "baza": "b", "wracaj": "b", "powrot": "b",
            "shop": "p", "sklep": "p",

            # Sklep i przedmioty
            "buy": "right_click", "kup": "right_click",
            "znajdz": "item_search", "find": "item_search", "szukaj": "item_search", "search": "item_search",

            # Inne
            "cokolwiek": "random_ability", "anything": "random_ability", "whatever": "random_ability",
            "niewygodnie mi sie siedzi": "esc",
            "niewdzieczna gowno gra": "esc",
            "no i wylaczam streama": "esc"
        }
        return {self.normalize(k): v for k, v in mappings.items()}

    def _build_active_mappings(self) -> dict:
        """Buduje słownik aktywnych komend na podstawie trybu."""
        if self.mode == "letters":
            if self.debug: print("DEBUG: Building active mappings for 'letters' (PRO) mode.")
            return {**self.letter_mappings, **self.default_core_mappings}
        elif self.mode == "spells":
            if self.debug: print("DEBUG: Building active mappings for 'spells' (CONTENT) mode.")
            return {**self.champion_spell_mappings, **self.default_core_mappings}
        else:
            if self.debug: print(f"DEBUG: Unknown mode '{self.mode}'. Falling back to 'letters' mode.")
            return {**self.letter_mappings, **self.default_core_mappings}

    def load_champion_mappings(self, champion_mappings: dict):
        self._champion_spell_mappings = {self.normalize(k): v for k, v in champion_mappings.items()}
        self.active_mappings = self._build_active_mappings()

    def reset_to_default(self):
        self._champion_spell_mappings = {}
        self.active_mappings = self._build_active_mappings()


    def match_command(self, text: str) -> Optional[str]:
        normalized_command = self.normalize(text)
        
        if normalized_command in self.active_mappings:
            if self.debug: print(f"DEBUG: Cache hit for '{normalized_command}'")
            return self.active_mappings[normalized_command]
        
        best_match = None
        highest_similarity = 0.0

        for phrase, key in self.active_mappings.items():
            similarity = difflib.SequenceMatcher(None, phrase, normalized_command).ratio()
            
            threshold = 0.55 if self.mode == 'letters' and len(phrase) <= 3 else self.accuracy_threshold

            if similarity >= threshold and similarity > highest_similarity:
                highest_similarity = similarity
                best_match = (phrase, key)
        
        if best_match:
            if self.debug: print(f"DEBUG: Fuzzy match found: '{normalized_command}' -> '{best_match[0]}' (Similarity: {highest_similarity:.2f})")
            return best_match[1]

        if self.debug: print(f"DEBUG: No match found for '{normalized_command}'")
        return None