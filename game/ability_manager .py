# game/ability_manager.py

from typing import Dict, List
from game.lol_game_client_api import LoLGameClientAPI

class AbilityManager:
    def __init__(self, game_api: LoLGameClientAPI):
        self.game_api = game_api
        self.keybinds = {'Q': 'q', 'W': 'w', 'E': 'e', 'R': 'r'}

    def _generate_ability_variations(self, ability_name: str) -> List[str]:
        """Tworzy proste wariacje nazwy umiejętności do lepszego dopasowania."""
        variations = []
        name_lower = ability_name.lower()
        variations.append(name_lower)
        words = name_lower.split()
        if len(words) > 1:
            for word in words:
                if len(word) >= 4:
                    variations.append(word)
        
        return list(set(variations)) 

    def create_voice_mappings_from_api(self) -> Dict[str, str]:
        """
        Pobiera umiejętności aktywnego gracza z API i tworzy z nich mapowania głosowe.
        """
        abilities_data = self.game_api.get_active_player_abilities()
        if not abilities_data:
            return {}

        mappings = {}
        for key, ability_info in abilities_data.items():
            if key in self.keybinds:
                ability_name = ability_info.get("displayName")
                key_binding = self.keybinds[key]
                
                if ability_name:
                    variations = self._generate_ability_variations(ability_name)
                    for variation in variations:
                        mappings[variation] = key_binding
        
        return mappings