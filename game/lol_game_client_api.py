# game/lol_game_client_api.py

import time
import requests
from typing import Dict, Optional, List
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class LoLGameClientAPI:
    def __init__(self):
        self.base_url = "https://127.0.0.1:2999"
        self.session = requests.Session()
        self.session.verify = False
        
    def is_game_active(self) -> bool:
        """Sprawdza, czy gra jest aktualnie w toku."""
        try:
            response = self.session.get(f"{self.base_url}/liveclientdata/gamestats", timeout=1)
            return response.status_code == 200
        except requests.RequestException:
            return False
    
    def get_active_player_name(self) -> Optional[str]:
        """Pobiera nick (summonerName) aktywnego gracza."""
        try:
            response = self.session.get(f"{self.base_url}/liveclientdata/activeplayer", timeout=1)
            if response.status_code == 200:
                return response.json().get('summonerName')
        except requests.RequestException:
            pass
        return None

    def get_all_players(self) -> Optional[List[Dict]]:
        """Pobiera listę wszystkich graczy w meczu."""
        try:
            response = self.session.get(f"{self.base_url}/liveclientdata/playerlist", timeout=1)
            if response.status_code == 200:
                return response.json()
        except requests.RequestException:
            pass
        return None

    def get_current_champion(self) -> Optional[str]:
        """
        Pobiera nazwę bohatera (championName) aktywnego gracza.
        Realizuje logikę:
        1. Pobierz nick aktywnego gracza.
        2. Pobierz listę wszystkich graczy.
        3. Znajdź na liście gracza o tym nicku i zwróć jego championName.
        """
        active_player_name = self.get_active_player_name()
        if not active_player_name:
            return None

        all_players = self.get_all_players()
        if not all_players:
            return None

        for player in all_players:
            if player.get('summonerName') == active_player_name:
                return player.get('championName')
        
        return None

    def get_active_player_abilities(self) -> Optional[Dict]:
        """Pobiera aktualne umiejętności aktywnego gracza (ważne dla bohaterów ze zmiennymi skillami)."""
        try:
            response = self.session.get(f"{self.base_url}/liveclientdata/activeplayerabilities", timeout=1)
            if response.status_code == 200:
                return response.json()
        except requests.RequestException:
            pass
        return None