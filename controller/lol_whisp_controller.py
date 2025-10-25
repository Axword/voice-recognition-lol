# controller/lol_whisp_controller.py

import time
import collections
import numpy as np
import webrtcvad
import sounddevice as sd
import concurrent.futures
import threading
import re

from controls.key_controller import KeyController
from controls.mapping_manager import MappingManager
from game.lol_game_client_api import LoLGameClientAPI
from game.ability_manager import AbilityManager
from utils.logger import make_logger

class LoLVoiceController:
    def __init__(self, language="pl_PL", debug=True):
        self.is_listening = False
        self.logger = make_logger(debug)
        self.language = language

        self.SAMPLE_RATE = 16000
        self.CHUNK_DURATION_MS = 30
        self.CHUNK_SIZE = int(self.SAMPLE_RATE * self.CHUNK_DURATION_MS / 1000)
        self.PADDING_DURATION_MS = 150
        self.NUM_PADDING_CHUNKS = int(self.PADDING_DURATION_MS / self.CHUNK_DURATION_MS)
        self.key_controller = KeyController()
        self.game_api = LoLGameClientAPI()
        self.mapping_manager = MappingManager(language)
        self.ability_manager = AbilityManager(self.game_api)

        self.whisper_model = None
        self.vad = None
        self.executor = None
        self.stream = None
        
        self.ring_buffer = collections.deque(maxlen=self.NUM_PADDING_CHUNKS)
        self.triggered = False
        self.speech_buffer = []
        
        self.current_champion = None
        self.recognition_model = "whisper"
        self.last_command = "No commands yet"
        self.last_champion_update = ""
        self.current_champion_name = None
        self._init_whisper()
        self.logger.info("✅ Voice Controller initialized.")
        total_defaults = len(self.mapping_manager.letter_mappings) + len(self.mapping_manager.default_core_mappings)
        self.logger.info(f"🗺️  Loaded {total_defaults} default voice commands.")
        
    def _init_whisper(self):
        try:
            from pywhispercpp.model import Whisper
            self.whisper_model = Whisper("models/ggml-tiny.bin", n_threads=4)
            self.logger.info("✅ Using pywhispercpp (fast)")
        except Exception:
            from faster_whisper import WhisperModel
            self.whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
            self.logger.info("✅ Using faster-whisper (fallback)")
        
        self.vad = webrtcvad.Vad(3)
# W pliku controller/lol_whisp_controller.py

# ... (reszta klasy bez zmian) ...

    def _periodic_game_state_update(self, interval_seconds=2):
        """
        Główna pętla odświeżająca stan gry. Zoptymalizowana, aby unikać zbędnej pracy.
        """
        last_mode = self.mapping_manager.mode
        
        while self.is_listening:
            time.sleep(interval_seconds)

            # Sprawdzamy, czy tryb w pliku config.json się nie zmienił
            current_mode = self.mapping_manager._load_config().get("recognition_mode", "letters")
            if current_mode != last_mode:
                self.logger.info(f"⚙️ Recognition mode changed to '{current_mode}'. Rebuilding mappings.")
                self.mapping_manager.mode = current_mode
                self.mapping_manager.active_mappings = self.mapping_manager._build_active_mappings()
                last_mode = current_mode
            
            if self.game_api.is_game_active():
                new_champion_name = self.game_api.get_current_champion()

                if (new_champion_name and self.current_champion_name != new_champion_name) or \
                   (self.mapping_manager.mode == "spells"):
                    
                    if self.current_champion_name != new_champion_name:
                         self.current_champion_name = new_champion_name
                         self.last_champion_update = time.strftime("%H:%M:%S")
                         self.logger.info(f"🎯 Champion detected: {self.current_champion_name}")
                    
                    champion_mappings = self.ability_manager.create_voice_mappings_from_api()
                    if champion_mappings:
                        normalized_new = {self.mapping_manager.normalize(k): v for k, v in champion_mappings.items()}
                        if normalized_new != self.mapping_manager.champion_spell_mappings:
                            self.mapping_manager.load_champion_mappings(champion_mappings)
                            self.logger.debug(f"🔄 Refreshed ability mappings for {self.current_champion_name}.")
            else:
                if self.current_champion_name is not None:
                    self.logger.info("🔴 Game session ended. Reverting to default mappings.")
                    self.current_champion_name = None
                    self.mapping_manager.reset_to_default()
    
