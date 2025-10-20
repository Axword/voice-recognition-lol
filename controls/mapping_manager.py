import difflib
import re
from typing import Optional, Tuple, List

class MappingManager:
    def __init__(self, language="pl_PL"):
        self.language = language
        self.current_champion = None
        self._default_mappings = self._generate_default_mappings()
        self._PL_TRANSLATION = str.maketrans(
            {"ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n", "ó": "o", "ś": "s", "ź": "z", "ż": "z"}
        )
        self.mappings = self._default_mappings.copy()
        self.keybinds = {
            "Flash": "f",
            "Summoner2": "d"
        }
    def normalize(self, text: str) -> str:
        """Normalizuje tekst: małe litery, usuwa znaki specjalne i polskie znaki."""
        text = re.sub(r'[^\w\s]', '', text)
        return text.lower().strip().translate(self._PL_TRANSLATION)

    def _generate_default_mappings(self) -> None:
        """Generate default voice mappings independent of champion."""
        flash_key = {}.get("Flash", "f")
        summ2_key = {}.get("Summoner2", "d")

        return {
            "flash": flash_key,
            "flasz": flash_key,
            "błysk": flash_key,
            "blysk": flash_key,
            "flas": flash_key,
            "fla": flash_key,
            "błys": flash_key,
            "blys": flash_key,
            "flash me": flash_key,
            "flash now": flash_key,
            "flash teraz": flash_key,
            "heal": summ2_key,
            "leczenie": summ2_key,
            "heal me": summ2_key,
            "heal up": summ2_key,
            "barrier": summ2_key,
            "bariera": summ2_key,
            "shield": summ2_key,
            "tarcza": summ2_key,
            "cleanse": summ2_key,
            "oczyszczenie": summ2_key,
            "clean": summ2_key,
            "cleanse me": summ2_key,
            "ignite": summ2_key,
            "ignite him": summ2_key,
            "ignite enemy": summ2_key,
            "exhaust": summ2_key,
            "wyczerpanie": summ2_key,
            "exhaust enemy": summ2_key,
            "ghost": summ2_key,
            "duch": summ2_key,
            "ghost speed": summ2_key,
            "teleport": summ2_key,
            "teleportacja": summ2_key,
            "tp": summ2_key,
            "teleport me": summ2_key,
            "smite": summ2_key,
            "karanie": summ2_key,
            "smite monster": summ2_key,
            "attack": "right_click",
            "atak": "right_click",
            "auto": "right_click",
            "auto attack": "right_click",
            "attack move": "right_click",
            "attack enemy": "right_click",
            "hit": "right_click",
            "stop": "s",
            "zatrzymaj": "s",
            "halt": "s",
            "stop moving": "s",
            "back": "b",
            "recall": "b",
            "base": "b",
            "baza": "b",
            "wracaj": "b",
            "powrót": "b",
            "powrot": "b",
            "go back": "b",
            "shop": "p",
            "sklep": "p",
            "buy": "right_click",
            "kup": "right_click",
            "open shop": "p",
            "znajdź": "item_search",
            "znajdz": "item_search",
            "find": "item_search",
            "szukaj": "item_search",
            "search": "item_search",
            "combo": "combo",
            "kombinacja": "combo",
            "sekwencja": "combo",
            "chain": "combo",
            "combo q w e": "combo",
            "combo q w e r": "combo",
            "and": "combo",
            "i": "combo",
            "cokolwiek": "random_ability",
            "anything": "random_ability",
            "whatever": "random_ability",
            "niewygodnie mi się siedzi": "esc",
            "niewdzięczna gówno gra": "esc",
            "no i wyłączam streama": "esc"
        }

    def load_champion_mappings(self, champion_mappings: dict):
        self.mappings = self._default_mappings.copy()
        normalized_champ_mappings = {self.normalize(k): v for k, v in champion_mappings.items()}
        self.mappings.update(normalized_champ_mappings)

    def reset_to_default(self):
        self.mappings = self._default_mappings.copy()
        
    @staticmethod
    def _split_words(text: str) -> List[str]:
        """Dzieli tekst na słowa i usuwa puste tokeny."""
        return [w for w in text.split() if w]

    def find_best_match(self, command: str) -> Optional[Tuple[str, str]]:
        """Znajduje najlepsze dopasowanie dla rozpoznanej komendy."""
        normalized_command = self.normalize(command)
        
        if normalized_command in self.mappings:
            return normalized_command, self.mappings[normalized_command]

        matches: List[Tuple[str, str, float]] = []
        command_words = self._split_words(normalized_command)

        for phrase, key in self.mappings.items():
            if phrase in normalized_command:
                matches.append((phrase, key, 100.0 + len(phrase)))
                continue

            phrase_words = self._split_words(phrase)
            for p_word in phrase_words:
                for c_word in command_words:
                    if len(p_word) < 3 or len(c_word) < 3:
                        continue
                    
                    sim = difflib.SequenceMatcher(None, p_word, c_word).ratio()
                    threshold = 0.85 if len(p_word) > 3 else 0.9

                    if sim >= threshold:
                        score = sim * 10 + len(p_word)
                        matches.append((phrase, key, score))
        
        if not matches:
            return None

        matches.sort(key=lambda x: x[2], reverse=True)
        best_match = matches[0]
        return best_match[0], best_match[1]

    def match_command(self, text: str) -> Optional[str]:
        """Główna metoda dopasowująca, używa find_best_match."""
        match = self.find_best_match(text)
        if match:
            return match[1]
        return None
    def update_champion(self, champion_name: str):
        self.current_champion = champion_name