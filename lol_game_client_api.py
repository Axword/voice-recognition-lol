#!/usr/bin/env python3
"""
League of Legends Game Client API Integration
Connects to the live game client to get current champion and game state
"""

import requests
import json
from typing import Dict, Optional
import urllib3

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class LoLGameClientAPI:
    def __init__(self):
        self.base_url = "https://127.0.0.1:2999"
        self.session = requests.Session()
        self.session.verify = False  # Ignore SSL certificate errors
        
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
        try:
            # First try to get from player list (most reliable)
            player_list = self.get_all_players()
            if player_list:
                # Find the active player (usually the first one or one with 'isBot': false)
                for player in player_list:
                    if not player.get('isBot', True):  # Find human player
                        champion_name = player.get('championName')
                        if champion_name:
                            print(f"🎯 Champion found via player list: {champion_name}")
                            return champion_name
                
                # If no human player found, try first player
                if player_list:
                    champion_name = player_list[0].get('championName')
                    if champion_name:
                        print(f"🎯 Champion found via first player: {champion_name}")
                        return champion_name
            
            # Fallback: try active player data
            player_data = self.get_active_player()
            if player_data:
                print(f"🔍 Active player data: {player_data}")
                # Try different possible fields
                for field in ['championName', 'champion', 'championId']:
                    if field in player_data:
                        champion_name = player_data[field]
                        if champion_name:
                            print(f"🎯 Champion found via active player ({field}): {champion_name}")
                            return champion_name
            
            print("❌ No champion found in any data source")
            return None
            
        except Exception as e:
            print(f"❌ Error getting current champion: {e}")
            return None
    
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
        
        # Get champion name
        result['champion'] = self.get_current_champion()
        
        # Get abilities (includes summoner spells in some cases)
        abilities = self.get_active_player_abilities()
        if abilities:
            # Extract summoner spells if available
            for key, ability in abilities.items():
                if key.startswith('Summoner'):
                    result['summoner_spells'][key] = ability.get('displayName', '')
        
        # Try to get summoner spells from player data
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
                
                # Wait before next check
                import time
                time.sleep(5)
                
            except KeyboardInterrupt:
                print("Monitoring stopped")
                break
            except Exception as e:
                print(f"Error in monitoring: {e}")
                import time
                time.sleep(10)

# Testing and example usage
if __name__ == "__main__":
    api = LoLGameClientAPI()
    
    print("=== League of Legends Game Client API Test ===")
    
    # Test connection
    if api.is_game_active():
        print("✅ Game is active!")
        
        # Get current champion
        champion = api.get_current_champion()
        print(f"Current champion: {champion}")
        
        # Get abilities
        abilities = api.get_active_player_abilities()
        if abilities:
            print("Abilities:")
            for key, ability in abilities.items():
                print(f"  {key}: {ability.get('displayName', 'N/A')}")
        
        # Get summoner spells and champion info
        game_data = api.get_champion_and_summoner_spells()
        print(f"Game data: {json.dumps(game_data, indent=2)}")
        
        # Get game stats
        stats = api.get_game_stats()
        if stats:
            print(f"Game mode: {stats.get('gameMode')}")
            print(f"Game time: {stats.get('gameTime'):.1f}s")
    else:
        print("❌ No active League of Legends game detected")
        print("Start a game (Practice Tool, Custom, or any game mode) and run this script again")
        print("Make sure the game client is running and you're in an active game")
