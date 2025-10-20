import time
import collections
import numpy as np
import webrtcvad
import sounddevice as sd
import concurrent.futures
import threading

from controls.key_controller import KeyController
from controls.mapping_manager import MappingManager
from game.lol_game_client_api import LoLGameClientAPI
from game.lol_data_manager import LoLDataManager
from utils.logger import make_logger

class LoLVoiceController:
    def __init__(self, language="pl_PL", debug=True):
        self.is_listening = False
        self.logger = make_logger(debug)
        self.language = language

        self.SAMPLE_RATE = 16000
        self.CHUNK_DURATION_MS = 30
        self.CHUNK_SIZE = int(self.SAMPLE_RATE * self.CHUNK_DURATION_MS / 1000)
        self.PADDING_DURATION_MS = 300
        self.NUM_PADDING_CHUNKS = int(self.PADDING_DURATION_MS / self.CHUNK_DURATION_MS)

        self.key_controller = KeyController()
        self.data_manager = LoLDataManager(language)
        self.mapping_manager = MappingManager(language)
        self.game_api = LoLGameClientAPI()

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

        self._init_whisper()
        self.logger.info("✅ Voice Controller initialized.")
        self.logger.info(f"🗺️  Loaded {len(self.mapping_manager.mappings)} default voice commands.")

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

    def _update_champion(self):
        new_champion = None
        if self.game_api.is_game_active():
            champ_data = self.game_api.get_champion_and_summoner_spells()
            new_champion = champ_data.get("champion")

        self.last_champion_update = time.strftime("%H:%M:%S")

        if new_champion != self.current_champion:
            self.current_champion = new_champion
            if new_champion:
                champion_mappings = self.data_manager.create_voice_mappings(new_champion)
                self.mapping_manager.load_champion_mappings(champion_mappings)
                self.logger.info(f"🎮 Champion detected: {new_champion}")
                self.logger.info(f"🗺️  Total active commands: {len(self.mapping_manager.mappings)}")
            else:
                self.mapping_manager.reset_to_default()
                self.logger.info("⚠️ Game not active or no champion detected. Using default mappings.")

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
            
            # Iterujemy po generatorze segmentów, aby zbudować pełny tekst
            text = "".join(segment.text for segment in segments)
            
            if text:
                text = text.strip().lower()
                process_time = (time.time() - start_time) * 1000
                self.logger.debug(f"🎤 Heard: '{text}' ({process_time:.0f}ms)")
                self._execute_fast_command(text)
        except Exception as e:
            self.logger.error(f"Whisper processing error: {e}")

    def _execute_fast_command(self, text: str):
        action = self.mapping_manager.match_command(text)
        self.last_command = text
        if action:
            self.key_controller.press_key(action)
            self.logger.info(f"🎯 Executed: '{text}' -> {action.upper()}")
        else:
            self.logger.debug(f"❌ No match for: '{text}'")

    def start_listening(self):
        if self.is_listening:
            self.logger.info("Already listening.")
            return

        self.is_listening = True
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self._init_audio_stream()
        threading.Thread(target=self._periodic_champion_update, daemon=True).start()
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

    def _periodic_champion_update(self, interval_seconds=15):
        """Sprawdza co pewien czas, czy zmienił się champion."""
        while self.is_listening:
            self._update_champion()
            time.sleep(interval_seconds)

    def change_recognition_model(self, new_model: str) -> bool:
        """Zmienia model rozpoznawania mowy."""
        try:
            if new_model.lower() not in ["whisper", "vosk", "sphinx"]:
                self.logger.warning(f"⚠️ Nieznany model: {new_model}")
                return False
            self.recognition_model = new_model.lower()
            self.logger.info(f"🟢 Recognition model set to: {self.recognition_model}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Failed to change recognition model: {e}")
            return False

    def get_status(self) -> dict:
        mappings_count = len(getattr(self.mapping_manager, "mappings", {}))
        return {
            "listening": self.is_listening,
            "champion": self.current_champion,
            "game_active": self.game_api.is_game_active(),
            "mappings_count": mappings_count,
            "accuracy": "70%",
            "language": self.language,
            "model": self.recognition_model,
            "last_update": self.last_champion_update,
            "last_command": self.last_command,
        }