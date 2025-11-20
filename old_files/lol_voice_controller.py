#!/usr/bin/env python3
"""
League of Legends Voice Controller v0.2 (refactored)
Automated champion detection and dynamic voice recognition
"""

from __future__ import annotations
import os
import json
import logging
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import re
import difflib
import pyperclip
import speech_recognition as sr
from pynput import mouse
from pynput import keyboard as pyn_keyboard
from pynput.keyboard import Key

from game.lol_data_manager import LoLDataManager
from game.lol_game_client_api import LoLGameClientAPI
import random

@dataclass(frozen=True)
class ModelConfig:
    """Configuration of a speech recognition model."""
    name: str
    online: bool
    accuracy: float


@dataclass
class GUIStatus:
    """Runtime status data used by potential GUI or CLI display."""
    champion: Optional[str] = None
    model: str = "google"
    is_listening: bool = False
    last_command: Optional[str] = None
    last_update: Optional[str] = None


def now_str() -> str:
    """Return current time formatted as HH:MM:SS."""
    return time.strftime("%H:%M:%S")


def make_logger(debug: bool = True) -> logging.Logger:
    """Create and configure a logger with a simple console handler."""
    logger = logging.getLogger("LoLVoiceController")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False
    return logger



class LoLVoiceControllerV2:
    """League of Legends voice controller with automatic champion detection and dynamic speech recognition."""
    LISTEN_TIMEOUT = 0.1
    PHRASE_TIME_LIMIT = 0.5
    COMBO_TIMEOUT = 2.0

    SHOP_SEARCH_CLICK = (400, 200)
    SHOP_BUY_CLICK = (500, 300)

    _PL_TRANSLATION = str.maketrans(
        {"ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n", "ó": "o", "ś": "s", "ź": "z", "ż": "z"}
    )

    MODEL_CONFIGS: Dict[str, ModelConfig] = {
        "google": ModelConfig(name="Google Speech Recognition", online=True, accuracy=0.85),
        "sphinx": ModelConfig(name="CMU Sphinx", online=False, accuracy=0.65),
        "vosk": ModelConfig(name="Vosk", online=False, accuracy=0.75),
    }

    def __init__(
        self,
        language: str = "pl_PL",
        recognizer: Optional[sr.Recognizer] = None,
        keyboard_controller: Optional[pyn_keyboard.Controller] = None,
        mouse_controller: Optional[mouse.Controller] = None,
        data_manager: Optional[LoLDataManager] = None,
        game_api: Optional[LoLGameClientAPI] = None,
        debug: bool = True,
    ) -> None:
        """Initialize controller, devices, mappings and initial game state."""
        self.recognizer = recognizer or sr.Recognizer()
        self.keyboard_controller = keyboard_controller or pyn_keyboard.Controller()
        self.mouse_controller = mouse_controller or mouse.Controller()
        self.data_manager = data_manager or LoLDataManager(language)
        self.game_api = game_api or LoLGameClientAPI()

        self.is_listening = False
        self.current_champion: Optional[str] = None
        self.current_mappings: Dict[str, str] = {}
        self.recognition_accuracy: float = 0.70
        self.language = language

        self.recognition_model = "google"
        self.gui_status = GUIStatus(model=self.recognition_model)

        self.combo_queue: List[str] = []
        self.last_combo_time = 0.0

        self.keybinds: Dict[str, str] = {
            "Q": "q",
            "W": "w",
            "E": "e",
            "R": "r",
            "Flash": "f",
            "Summoner2": "d",
        }

        self.recognizer.energy_threshold = 100
        self.recognizer.dynamic_energy_threshold = False
        self.recognizer.pause_threshold = 0.12
        self.recognizer.phrase_threshold = 0.05
        self.recognizer.non_speaking_duration = 0.08

        self.debug = debug
        self.logger = make_logger(self.debug)

        self.microphone: Optional[sr.Microphone] = None
        self.default_mappings: Dict[str, str] = {}

        self._init_microphone()
        self._generate_default_mappings()
        self._update_champion()

        self._listen_thread: Optional[threading.Thread] = None
        self._vosk_model = None

    @property
    def lang_code(self) -> str:
        """Return language code compatible with Google recognizer."""
        return "pl-PL" if self.language == "pl_PL" else "en-US"

    def _init_microphone(self) -> None:
        """Initialize microphone device if available."""
        self.logger.info("Initializing microphone...")
        try:
            self.microphone = sr.Microphone(sample_rate=16000, chunk_size=1024)
            self.logger.info("✅ Microphone ready!")
        except Exception as exc:
            self.logger.warning(f"⚠️  Microphone issue: {exc}")
            self.logger.info("Using default settings...")
            self.microphone = None

    def _generate_default_mappings(self) -> None:
        """Generate default voice mappings independent of champion."""
        flash_key = self.keybinds.get("Flash", "f")
        summ2_key = self.keybinds.get("Summoner2", "d")

        self.default_mappings = {
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

    def _update_champion(self) -> bool:
        """Update currently detected champion and reload mappings."""
        if not self.game_api.is_game_active():
            if self.current_champion:
                self.current_champion = None
                self.current_mappings.clear()
                self.logger.info("🔴 Game not active - using default mappings only")
            return False

        game_data = self.game_api.get_champion_and_summoner_spells()
        new_champion = game_data.get("champion")
        if not new_champion or new_champion == self.current_champion:
            return False

        self.current_champion = new_champion
        self.gui_status.champion = new_champion
        self.gui_status.last_update = now_str()
        self._load_champion_mappings()

        self.logger.info(f"🎯 Champion detected: {self.current_champion}")
        self.logger.info(f"📊 Loaded {len(self.current_mappings)} voice commands")
        return True

    def _load_champion_mappings(self) -> None:
        """Load champion-specific mappings and adjust recognition accuracy."""
        if not self.current_champion:
            self.current_mappings = {}
            return

        champion_mappings = self.data_manager.create_voice_mappings(self.current_champion, self.keybinds)
        self.current_mappings = {**champion_mappings, **self.default_mappings}
        self.recognition_accuracy = self.data_manager.suggest_recognition_accuracy(self.current_champion)

        abilities = self.data_manager.get_champion_abilities(self.current_champion)
        self.logger.info(f"🎮 {self.current_champion} abilities:")
        for key, name in abilities.items():
            if key == "passive":
                continue
            keybind = self.keybinds.get(key, key.lower())
            self.logger.info(f"   {key}: '{name}' -> {keybind}")
        self.logger.info(f"🎯 Recognition accuracy: {self.recognition_accuracy:.2f}")

    def press_key(self, key: str) -> None:
        """Press a key or execute a mouse action."""
        try:
            if key == "right_click":
                self.mouse_controller.click(mouse.Button.right, 1)
                self.logger.debug("🖱️ RIGHT CLICK")
                return

            if "+" in key:
                keys = self._parse_hotkey(key)
                for k in keys:
                    self.keyboard_controller.press(k)
                for k in reversed(keys):
                    self.keyboard_controller.release(k)
            else:
                self.keyboard_controller.press(key)
                self.keyboard_controller.release(key)

            self.logger.debug(f"⚡ {key.upper()}")
        except Exception as exc:
            self.logger.error(f"❌ Key press error for {key}: {exc}")

    @staticmethod
    def _parse_hotkey(hotkey: str) -> List[object]:
        """Parse a hotkey string like 'ctrl+v' into pynput Key and str parts."""
        parts = [p.strip().lower() for p in hotkey.split("+") if p.strip()]
        mapping = {
            "ctrl": Key.ctrl,
            "alt": Key.alt,
            "shift": Key.shift,
            "cmd": Key.cmd,
            "win": Key.cmd,
        }
        result: List[object] = []
        for p in parts:
            result.append(mapping.get(p, p))
        return result

    def _paste_text(self, text: str) -> None:
        """Paste provided text via clipboard."""
        try:
            pyperclip.copy(text)
            self.press_key("ctrl+v")
            self.logger.debug(f"📋 Pasted: '{text}'")
        except Exception as exc:
            self.logger.error(f"❌ Paste error: {exc}")

    def _click_search_field(self) -> None:
        """Click the shop search field."""
        try:
            x, y = self.SHOP_SEARCH_CLICK
            self.mouse_controller.position = (x, y)
            self.mouse_controller.click(mouse.Button.left, 1)
            self.logger.debug(f"🖱️ Clicked search field at ({x}, {y})")
        except Exception as exc:
            self.logger.error(f"❌ Click error: {exc}")

    def _right_click_buy(self) -> None:
        """Perform a right-click to buy an item in the shop."""
        try:
            x, y = self.SHOP_BUY_CLICK
            self.mouse_controller.position = (x, y)
            self.mouse_controller.click(mouse.Button.right, 1)
            self.logger.debug(f"🛒 Right clicked to buy at ({x}, {y})")
        except Exception as exc:
            self.logger.error(f"❌ Right click error: {exc}")

    @staticmethod
    def _split_words(text: str) -> List[str]:
        """Split text into words and drop empty tokens."""
        return [w for w in text.split() if w]

    def normalize_text(self, text: str) -> str:
        """Normalize text for matching by lowercasing and removing diacritics."""
        return text.lower().strip().translate(self._PL_TRANSLATION)

    def find_best_match(self, command: str) -> Optional[Tuple[str, str, float]]:
        """Find the best matching mapping for recognized command."""
        normalized = self.normalize_text(command)
        mappings = self.current_mappings or self.default_mappings
        matches: List[Tuple[str, str, float]] = []

        if normalized in mappings:
            key = mappings[normalized]
            return normalized, key, 9999.0

        command_words = self._split_words(normalized)

        for phrase, key in mappings.items():
            if phrase == normalized:
                matches.append((phrase, key, len(phrase) * 10 + 100))
                continue

            if phrase in normalized:
                matches.append((phrase, key, len(phrase) * 8))
                continue

            phrase_words = self._split_words(phrase)
            for p_word in phrase_words:
                for c_word in command_words:
                    min_len = 3 if len(p_word) <= 4 else 4
                    if len(p_word) >= 3 and len(c_word) >= min_len:
                        sim = difflib.SequenceMatcher(None, p_word, c_word).ratio()
                        threshold = 0.8 if len(p_word) <= 4 else self.recognition_accuracy
                        if sim >= threshold:
                            base = sim * len(phrase) + len(p_word)
                            if len(p_word) <= 4 and sim >= 0.9:
                                base += 20
                            matches.append((phrase, key, base))

        if not matches:
            return None

        matches.sort(key=lambda x: x[2], reverse=True)
        return matches[0]

    def process_voice_command(self, command: str) -> bool:
        """Process a single recognized voice command."""
        self.logger.debug(f"🔍 Processing: '{command}'")
        self.gui_status.last_command = command

        self._update_champion()

        if self._handle_item_search(command):
            return True

        if self._handle_combo_command(command):
            return True

        match = self.find_best_match(command)
        if not match:
            self.logger.debug("❌ No match found")
            return False

        phrase, key, confidence = match
        self.logger.debug(f"✅ Match: '{phrase}' -> {key} (score: {confidence:.2f})")

        if key == "item_search":
            return False
        
        if key == "random_ability":
            choice = random.choice(["q", "w", "e"])
            self.logger.debug(f"🎲 Random ability -> {choice.upper()}")
            self.press_key(choice)
            return True
        self.press_key(key)
        return True

    def _handle_item_search(self, command: str) -> bool:
        """Handle item search command and perform shop actions."""
        normalized = self.normalize_text(command)
        prefixes = ("znajdź ", "znajdz ", "find ", "szukaj ", "search ")

        item_name = None
        for p in prefixes:
            if normalized.startswith(p):
                item_name = normalized[len(p):].strip()
                break

        if not item_name:
            return False

        self.logger.debug(f"🔍 Searching for item: '{item_name}'")
        matches = self.data_manager.search_items(item_name)
        if not matches:
            self.logger.debug(f"❌ No items found for: '{item_name}'")
            return False

        best_item = matches[0]
        self.logger.debug(f"🛒 Found item: '{best_item[0]}' (ID: {best_item[1]})")

        self.press_key("p")
        time.sleep(0.5)

        self._click_search_field()
        time.sleep(0.2)

        self.press_key("ctrl+a")
        time.sleep(0.1)
        self._paste_text(best_item[0])
        time.sleep(0.3)

        self._right_click_buy()
        return True
    
    def _handle_combo_command(self, command: str) -> bool:
        """Handle combo-style commands and queue abilities."""
        normalized = self.normalize_text(command)
        now = time.time()

        abilities_from_text = self._extract_abilities_from_combo(normalized)
        if len(abilities_from_text) >= 2:
            self.logger.debug(f"🎯 Ability chain detected: {abilities_from_text}")
            self._execute_combo(abilities_from_text, gap=0.1)
            return True

        if "and" in normalized or "i" in normalized:
            abilities = self._extract_abilities_from_combo(normalized)
            if abilities:
                self.logger.debug(f"🎯 Combo detected: {abilities}")
                self._execute_combo(abilities, gap=0.1)
                return True

        match = self.find_best_match(command)
        if not match:
            return False

        _, key, _ = match
        if key.lower() not in {"q", "w", "e", "r"} or key == "combo":
            return False

        if now - self.last_combo_time >= self.COMBO_TIMEOUT:
            self.combo_queue.clear()

        self.combo_queue.append(key)
        self.logger.debug(f"🔗 Added to combo: {key} (queue: {self.combo_queue})")

        self.press_key(key)
        self.last_combo_time = now

        if len(self.combo_queue) >= 3:
            self._execute_combo_queue(gap=0.1)

        return True

    def _tokenize_with_spans(self, text: str) -> Tuple[List[str], List[int]]:
        """Tokenize text into words and return tokens with their start positions."""
        tokens: List[str] = []
        starts: List[int] = []
        for m in re.finditer(r"\S+", text):
            tokens.append(m.group(0))
            starts.append(m.start())
        return tokens, starts

    def _extract_abilities_from_combo(self, command: str) -> List[str]:
        """Extract abilities in spoken order using token-level fuzzy matching."""
        abilities: List[str] = []
        cmd = self.normalize_text(command)

        for kw in ("combo", "kombinacja", "sekwencja", "chain", "then", "potem", "następnie", "nastepnie"):
            cmd = cmd.replace(kw, " ")

        tokens, starts = self._tokenize_with_spans(cmd)
        if not tokens:
            return abilities
        print(tokens, starts)
        match_positions: List[Tuple[int, str]] = []

        if self.current_champion:
            champ_abilities = self.data_manager.get_champion_abilities(self.current_champion)
            for key, ability_name in champ_abilities.items():
                if key == "passive":
                    continue
                name_norm = self.normalize_text(ability_name)
                name_parts = [p for p in name_norm.split() if len(p) >= 3]

                best_pos: Optional[int] = None
                best_score = 0.0

                for part in name_parts:
                    for idx, tok in enumerate(tokens):
                        sim = difflib.SequenceMatcher(None, part, tok).ratio()
                        thresh = 0.85 if len(part) <= 4 else max(0.72, self.recognition_accuracy - 0.03)
                        if sim >= thresh and sim > best_score:
                            best_score = sim
                            best_pos = starts[idx]

                if best_pos is not None:
                    match_positions.append((best_pos, key.lower()))

        tokenized_cmd = f" {cmd} "
        for key in ("q", "w", "e", "r"):
            pos = tokenized_cmd.find(f" {key} ")
            if pos != -1:
                match_positions.append((pos, key))

        match_positions.sort(key=lambda x: x[0])

        seen = set()
        for _, k in match_positions:
            if k not in seen:
                abilities.append(k)
                seen.add(k)

        return abilities

    def _extract_abilities_from_combo(self, command: str) -> List[str]:
        """Extract ability keys from a free-form combo command in spoken order."""
        abilities: List[str] = []
        cmd = self.normalize_text(command)

        for kw in ("combo", "kombinacja", "sekwencja", "chain", "then", "potem", "następnie", "nastepnie"):
            cmd = cmd.replace(kw, " ")

        indices: List[Tuple[int, str]] = []

        if self.current_champion:
            champ_abilities = self.data_manager.get_champion_abilities(self.current_champion)
            for key, ability_name in champ_abilities.items():
                if key == "passive":
                    continue
                name_norm = self.normalize_text(ability_name)
                pos = cmd.find(name_norm)
                if pos != -1:
                    indices.append((pos, key.lower()))

        tokenized = f" {cmd} "
        for key in ("q", "w", "e", "r"):
            pos = tokenized.find(f" {key} ")
            if pos != -1:
                indices.append((pos, key))

        indices.sort(key=lambda x: x[0])

        seen = set()
        for _, k in indices:
            if k not in seen:
                abilities.append(k)
                seen.add(k)

        return abilities

    def _execute_combo(self, abilities: List[str], gap: float = 0.1) -> None:
        """Execute a sequence of abilities in order with a fixed gap."""
        self.logger.debug(f"🎯 Executing combo: {' -> '.join(abilities)}")
        for i, ability in enumerate(abilities):
            if i > 0:
                time.sleep(gap)
            self.press_key(ability)

    def _execute_combo_queue(self, gap: float = 0.2) -> None:
        """Execute queued abilities accumulated by sequential triggers."""
        if not self.combo_queue:
            return
        self.logger.debug(f"🎯 Executing combo queue: {' -> '.join(self.combo_queue)}")
        for ability in self.combo_queue[1:]:
            time.sleep(gap)
            self.press_key(ability)
        self.combo_queue.clear()
        
    def listen_continuously(self) -> None:
        """Main loop for continuous listening and async recognition."""
        self.logger.info("🚀 Voice recognition active!")
        while self.is_listening:
            if self.microphone is None:
                self.logger.error("❌ No microphone available")
                time.sleep(1)
                continue

            try:
                with self.microphone as source:
                    if self.debug:
                        status = f"👂 Listening ({self.current_champion or 'No champion detected'})"
                        self.logger.debug(status)
                    audio = self.recognizer.listen(
                        source,
                        timeout=self.LISTEN_TIMEOUT,
                        phrase_time_limit=self.PHRASE_TIME_LIMIT,
                    )
            except sr.WaitTimeoutError:
                continue
            except Exception as exc:
                self.logger.debug(f"⚠️  Listening error: {exc}")
                time.sleep(0.1)
                continue

            t = threading.Thread(target=self._process_audio_async, args=(audio,), daemon=True)
            t.start()

    def _process_audio_async(self, audio: sr.AudioData) -> None:
        """Perform recognition in a background thread and process the command."""
        self.logger.debug(f"🔊 Recognizing using {self.MODEL_CONFIGS[self.recognition_model].name}...")
        command = self._recognize_audio(audio)

        if not command:
            return

        self.logger.debug(f"🎤 Heard: '{command}'")
        self.process_voice_command(command)

    def _recognize_audio(self, audio: sr.AudioData) -> Optional[str]:
        """Recognize audio using the selected model with a Google fallback."""
        try:
            if self.recognition_model == "google":
                return self.recognizer.recognize_google(audio, language=self.lang_code)
            if self.recognition_model == "sphinx":
                return self.recognizer.recognize_sphinx(audio)
            if self.recognition_model == "vosk":
                return self._recognize_with_vosk(audio)
        except Exception as exc:
            self.logger.debug(f"❌ Recognition failed: {exc}")

        try:
            fallback_lang = "en-US" if self.language == "pl_PL" else "pl-PL"
            return self.recognizer.recognize_google(audio, language=fallback_lang)
        except Exception:
            self.logger.debug("❌ Fallback recognition failed")
            return None

    def _recognize_with_vosk(self, audio: sr.AudioData) -> Optional[str]:
        """Recognize audio using Vosk with proper sample rate conversion."""
        try:
            from vosk import Model, KaldiRecognizer

            if self._vosk_model is None:
                model_dir = (
                    os.environ.get("VOSK_MODEL_PL", "vosk-model-small-pl-0.22")
                    if self.language == "pl_PL"
                    else os.environ.get("VOSK_MODEL_EN", "vosk-model-small-en-us")
                )
                if not os.path.isdir(model_dir):
                    self.logger.error(f"Missing Vosk model at: {model_dir}")
                    return None
                self._vosk_model = Model(model_dir)

            sample_rate = getattr(audio, "sample_rate", 16000) or 16000
            data = audio.get_raw_data(convert_rate=sample_rate, convert_width=2)

            recognizer = KaldiRecognizer(self._vosk_model, sample_rate)
            ok = recognizer.AcceptWaveform(data)
            result_json = recognizer.Result() if ok else recognizer.FinalResult()
            result = json.loads(result_json)
            text = (result.get("text") or "").strip()
            return text or None
        except Exception as exc:
            self.logger.debug(f"Vosk error: {exc}")
            return None
        

    def start_listening(self) -> None:
        """Start background listening loop."""
        if self.is_listening:
            self.logger.info("⚡ Already listening!")
            return

        self.is_listening = True
        self.gui_status.is_listening = True
        self._listen_thread = threading.Thread(target=self.listen_continuously, daemon=True)
        self._listen_thread.start()

        self.logger.info("🎯 LoL Voice Controller v0.2 Active!")
        self.logger.info("🤖 Automatic champion detection enabled")
        self.logger.info("🧠 Dynamic voice recognition with ability prioritization")

        if self.current_champion:
            abilities = self.data_manager.get_champion_abilities(self.current_champion)
            self.logger.info(f"\n🎮 Current Champion: {self.current_champion}")
            for key, name in abilities.items():
                if key != "passive":
                    keybind = self.keybinds.get(key, key.lower())
                    self.logger.info(f"   {key}: '{name}' -> {keybind}")
        else:
            self.logger.info("\n⚠️  No active game detected - using default mappings")

        self.logger.info(f"\n🎯 Recognition accuracy: {self.recognition_accuracy:.0%}")
        self.logger.info("💡 Say ability names naturally - algorithm will find the best match!")

    def stop_listening(self) -> None:
        """Stop background listening loop."""
        self.is_listening = False
        self.gui_status.is_listening = False
        if self._listen_thread and self._listen_thread.is_alive():
            self._listen_thread.join(timeout=1)
        self.logger.info("🔴 Voice recognition stopped")

    def test_microphone(self) -> None:
        """Perform a short mic test and process the recognized command."""
        self.logger.info("🎤 Microphone test - speak for 3 seconds...")
        if self.microphone is None:
            self.logger.error("❌ No microphone available")
            return

        with self.microphone as source:
            audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=3)

        self.logger.info("🔊 Processing...")
        try:
            command = self.recognizer.recognize_google(audio, language=self.lang_code)
            self.logger.info(f"✅ Recognized: '{command}'")
            self.process_voice_command(command)
        except Exception:
            self.logger.error("❌ Could not recognize speech - check microphone and internet")

    def toggle_debug(self) -> None:
        """Toggle debug logging verbosity."""
        self.debug = not self.debug
        self.logger = make_logger(self.debug)
        status = "ON" if self.debug else "OFF"
        self.logger.info(f"🐛 Debug mode: {status}")

    def update_keybinds(self, new_keybinds: Dict[str, str]) -> None:
        """Update keybinds and rebuild mappings."""
        self.keybinds.update(new_keybinds)
        self._generate_default_mappings()
        if self.current_champion:
            self._load_champion_mappings()
        self.logger.info(f"⚙️  Keybinds updated: {new_keybinds}")

    def get_status(self) -> Dict:
        """Return a snapshot of the controller status."""
        return {
            "listening": self.is_listening,
            "champion": self.current_champion,
            "game_active": self.game_api.is_game_active(),
            "mappings_count": len(self.current_mappings),
            "accuracy": self.recognition_accuracy,
            "language": self.language,
            "model": self.recognition_model,
            "last_update": self.gui_status.last_update,
            "last_command": self.gui_status.last_command,
        }

    def change_recognition_model(self, model_name: str) -> bool:
        """Change recognition model if available."""
        if model_name not in self.MODEL_CONFIGS:
            return False
        self.recognition_model = model_name
        self.gui_status.model = model_name
        config = self.MODEL_CONFIGS[model_name]
        self.logger.info(f"🎤 Changed recognition model to: {config.name}")
        if config.online:
            self.logger.info("ℹ️ This model requires internet connection")
        return True

    def change_language(self, new_language: str) -> bool:
        """Change language in data manager and refresh mappings."""
        if not self.data_manager.change_language(new_language):
            return False
        self.language = new_language
        self._update_champion()
        self.logger.info(f"🌍 Language changed to: {new_language}")
        return True


