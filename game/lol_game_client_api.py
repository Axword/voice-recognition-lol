#!/usr/bin/env python3
"""
League of Legends Game Client API Integration
Connects to the live game client to get current champion and game state
"""
import time
import requests
import json
from typing import Dict, Optional
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class LoLGameClientAPI:
    def __init__(self):
        self.base_url = "https://127.0.0.1:2999"
        self.session = requests.Session()
        self.session.verify = False
        
    def is_game_active(self) -> bool:
        """Check if League of Legends game is currently running"""
        try:
            response = self.session.get(
                f"{self.base_url}/liveclientdata/gamestats",
                timeout=2
            )
            return response.status_code == 200
        except:
            return False
    
    def get_active_player(self) -> Optional[Dict]:
        """Get information about the active player"""
        try:
            response = self.session.get(
                f"{self.base_url}/liveclientdata/activeplayer",
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Error getting active player: {e}")
        return None
    
    def get_current_champion(self) -> Optional[str]:
        """Get the currently played champion name"""
        """Get the currently played champion name"""
        player_data = self.get_active_player()
        champion = player_data.get('summonerName')
        if champion:
            print(f"✅ Found champion in active player data: {champion}")
            return champion
        print(f"ℹ️ No champion found in active player data {champion}")
    
    def get_active_player_abilities(self) -> Optional[Dict]:
        """Get the active player's abilities"""
        try:
            response = self.session.get(
                f"{self.base_url}/liveclientdata/activeplayerabilities",
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Error getting abilities: {e}")
        return None
    
    def get_active_player_runes(self) -> Optional[Dict]:
        """Get the active player's runes"""
        try:
            response = self.session.get(
                f"{self.base_url}/liveclientdata/activeplayerrunes",
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Error getting runes: {e}")
        return None
    
    def get_all_players(self) -> Optional[list]:
        """Get list of all players in the game"""
        try:
            response = self.session.get(
                f"{self.base_url}/liveclientdata/playerlist",
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Error getting player list: {e}")
        return None
    
    def get_game_stats(self) -> Optional[Dict]:
        """Get basic game statistics"""
        try:
            response = self.session.get(
                f"{self.base_url}/liveclientdata/gamestats",
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Error getting game stats: {e}")
        return None
    
    def get_events(self) -> Optional[Dict]:
        """Get game events"""
        try:
            response = self.session.get(
                f"{self.base_url}/liveclientdata/eventdata",
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Error getting events: {e}")
        return None
    
    def get_champion_and_summoner_spells(self) -> Dict:
        """Get current champion and summoner spell information"""
        result = {
            'champion': None,
            'summoner_spells': {},
            'game_active': False
        }
        
        if not self.is_game_active():
            return result
        
        result['game_active'] = True
        result['champion'] = self.get_current_champion()
        abilities = self.get_active_player_abilities()
        if abilities:
            for key, ability in abilities.items():
                if key.startswith('Summoner'):
                    result['summoner_spells'][key] = ability.get('displayName', '')
        
        player_data = self.get_active_player()
        if player_data and 'summonerSpells' in player_data:
            spells = player_data['summonerSpells']
            result['summoner_spells']['D'] = spells.get('summonerSpellOne', {}).get('displayName', '')
            result['summoner_spells']['F'] = spells.get('summonerSpellTwo', {}).get('displayName', '')
        
        return result
    
    def monitor_game_state(self, callback_func=None):
        """Monitor game state and call callback when champion changes"""
        last_champion = None
        
        while True:
            try:
                current_data = self.get_champion_and_summoner_spells()
                current_champion = current_data.get('champion')
                
                if current_champion != last_champion:
                    print(f"Champion changed: {last_champion} -> {current_champion}")
                    if callback_func:
                        callback_func(current_data)
                    last_champion = current_champion
                time.sleep(5)
                
            except KeyboardInterrupt:
                print("Monitoring stopped")
                break
            except Exception as e:
                print(f"Error in monitoring: {e}")
                import time
                time.sleep(10)
