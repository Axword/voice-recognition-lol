import difflib

class MappingManager:
    def __init__(self, language="pl_PL"):
        self.language = language
        self.current_champion = None
        self._default_mappings = self._generate_default_mappings()
        self.mappings = self._default_mappings.copy()
        self.keybinds = {
            "Flash": "f",
            "Summoner2": "d"
        }
    def normalize(self, text: str) -> str:
        return text.lower().strip()

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
            """Łączy mapowania domyślne z mapowaniami dla konkretnego championa."""
            self.mappings = self._default_mappings.copy()
            self.mappings.update(champion_mappings)

    def reset_to_default(self):
        """Przywraca tylko domyślne mapowania."""
        self.mappings = self._default_mappings.copy()

    def match_command(self, text: str):
        if text in self.mappings:
            return self.mappings[text]
        for phrase, key in self.mappings.items():
            if difflib.SequenceMatcher(None, phrase, text).ratio() > 0.85:
                return key
        return None

    def update_champion(self, champion_name: str):
        self.current_champion = champion_name