def main() -> None:
    """Run CLI loop for the voice controller."""
    logger = make_logger(True)
    logger.info("🎯 === League of Legends Voice Controller v0.2 === 🎯")
    logger.info("🤖 Automatic champion detection and dynamic voice recognition")
    print("Commands:")
    print("  Enter = Start/Stop listening")
    print("  't' = Test microphone")
    print("  'd' = Toggle debug mode")
    print("  'u' = Update champion")
    print("  'm' = Change recognition model")
    print("  's' = Show status")
    print("  'q' = Quit")

    controller = LoLVoiceControllerV2()

    try:
        while True:
            user_input = input("\n>>> ").strip().lower()
            if user_input == "q":
                break
            if user_input == "":
                if not controller.is_listening:
                    controller.start_listening()
                else:
                    controller.stop_listening()
                continue
            if user_input == "t":
                controller.test_microphone()
                continue
            if user_input == "d":
                controller.toggle_debug()
                continue
            if user_input == "u":
                controller._update_champion()
                print("🔄 Champion detection updated")
                continue
            if user_input == "m":
                print("\nAvailable recognition models:")
                for model, config in controller.MODEL_CONFIGS.items():
                    status = "🌐 Online" if config.online else "💻 Offline"
                    print(f"- {config.name} ({status}, Accuracy: {config.accuracy:.0%})")
                choice = input("\nSelect model (google/sphinx/vosk): ").strip().lower()
                if controller.change_recognition_model(choice):
                    print(f"✅ Changed to {controller.MODEL_CONFIGS[choice].name}")
                else:
                    print("❌ Invalid model choice")
                continue
            if user_input == "s":
                status = controller.get_status()
                print(f"📊 Status: {json.dumps(status, indent=2)}")
                continue

            print("\nCommands:")
            print("  Enter = Start/Stop listening")
            print("  't' = Test microphone")
            print("  'd' = Toggle debug mode")
            print("  'u' = Update champion")
            print("  'm' = Change recognition model")
            print("  's' = Show status")
            print("  'q' = Quit")

    except KeyboardInterrupt:
        print("\n🔴 Interrupted!")
    finally:
        controller.stop_listening()
        print("🔴 Voice Controller stopped.")


if __name__ == "__main__":
    main()