# ... (reszta klasy bez zmian) ...
    
    def _init_audio_stream(self):
        try:
            self.stream = sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                channels=1,
                dtype="int16",
                blocksize=self.CHUNK_SIZE,
                callback=self._audio_stream_callback,
                latency="low"
            )
            self.stream.start()
            self.logger.info("🎤 Audio stream active")
        except Exception as e:
            self.logger.error(f"❌ Failed to start audio stream: {e}")
            self.is_listening = False

    def _audio_stream_callback(self, indata, frames, time_info, status):
        if not self.is_listening: return
        if status: self.logger.warning(f"Audio status: {status}")
        try:
            audio_bytes = indata.tobytes()
            is_speech = self.vad.is_speech(audio_bytes, self.SAMPLE_RATE)
            if self.triggered:
                self.speech_buffer.append(audio_bytes)
                if not is_speech:
                    if self.executor:
                        audio_data_bytes = b''.join(self.speech_buffer)
                        self.executor.submit(self._process_whisper_audio, audio_data_bytes)
                    self.speech_buffer.clear()
                    self.triggered = False
            else:
                self.ring_buffer.append((audio_bytes, is_speech))
                num_voiced = len([f for f, speech in self.ring_buffer if speech])
                if num_voiced > 0.8 * self.ring_buffer.maxlen:
                    self.triggered = True
                    self.speech_buffer.extend(f for f, s in self.ring_buffer)
                    self.ring_buffer.clear()
        except Exception as e:
            self.logger.error(f"Error in audio callback: {e}")

    def _process_whisper_audio(self, audio_data_bytes):
        try:
            if not audio_data_bytes:
                return
            start_time = time.time()
            audio_np = np.frombuffer(audio_data_bytes, dtype=np.int16)
            audio_float = audio_np.astype(np.float32) / 32768.0
            segments, info = self.whisper_model.transcribe(audio_float, language="pl")
            text = "".join(segment.text for segment in segments)
            if text:
                text = re.sub(r'[^\w\sąćęłńóśźż]', '', text.lower().strip())
                self.logger.debug(f"🎤 Heard: '{text}' ({(time.time() - start_time) * 1000:.0f}ms)")
                self._execute_fast_command(text)
        except Exception as e:
            self.logger.error(f"Whisper processing error: {e}")

    def _execute_combo(self, actions: list, delay: float = 0.15):
        """Wykonuje sekwencję akcji z opóźnieniem."""
        self.logger.info(f"💥 Executing combo: {' -> '.join(str(a) for a in actions).upper()}")
        for i, action in enumerate(actions):
            if i > 0:
                time.sleep(delay)
            self.key_controller.press_key(action)

    def _execute_fast_command(self, text: str):
        result = self.mapping_manager.match_command(text)
        self.last_command = text
        if result:
            if isinstance(result, list):
                self._execute_combo(result)
            elif isinstance(result, str):
                self.key_controller.press_key(result)
                self.logger.info(f"🎯 Executed: '{text}' -> {result.upper()}")
        else:
            self.logger.debug(f"❌ No match for: '{text}'")

    def start_listening(self):
        if self.is_listening:
            self.logger.info("Already listening.")
            return
        self.is_listening = True
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self._init_audio_stream()
        threading.Thread(target=self._periodic_game_state_update, daemon=True).start()
        self.logger.info("🚀 Whisper mode active. Listening for commands...")

    def stop_listening(self):
        if not self.is_listening: return
        self.is_listening = False
        if self.stream:
            self.stream.stop(); self.stream.close()
            self.logger.info("🎤 Audio stream stopped.")
        if self.executor:
            self.executor.shutdown(wait=True)
            self.logger.info("ThreadPool shut down.")
        self.logger.info("🛑 Listening stopped.")


    def get_status(self) -> dict:
        mappings_count = len(getattr(self.mapping_manager, "mappings", {}))
        return {
            "listening": self.is_listening,
            "champion": self.current_champion_name,
            "game_active": self.game_api.is_game_active(),
            "mappings_count": mappings_count,
            "language": self.language,
            "last_update": self.last_champion_update,
            "last_command": self.last_command,
        }