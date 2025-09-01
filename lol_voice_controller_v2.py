#!/usr/bin/env python3
"""
League of Legends Voice Controller v2.0
Automated champion detection and dynamic voice recognition
"""

import pynput
from pynput import keyboard, mouse
import threading
import time
import sys
import queue
import difflib
from typing import Dict, List, Optional, Tuple
import json
import pyperclip
import pyaudio
import os



from lol_data_manager import LoLDataManager
from lol_game_client_api import LoLGameClientAPI

class LoLVoiceControllerV2:
    def __init__(self, language='pl_PL', speech_engine='vosk'):
        self.keyboard_controller = pynput.keyboard.Controller()
        self.mouse_controller = pynput.mouse.Controller()
        self.data_manager = LoLDataManager(language)
        self.game_api = LoLGameClientAPI()
        
        self.is_listening = False
        self.current_champion = None
        self.current_mappings = {}
        self.recognition_accuracy = 0.85  # Increased accuracy with Vosk
        self.language = language
        self.speech_engine = speech_engine
        
        self.combo_queue = []
        self.combo_timeout = 3.0
        self.last_combo_time = 0
        
        self.keybinds = {
            'Q': 'q', 'W': 'w', 'E': 'e', 'R': 'r',
            'Flash': 'f', 'Summoner2': 'd'
        }
        
        # Audio settings - optimized for speed
        self.audio_format = pyaudio.paInt16
        self.channels = 1
        self.rate = 8000  # Reduced sample rate for faster processing
        self.chunk = 256   # Even smaller chunks for ultra-low latency
        self.audio = None
        self.stream = None
        
        # Speech recognition component
        self.speech_recognizer = None
        
        # Audio buffer for Vosk processing
        self.audio_buffer = []
        self.buffer_size = 4  # Process 4 chunks at once for better accuracy
        
        # Command cache for faster response
        self.command_cache = {}
        self.cache_hits = 0
        
        self.debug = True
        self.default_mappings = {}
        
        self._init_speech_recognition()
        self._generate_default_mappings()
        self._update_champion()
    
    def _init_speech_recognition(self):
        """Initialize speech recognition using speech_recognition library"""
        try:
            print(f"🔧 Initializing speech recognition for engine: {self.speech_engine}")
            
            import speech_recognition as sr
            self.speech_recognizer = sr.Recognizer()
            
            # Optimize for speed
            self.speech_recognizer.energy_threshold = 300
            self.speech_recognizer.pause_threshold = 0.3
            self.speech_recognizer.phrase_threshold = 0.3
            self.speech_recognizer.non_speaking_duration = 0.3
            
            print(f"✅ Speech Recognition initialized with engine: {self.speech_engine}")
            
            # Initialize audio stream
            print("🔧 Initializing audio stream...")
            self._init_audio()
            
            print(f"✅ Speech recognition fully initialized for {self.speech_engine}")
        except Exception as e:
            print(f"❌ Error initializing speech recognition: {e}")
            import traceback
            traceback.print_exc()
            print("❌ No speech recognition available")
    
    def _generate_default_mappings(self):
        flash_key = self.keybinds.get('Flash', 'f')
        summ2_key = self.keybinds.get('Summoner2', 'd')
        
        self.default_mappings = {
            'flash': flash_key, 'flasz': flash_key, 'błysk': flash_key, 'blysk': flash_key,
            'flas': flash_key, 'fla': flash_key, 'błys': flash_key, 'blys': flash_key,
            'flash me': flash_key, 'flash now': flash_key, 'flash teraz': flash_key,
            
            'heal': summ2_key, 'leczenie': summ2_key, 'heal me': summ2_key, 'heal up': summ2_key,
            'barrier': summ2_key, 'bariera': summ2_key, 'shield': summ2_key, 'tarcza': summ2_key,
            'cleanse': summ2_key, 'oczyszczenie': summ2_key, 'clean': summ2_key, 'cleanse me': summ2_key,
            'ignite': summ2_key, 'podpalenie': summ2_key, 'ignite him': summ2_key, 'ignite enemy': summ2_key,
            'exhaust': summ2_key, 'wyczerpanie': summ2_key, 'exhaust enemy': summ2_key,
            'ghost': summ2_key, 'duch': summ2_key, 'ghost speed': summ2_key,
            'teleport': summ2_key, 'teleportacja': summ2_key, 'tp': summ2_key, 'teleport me': summ2_key,
            'smite': summ2_key, 'karanie': summ2_key, 'smite monster': summ2_key,
            
            'attack': 'right_click', 'atak': 'right_click', 'auto': 'right_click', 'auto attack': 'right_click',
            'attack move': 'right_click', 'attack enemy': 'right_click', 'hit': 'right_click',
            'stop': 's', 'zatrzymaj': 's', 'halt': 's', 'stop moving': 's',
            'back': 'b', 'recall': 'b', 'base': 'b', 'baza': 'b', 
            'wracaj': 'b', 'powrót': 'b', 'powrot': 'b', 'go back': 'b',
            'shop': 'p', 'sklep': 'p', 'buy': 'p', 'kup': 'p', 'open shop': 'p',
            
            'znajdź': 'item_search', 'znajdz': 'item_search', 'find': 'item_search',
            'szukaj': 'item_search', 'search': 'item_search',
            
            'combo': 'combo', 'kombinacja': 'combo', 'sekwencja': 'combo',
            'chain': 'combo', 'combo q w e': 'combo', 'combo q w e r': 'combo',
            'and': 'combo', 'i': 'combo'
        }
    
    def _init_audio(self):
        """Initialize audio stream for speech recognition"""
        try:
            self.audio = pyaudio.PyAudio()
            self.stream = self.audio.open(
                format=self.audio_format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk
            )
            print("✅ Audio stream initialized")
        except Exception as e:
            print(f"❌ Error initializing audio: {e}")
    
    def _init_vosk_model(self):
        """Initialize Vosk speech recognition model"""
        try:
            # Check if Vosk model exists
            model_paths = [
                "vosk-model-small-pl-0.22",  # Polish small model
                "vosk-model-small-en-us-0.15",  # English small model
                "vosk-model-pl-0.22",  # Polish full model
                "vosk-model-en-us-0.22"  # English full model
            ]
            
            model_path = None
            for path in model_paths:
                if os.path.exists(path):
                    model_path = path
                    break
            
            if not model_path:
                print("❌ No Vosk model found")
                return False
            
            print(f"✅ Vosk model found: {model_path}")
            return True
        except Exception as e:
            print(f"❌ Error checking Vosk model: {e}")
            return False
    
    def _update_champion(self):
        if self.game_api.is_game_active():
            game_data = self.game_api.get_champion_and_summoner_spells()
            new_champion = game_data.get('champion')
            
            if new_champion and new_champion != self.current_champion:
                self.current_champion = new_champion
                self._load_champion_mappings()
                
                if self.debug:
                    print(f"🎯 Champion detected: {self.current_champion}")
                    print(f"📊 Loaded {len(self.current_mappings)} voice commands")
                
                return True
        else:
            if self.current_champion:
                self.current_champion = None
                self.current_mappings = {}
                if self.debug:
                    print("🔴 Game not active - using default mappings only")
        
        return False
    
    def _load_champion_mappings(self):
        if not self.current_champion:
            self.current_mappings = {}
            return
        
        champion_mappings = self.data_manager.create_voice_mappings(
            self.current_champion, 
            self.keybinds
        )
        
        self.current_mappings = {**champion_mappings, **self.default_mappings}
        
        self.recognition_accuracy = self.data_manager.suggest_recognition_accuracy(
            self.current_champion
        )
        
        if self.debug:
            abilities = self.data_manager.get_champion_abilities(self.current_champion)
            print(f"🎮 {self.current_champion} abilities:")
            for key, name in abilities.items():
                if key != 'passive':
                    keybind = self.keybinds.get(key, key.lower())
                    print(f"   {key}: '{name}' -> {keybind}")
            print(f"🎯 Recognition accuracy: {self.recognition_accuracy:.2f}")
    
    def normalize_text(self, text: str) -> str:
        text = text.lower().strip()
        replacements = {
            'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l',
            'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z'
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text
    
    def press_key(self, key: str):
        try:
            if key == 'right_click':
                self.mouse_controller.click(mouse.Button.right, 1)
                if self.debug:
                    print("🖱️ RIGHT CLICK")
                return
            
            # Optimized key press for faster execution
            if '+' in key:
                keys = key.split('+')
                from pynput.keyboard import Key
                key_objects = []
                for k in keys:
                    k = k.strip()
                    if k == 'ctrl':
                        key_objects.append(Key.ctrl)
                    elif k == 'alt':
                        key_objects.append(Key.alt)
                    elif k == 'shift':
                        key_objects.append(Key.shift)
                    elif k == 'cmd' or k == 'win':
                        key_objects.append(Key.cmd)
                    else:
                        key_objects.append(k)
                
                # Faster key combination execution
                for k in key_objects:
                    self.keyboard_controller.press(k)
                for k in reversed(key_objects):
                    self.keyboard_controller.release(k)
            else:
                # Single key press - optimized
                self.keyboard_controller.press(key)
                self.keyboard_controller.release(key)
            
            if self.debug:
                print(f"⚡ {key.upper()}")
        except Exception as e:
            print(f"❌ Key press error for {key}: {e}")
    
    def _paste_text(self, text: str):
        try:
            pyperclip.copy(text)
            self.press_key('ctrl+v')
            if self.debug:
                print(f"📋 Pasted: '{text}'")
        except Exception as e:
            print(f"❌ Paste error: {e}")
    
    def _click_search_field(self):
        try:
            x, y = 400, 200
            self.mouse_controller.position = (x, y)
            self.mouse_controller.click(mouse.Button.left, 1)
            if self.debug:
                print(f"🖱️ Clicked search field at ({x}, {y})")
        except Exception as e:
            print(f"❌ Click error: {e}")
    
    def _right_click_buy(self):
        try:
            x, y = 500, 300
            self.mouse_controller.position = (x, y)
            self.mouse_controller.click(mouse.Button.right, 1)
            if self.debug:
                print(f"🛒 Right clicked to buy at ({x}, {y})")
        except Exception as e:
            print(f"❌ Right click error: {e}")
    
    def find_best_match(self, command: str) -> Optional[Tuple[str, str, float]]:
        normalized_command = self.normalize_text(command)
        mappings = self.current_mappings if self.current_mappings else self.default_mappings
        
        matches = []
        command_words = normalized_command.split()
        
        for phrase, key in mappings.items():
            if phrase == normalized_command:
                priority = len(phrase) * 10 + 100
                matches.append((phrase, key, priority))
                continue
            
            if phrase in normalized_command:
                priority = len(phrase) * 8
                matches.append((phrase, key, priority))
                continue
            
            phrase_words = phrase.split()
            for phrase_word in phrase_words:
                for command_word in command_words:
                    min_length = 3 if len(phrase_word) <= 4 else 4
                    
                    if len(phrase_word) >= 3 and len(command_word) >= min_length:
                        similarity = difflib.SequenceMatcher(
                            None, phrase_word, command_word
                        ).ratio()
                        
                        threshold = 0.8 if len(phrase_word) <= 4 else self.recognition_accuracy
                        
                        if similarity >= threshold:
                            if len(phrase_word) <= 4 and similarity >= 0.9:
                                priority = similarity * len(phrase) + len(phrase_word) + 20
                            else:
                                priority = similarity * len(phrase) + len(phrase_word)
                            matches.append((phrase, key, priority))
        
        if matches:
            matches.sort(key=lambda x: x[2], reverse=True)
            return matches[0]
        
        return None
    
    def process_voice_command(self, command: str) -> bool:
        if self.debug:
            print(f"🔍 Processing: '{command}'")
        
        # Quick check for common commands first (faster response)
        normalized_command = self.normalize_text(command)
        
        # Check command cache first (fastest response)
        if normalized_command in self.command_cache:
            key = self.command_cache[normalized_command]
            self.cache_hits += 1
            if self.debug:
                print(f"🚀 Cache hit: '{normalized_command}' -> {key}")
            self.press_key(key)
            return True
        
        # Direct mapping lookup for speed
        if normalized_command in self.current_mappings:
            key = self.current_mappings[normalized_command]
            # Cache this result for next time
            self.command_cache[normalized_command] = key
            if self.debug:
                print(f"⚡ Direct match: '{normalized_command}' -> {key}")
            self.press_key(key)
            return True
        
        # Fallback to full processing
        self._update_champion()
        
        if self._handle_item_search(command):
            return True
        
        if self._handle_combo_command(command):
            return True
        
        match = self.find_best_match(command)
        
        if match:
            phrase, key, confidence = match
            # Cache this result for next time
            self.command_cache[normalized_command] = key
            if self.debug:
                print(f"✅ Match: '{phrase}' -> {key} (score: {confidence:.2f})")
            
            if key == 'item_search':
                return False
            else:
                self.press_key(key)
                return True
        
        if self.debug:
            print("❌ No match found")
        return False
    
    def _handle_item_search(self, command: str) -> bool:
        normalized_command = self.normalize_text(command)
        
        search_patterns = [
            'znajdź ', 'znajdz ', 'find ', 'szukaj ', 'search '
        ]
        
        item_name = None
        for pattern in search_patterns:
            if normalized_command.startswith(pattern):
                item_name = normalized_command[len(pattern):].strip()
                break
        
        if item_name:
            if self.debug:
                print(f"🔍 Searching for item: '{item_name}'")
            
            matches = self.data_manager.search_items(item_name)
            if matches:
                best_item = matches[0]
                if self.debug:
                    print(f"🛒 Found item: '{best_item[0]}' (ID: {best_item[1]})")
                
                self.press_key('p')
                time.sleep(0.5)
                
                self._click_search_field()
                time.sleep(0.2)
                
                # Clear search field and type item name manually
                self.press_key('ctrl+a')
                time.sleep(0.1)
                
                # Type item name character by character (more reliable than copy/paste)
                self._type_text_manually(best_item[0])
                time.sleep(0.3)
                
                self._right_click_buy()
                
                return True
            else:
                if self.debug:
                    print(f"❌ No items found for: '{item_name}'")
        
        return False
    
    def _handle_combo_command(self, command: str) -> bool:
        normalized_command = self.normalize_text(command)
        current_time = time.time()
        
        # Check for two abilities in one command (e.g., "q and w", "q i w", "q w")
        if 'and' in normalized_command or 'i' in normalized_command or self._has_two_abilities(normalized_command):
            abilities = self._extract_abilities_from_combo(normalized_command)
            if len(abilities) >= 2:
                if self.debug:
                    print(f"🎯 Two abilities detected: {abilities}")
                self._execute_combo(abilities)
                return True
            elif len(abilities) == 1:
                # Single ability found, execute it
                if self.debug:
                    print(f"⚡ Single ability: {abilities[0]}")
                self.press_key(abilities[0])
                return True
        
        # Check for combo queue (time-based)
        match = self.find_best_match(command)
        if match:
            phrase, key, confidence = match
            if key.lower() in ['q', 'w', 'e', 'r'] and key != 'combo':
                if current_time - self.last_combo_time < self.combo_timeout:
                    self.combo_queue.append(key)
                    if self.debug:
                        print(f"🔗 Added to combo: {key} (queue: {self.combo_queue})")
                    
                    self.press_key(key)
                    self.last_combo_time = current_time
                    
                    if len(self.combo_queue) >= 3:
                        self._execute_combo_queue()
                    
                    return True
                else:
                    self.combo_queue = []
                    self.last_combo_time = current_time
        
        return False
    
    def _extract_abilities_from_combo(self, command: str) -> List[str]:
        abilities = []
        command_lower = command.lower()
        
        # Remove combo keywords
        for keyword in ['combo', 'kombinacja', 'sekwencja', 'chain', 'then', 'potem', 'następnie']:
            command_lower = command_lower.replace(keyword, '')
        
        # First check for ability names in champion abilities
        if self.current_champion:
            champ_abilities = self.data_manager.get_champion_abilities(self.current_champion)
            for key, ability_name in champ_abilities.items():
                if key != 'passive':
                    ability_lower = ability_name.lower()
                    if ability_lower in command_lower:
                        abilities.append(key.lower())
        
        # Then check for direct Q W E R keys
        for key in ['q', 'w', 'e', 'r']:
            if f' {key} ' in f' {command_lower} ' or command_lower.startswith(f'{key} ') or command_lower.endswith(f' {key}'):
                if key not in abilities:
                    abilities.append(key)
        
        # Check for two abilities mentioned together (e.g., "q and w", "q i w")
        if len(abilities) >= 2:
            # Sort abilities in Q W E R order for consistent execution
            ability_order = {'q': 0, 'w': 1, 'e': 2, 'r': 3}
            abilities.sort(key=lambda x: ability_order.get(x, 4))
        
        return abilities
    
    def _has_two_abilities(self, command: str) -> bool:
        """Check if command contains two ability references"""
        ability_count = 0
        command_lower = command.lower()
        
        # Count Q W E R mentions
        for key in ['q', 'w', 'e', 'r']:
            if f' {key} ' in f' {command_lower} ' or command_lower.startswith(f'{key} ') or command_lower.endswith(f' {key}'):
                ability_count += 1
        
        # Count ability names if champion is known
        if self.current_champion:
            champ_abilities = self.data_manager.get_champion_abilities(self.current_champion)
            for key, ability_name in champ_abilities.items():
                if key != 'passive':
                    ability_lower = ability_name.lower()
                    if ability_lower in command_lower:
                        ability_count += 1
        
        return ability_count >= 2
    
    def _execute_combo(self, abilities: List[str]):
        if self.debug:
            print(f"🎯 Executing combo: {' -> '.join(abilities)}")
        
        for i, ability in enumerate(abilities):
            if i > 0:
                time.sleep(0.3)
            self.press_key(ability)
    
    def _execute_combo_queue(self):
        if self.combo_queue:
            if self.debug:
                print(f"🎯 Executing combo queue: {' -> '.join(self.combo_queue)}")
            
            for ability in self.combo_queue[1:]:
                time.sleep(0.3)
                self.press_key(ability)
            
            self.combo_queue = []
    
    def listen_continuously(self):
        while self.is_listening:
            if self.audio is None or self.stream is None:
                time.sleep(0.05)  # Reduced sleep for faster response
                continue
            
            # Read audio data from the stream
            audio_data = self.stream.read(self.chunk, exception_on_overflow=False)
            
            # Process audio with speech_recognition library
            self._process_audio_with_speech_recognition(audio_data)
    
    def _process_audio_with_speech_recognition(self, audio_data):
        """Process audio using speech_recognition library with selected engine"""
        try:
            import speech_recognition as sr
            
            # Convert audio data to AudioData format
            audio = sr.AudioData(audio_data, self.rate, 2)
            
            # Debug current engine
            if hasattr(self, 'speech_engine'):
                print(f"🔍 Processing audio with engine: {self.speech_engine}")
            else:
                print("❌ speech_engine attribute not found!")
                return
            
            # Process based on selected engine
            if self.speech_engine == 'vosk':
                try:
                    print("🔍 Using Vosk recognition...")
                    command = self.speech_recognizer.recognize_vosk(audio)
                    if command:
                        # Extract text from Vosk result
                        import json
                        result = json.loads(command)
                        command_text = result.get('text', '').strip()
                        if command_text:
                            self.process_voice_command(command_text)
                except json.JSONDecodeError:
                    print("❌ Invalid Vosk result format")
                except Exception as e:
                    print(f"❌ Vosk error: {e}")
            
            elif self.speech_engine == 'speech_recognition':
                # Google Speech Recognition (ultra fast)
                try:
                    print("🔍 Using Google Speech Recognition...")
                    command = self.speech_recognizer.recognize_google(audio, language=self.language)
                    if command.strip():
                        self.process_voice_command(command)
                except Exception as e:
                    print(f"❌ Google Speech Recognition error: {e}")
            
            elif self.speech_engine == 'whisper':
                # Whisper (fast and accurate)
                try:
                    print("🔍 Using Whisper recognition...")
                    command = self.speech_recognizer.recognize_whisper(audio, language=self.language[:2])
                    if command.strip():
                        self.process_voice_command(command)
                except Exception as e:
                    print(f"❌ Whisper error: {e}")
            
            else:
                print(f"❌ Unknown speech engine: {self.speech_engine}")
            
        except sr.UnknownValueError:
            pass  # No speech detected
        except sr.RequestError as e:
            print(f"❌ Speech recognition error: {e}")
        except Exception as e:
            print(f"❌ Audio processing error: {e}")
            import traceback
            traceback.print_exc()
    
    def _process_audio_async(self, audio):
        """Legacy method - no longer used with Vosk"""
        pass
    
    def start_listening(self):
        if self.is_listening:
            print("⚡ Already listening!")
            return
        
        self.is_listening = True
        self.listen_thread = threading.Thread(target=self.listen_continuously, daemon=True)
        self.listen_thread.start()
        
        print("🎯 LoL Voice Controller v2.0 Active!")
        print("🤖 Automatic champion detection enabled")
        print("🧠 Dynamic voice recognition with ability prioritization")
        
        if self.current_champion:
            abilities = self.data_manager.get_champion_abilities(self.current_champion)
            print(f"\n🎮 Current Champion: {self.current_champion}")
            for key, name in abilities.items():
                if key != 'passive':
                    keybind = self.keybinds.get(key, key.lower())
                    print(f"   {key}: '{name}' -> {keybind}")
        else:
            print("\n⚠️  No active game detected - using default mappings")
        
        print(f"\n🎯 Recognition accuracy: {self.recognition_accuracy:.0%}")
        print("💡 Say ability names naturally - algorithm will find the best match!")
    
    def stop_listening(self):
        self.is_listening = False
        if hasattr(self, 'listen_thread'):
            self.listen_thread.join(timeout=1)
        print("🔴 Voice recognition stopped")
    
    def test_microphone(self):
        if self.audio is None or self.stream is None:
            return
                
        # Read audio data from the stream
        audio_data = self.stream.read(self.chunk, exception_on_overflow=False)
        
        # Process audio data with Vosk
        if self.vosk_recognizer:
            if self.vosk_recognizer.AcceptWaveform(audio_data):
                final_result = self.vosk_recognizer.FinalResult()
                if final_result:
                    command = json.loads(final_result)['text']
                    if command.strip():
                        self.process_voice_command(command)
    
    def toggle_debug(self):
        self.debug = not self.debug
        status = "ON" if self.debug else "OFF"
        print(f"🐛 Debug mode: {status}")
    
    def update_keybinds(self, new_keybinds: Dict[str, str]):
        # Safely update keybinds
        try:
            self.keybinds.update(new_keybinds)
            self._generate_default_mappings()
            if self.current_champion:
                self._load_champion_mappings()
            print(f"⚙️  Keybinds updated: {new_keybinds}")
        except Exception as e:
            print(f"❌ Error updating keybinds: {e}")
            # Fallback to safe values
            self.keybinds = {
                'Q': 'q', 'W': 'w', 'E': 'e', 'R': 'r',
                'Flash': 'f', 'Summoner2': 'd'
            }
            self._generate_default_mappings()
    
    def get_status(self) -> Dict:
        return {
            'listening': self.is_listening,
            'champion': self.current_champion,
            'game_active': self.game_api.is_game_active(),
            'mappings_count': len(self.current_mappings),
            'accuracy': self.recognition_accuracy,
            'language': self.language,
            'cache_hits': self.cache_hits,
            'cache_size': len(self.command_cache)
        }
    
    def change_language(self, new_language: str):
        if self.data_manager.change_language(new_language):
            self.language = new_language
            self._update_champion()
            print(f"🌍 Language changed to: {new_language}")
            return True
        return False
    
    def change_speech_engine(self, new_engine: str):
        """Change speech recognition engine on the fly"""
        try:
            print(f"🔄 Starting speech engine change to: {new_engine}")
            
            if self.is_listening:
                print("🛑 Stopping current listening...")
                self.stop_listening()
            
            print(f"🔧 Updating speech_engine attribute from '{self.speech_engine}' to '{new_engine}'")
            self.speech_engine = new_engine
            
            print(f"🔧 Speech engine changed to: {new_engine}")
            
            # Reinitialize speech recognition with new engine
            print("🔄 Reinitializing speech recognition...")
            self._init_speech_recognition()
            
            print(f"✅ Speech recognition reinitialized with {new_engine}")
            return True
        except Exception as e:
            print(f"❌ Error changing speech engine: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # GUI required methods
    def get_current_champion(self) -> Optional[str]:
        """Get the current champion name for GUI display"""
        return self.current_champion
    
    def get_champion_abilities(self) -> Dict[str, str]:
        """Get current champion abilities for GUI display"""
        if not self.current_champion:
            return {}
        return self.data_manager.get_champion_abilities(self.current_champion)
    
    def get_command_count(self) -> int:
        """Get total number of available voice commands"""
        return len(self.current_mappings)
    
    def is_game_running(self) -> bool:
        """Check if game is currently running"""
        return self.game_api.is_game_active()
    
    def update_champion_data(self):
        """Update champion data - called from GUI"""
        return self._update_champion()

def main():
    print("🎯 === League of Legends Voice Controller v2.0 === 🎯")
    print("🤖 Automatic champion detection and dynamic voice recognition")
    print("Commands: Enter=Start/Stop | 't'=Test | 'd'=Debug | 'u'=Update | 'q'=Quit")
    
    controller = LoLVoiceControllerV2()
    
    try:
        while True:
            user_input = input("\n>>> ").strip().lower()
            
            if user_input == 'q':
                break
            elif user_input == '':
                if not controller.is_listening:
                    controller.start_listening()
                else:
                    controller.stop_listening()
            elif user_input == 't':
                controller.test_microphone()
            elif user_input == 'd':
                controller.toggle_debug()
            elif user_input == 'u':
                controller._update_champion()
                print("🔄 Champion detection updated")
            elif user_input == 's':
                status = controller.get_status()
                print(f"📊 Status: {json.dumps(status, indent=2)}")
            else:
                print("Commands: Enter=Start/Stop | 't'=Test | 'd'=Debug | 'u'=Update | 's'=Status | 'q'=Quit")
    
    except KeyboardInterrupt:
        print("\n🔴 Interrupted!")
    
    finally:
        controller.stop_listening()
        print("🔴 Voice Controller stopped.")

if __name__ == "__main__":
    main()
