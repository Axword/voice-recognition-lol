#!/usr/bin/env python3
"""
League of Legends Data Manager
Fetches and manages champion data, ability names, and voice recognition mappings
"""

import os
import json
import requests
from typing import Dict, List, Tuple, Optional
import difflib
from datetime import datetime, timedelta

TRANSLATOR_AVAILABLE = False

class LoLDataManager:
    def __init__(self, language='pl_PL'):
        self.language = language
        self.cache_dir = 'cache'
        self.version_dir = os.path.join(self.cache_dir, self.language)
        self.latest_version = None
        self.champions_data = {}
        self.items_data = {}
        self.cache_metadata = {}
        self.metadata_file = os.path.join(self.cache_dir, 'metadata.json')
        
        os.makedirs(self.version_dir, exist_ok=True)
        self._load_cache_metadata()
    
    def _load_cache_metadata(self):
        try:
            if os.path.exists(self.metadata_file):
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    self.cache_metadata = json.load(f)
        except Exception:
            self.cache_metadata = {}
    
    def _save_cache_metadata(self):
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache_metadata, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def _is_cache_outdated(self, cache_key: str, max_age_hours: int = 24) -> bool:
        if cache_key not in self.cache_metadata:
            return True
        
        last_update = datetime.fromisoformat(self.cache_metadata[cache_key]['last_update'])
        return datetime.now() - last_update > timedelta(hours=max_age_hours)
    
    def _update_cache_metadata(self, cache_key: str, version: str):
        self.cache_metadata[cache_key] = {
            'version': version,
            'last_update': datetime.now().isoformat()
        }
        self._save_cache_metadata()
    
    def get_latest_version(self) -> str:
        if not self.latest_version:
            try:
                response = requests.get("https://ddragon.leagueoflegends.com/api/versions.json", timeout=10)
                self.latest_version = response.json()[0]
            except Exception:
                self.latest_version = "14.1.1"
        return self.latest_version
    
    def fetch_champion_data(self, force_update=False) -> Dict:
        version = self.get_latest_version()
        data_path = os.path.join(self.version_dir, "championFull.json")
        cache_key = f"champions_{self.language}"
        
        if (os.path.exists(data_path) and not force_update and 
            not self._is_cache_outdated(cache_key)):
            try:
                with open(data_path, 'r', encoding='utf-8') as f:
                    self.champions_data = json.load(f)
                print(f"Loaded {len(self.champions_data)} champions from cache")
                return self.champions_data
            except Exception:
                pass
        
        try:
            url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/{self.language}/championFull.json"
            print(f"Fetching champion data from: {url}")
            response = requests.get(url, timeout=30)
            data = response.json()['data']
            
            with open(data_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.champions_data = data
            self._update_cache_metadata(cache_key, version)
            print(f"Fetched and cached {len(self.champions_data)} champions")
            return self.champions_data
            
        except Exception as e:
            print(f"Error fetching champion data: {e}")
            return {}
    
    def get_champion_abilities(self, champion_name: str) -> Dict:
        if not self.champions_data:
            self.fetch_champion_data()
        
        champion_data = self.champions_data.get(champion_name)
        if not champion_data:
            return {}
        
        return {
            'passive': champion_data['passive']['name'],
            'Q': champion_data['spells'][0]['name'],
            'W': champion_data['spells'][1]['name'],
            'E': champion_data['spells'][2]['name'],
            'R': champion_data['spells'][3]['name']
        }
    
    def get_champion_sub_abilities(self, champion_name: str) -> Dict[str, List[str]]:
        if not self.champions_data:
            self.fetch_champion_data()
        
        champion_data = self.champions_data.get(champion_name)
        if not champion_data:
            return {}
        
        sub_abilities = {}
        
        for i, spell in enumerate(champion_data['spells']):
            key = ['Q', 'W', 'E', 'R'][i]
            sub_abilities[key] = []
            
            if 'leveltip' in spell and 'label' in spell['leveltip']:
                for label in spell['leveltip']['label']:
                    if '<spellName>' in label and '</spellName>' in label:
                        start = label.find('<spellName>') + len('<spellName>')
                        end = label.find('</spellName>')
                        if start < end:
                            sub_ability_name = label[start:end].strip()
                            if sub_ability_name and sub_ability_name not in sub_abilities[key]:
                                sub_abilities[key].append(sub_ability_name)
        
        return sub_abilities
    
    def get_hwei_sub_ability_mappings(self) -> Dict[str, str]:
        hwei_sub_mappings = {}
        
        sub_abilities = self.get_champion_sub_abilities('Hwei')
        if not sub_abilities:
            return {}
        
        key_order = ['q', 'w', 'e']
        
        for theme_key, abilities in sub_abilities.items():
            if theme_key in ['Q', 'W', 'E'] and abilities:
                for i, ability in enumerate(abilities):
                    if i < len(key_order):
                        hwei_sub_mappings[ability.lower()] = key_order[i]
        
        hwei_sub_mappings.update({
            'spirala rozpaczy': 'r',
            'czyszczenie pędzla': 'r',
            'clear brush': 'r',
            'brush clear': 'r'
        })
        
        return hwei_sub_mappings
    
    def create_voice_mappings(self, champion_name: str, keybinds: Dict = None) -> Dict[str, str]:
        if keybinds is None:
            keybinds = {'Q': 'q', 'W': 'w', 'E': 'e', ' ': 'r', 'Flash': 'f', 'Summoner2': 'd'}
        
        abilities = self.get_champion_abilities(champion_name)
        if not abilities:
            return {}
        
        mappings = {}
        sub_abilities = self.get_champion_sub_abilities(champion_name)
        
        for ability_key, ability_name in abilities.items():
            if ability_key == 'passive':
                continue
                
            key_binding = keybinds.get(ability_key, ability_key.lower())
            mappings[ability_name.lower()] = key_binding
            
            variations = self._generate_ability_variations(ability_name)
            for variation in variations:
                mappings[variation] = key_binding
            
            if ability_key in sub_abilities and sub_abilities[ability_key]:
                if champion_name.lower() == 'hwei':
                    hwei_mappings = self.get_hwei_sub_ability_mappings()
                    for sub_ability in sub_abilities[ability_key]:
                        sub_key = hwei_mappings.get(sub_ability.lower(), key_binding)
                        mappings[sub_ability.lower()] = sub_key
                        
                        sub_variations = self._generate_ability_variations(sub_ability)
                        for variation in sub_variations:
                            if variation not in mappings:
                                mappings[variation] = sub_key
                else:
                    for sub_ability in sub_abilities[ability_key]:
                        mappings[sub_ability.lower()] = key_binding
                        
                        sub_variations = self._generate_ability_variations(sub_ability)
                        for variation in sub_variations:
                            if variation not in mappings:
                                mappings[variation] = key_binding
        
        return mappings
    
    def _generate_ability_variations(self, ability_name: str) -> List[str]:
        variations = []
        name_lower = ability_name.lower()
        
        diacritic_map = {
            'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 
            'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z'
        }
        
        normalized_name = name_lower
        for old, new in diacritic_map.items():
            normalized_name = normalized_name.replace(old, new)
        
        variations.append(normalized_name)
        
        words = normalized_name.split()
        
        if len(words) > 1:
            for word in words:
                if len(word) >= 4:
                    variations.append(word)
            
            for i in range(len(words)):
                for j in range(i + 1, len(words) + 1):
                    phrase = ' '.join(words[i:j])
                    if len(phrase) >= 4:
                        variations.append(phrase)
        
        unique_variations = []
        for var in variations:
            if var not in unique_variations:
                unique_variations.append(var)
        
        return unique_variations
    
    def get_ability_priority_score(self, ability_name: str) -> float:
        base_score = len(ability_name)
        word_count = len(ability_name.split())
        if word_count > 1:
            base_score += word_count * 2
        return base_score
    
    def find_similar_abilities(self, champion_name: str, threshold: float = 0.6) -> List[Tuple[str, str, float]]:
        abilities = self.get_champion_abilities(champion_name)
        if not abilities:
            return []
        
        similar_pairs = []
        ability_list = [(k, v) for k, v in abilities.items() if k != 'passive']
        
        for i, (key1, name1) in enumerate(ability_list):
            for key2, name2 in ability_list[i+1:]:
                similarity = difflib.SequenceMatcher(None, name1.lower(), name2.lower()).ratio()
                if similarity >= threshold:
                    similar_pairs.append((name1, name2, similarity))
        
        return similar_pairs
    
    def suggest_recognition_accuracy(self, champion_name: str) -> float:
        similar_abilities = self.find_similar_abilities(champion_name, threshold=0.4)
        
        if not similar_abilities:
            return 0.5
        
        max_similarity = max(pair[2] for pair in similar_abilities)
        
        if max_similarity > 0.8:
            return 0.85
        elif max_similarity > 0.6:
            return 0.75
        else:
            return 0.70
    
    def get_all_champions(self) -> List[str]:
        if not self.champions_data:
            self.fetch_champion_data()
        return list(self.champions_data.keys())

    
    def fetch_items_data(self, force_update=False) -> Dict:
        version = self.get_latest_version()
        data_path = os.path.join(self.version_dir, "item.json")
        cache_key = f"items_{self.language}"
        
        if (os.path.exists(data_path) and not force_update and 
            not self._is_cache_outdated(cache_key)):
            try:
                with open(data_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        
        try:
            url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/{self.language}/item.json"
            print(f"Fetching items data from: {url}")
            response = requests.get(url, timeout=30)
            data = response.json()['data']
            
            with open(data_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self._update_cache_metadata(cache_key, version)
            print(f"Fetched and cached {len(data)} items")
            return data
            
        except Exception as e:
            print(f"Error fetching items data: {e}")
            return {}
    
    def search_items(self, query: str) -> List[Tuple[str, str, float]]:
        items_data = self.fetch_items_data()
        if not items_data:
            return []
        
        matches = []
        query_lower = query.lower()
        
        for item_id, item_data in items_data.items():
            item_name = item_data.get('name', '')
            if not item_name:
                continue
            
            if not item_data.get('maps', {}).get('11', False):
                continue
            
            if query_lower == item_name.lower():
                matches.append((item_name, item_id, 1.0))
                continue
            
            if item_name.lower().startswith(query_lower):
                matches.append((item_name, item_id, 0.9))
                continue
            
            if query_lower in item_name.lower():
                matches.append((item_name, item_id, 0.8))
                continue
            
            similarity = difflib.SequenceMatcher(None, query_lower, item_name.lower()).ratio()
            if similarity >= 0.6:
                matches.append((item_name, item_id, similarity))
        
        matches.sort(key=lambda x: x[2], reverse=True)
        return matches[:5]
    
    def get_supported_languages(self) -> List[str]:
        return [
            'en_US', 'pl_PL', 'de_DE', 'es_ES', 'fr_FR', 'it_IT', 
            'pt_BR', 'ru_RU', 'ko_KR', 'zh_CN', 'ja_JP', 'tr_TR'
        ]
    
    def change_language(self, new_language: str):
        if new_language in self.get_supported_languages():
            self.language = new_language
            self.version_dir = os.path.join(self.cache_dir, self.language)
            os.makedirs(self.version_dir, exist_ok=True)
            self.champions_data = {}
            self.items_data = {}
            return True
        return False
    
    def translate_text(self, text: str, target_language: str) -> str:
        """Translate text to target language using Google Translate"""
        if not TRANSLATOR_AVAILABLE:
            return text
        
        try:
            translator = Translator()
            result = translator.translate(text, dest=target_language)
            return result.text
        except Exception:
            return text
    
    def get_champion_abilities_translated(self, champion_name: str, target_language: str) -> Dict:
        """Get champion abilities in target language with translation fallback"""
        if target_language == self.language:
            return self.get_champion_abilities(champion_name)
        
        abilities = self.get_champion_abilities(champion_name)
        if not abilities:
            return {}
        
        translated_abilities = {}
        for key, name in abilities.items():
            if key == 'passive':
                translated_abilities[key] = name
                continue
            
            translated_name = self.translate_text(name, target_language)
            translated_abilities[key] = translated_name
        
        return translated_abilities
    
    def auto_update_data(self):
        """Automatically update champion and item data if outdated"""
        try:
            current_version = self.get_latest_version()
            cache_key = f"champions_{self.language}"
            
            if self._is_cache_outdated(cache_key, max_age_hours=6):
                print("🔄 Data is outdated, updating...")
                self.fetch_champion_data(force_update=True)
                self.fetch_items_data(force_update=True)
                print("✅ Data updated successfully")
                return True
            else:
                print("✅ Data is up to date")
                return False
        except Exception as e:
            print(f"❌ Auto-update failed: {e}")
            return False
