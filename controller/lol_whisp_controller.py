
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

        self.key_controller = KeyController()
        self.data_manager = LoLDataManager(language)
        self.mapping_manager = MappingManager(language)
        self.game_api = LoLGameClientAPI()

        self.whisper_model = None
        self.vad = None
        self.executor = None
        self.stream = None
        self.speech_buffer = collections.deque(maxlen=5)
        self.current_champion = None
        self.recognition_model = "whisper"
        self.last_command = "No commands yet"
        self.last_champion_update = ""

        self._init_whisper()
        self.logger.info("✅ Voice Controller initialized.")
        self.logger.info(f"🗺️  Loaded {len(self.mapping_manager.mappings)} default voice commands.")

    def _init_whisper(self):
        """Inicjalizuje model Whisper i VAD."""
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
        """Aktualizuje aktualnego championa i voice mappings."""
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
        """Inicjalizuje strumień audio z mikrofonu."""
        try:
            self.stream = sd.InputStream(
                samplerate=16000,
                channels=1,
                dtype="int16",
                blocksize=480,  # 30ms na blok
                callback=self._audio_stream_callback,
                latency="low"
            )
            self.stream.start()
            self.logger.info("🎤 Audio stream active")
        except Exception as e:
            self.logger.error(f"❌ Failed to start audio stream: {e}")
            self.is_listening = False

    def _audio_stream_callback(self, indata, frames, time_info, status):
        if not self.is_listening:
            return
        if status:
            self.logger.warning(f"Audio status: {status}")

        try:
            audio_bytes = indata.tobytes()
            if self.vad.is_speech(audio_bytes, 16000):
                self.speech_buffer.append(indata.copy())
                # Jeśli mamy >= 1s audio (16000 próbek), wyślij do transkrypcji
                if sum(len(chunk) for chunk in self.speech_buffer) >= 16000:
                    audio_data = np.concatenate(list(self.speech_buffer), axis=0)
                    if self.executor:
                        self.executor.submit(self._process_whisper_audio, audio_data)
                    self.speech_buffer.clear()
        except Exception as e:
            self.logger.error(f"Error in audio callback: {e}")


    def _process_whisper_audio(self, audio_data):
        try:
            start_time = time.time()
            audio_float = audio_data.flatten().astype(np.float32) / 32768.0
            text = ""

            try:
                result = self.whisper_model.transcribe(audio_float, language="pl")
                if isinstance(result, tuple) and len(result) == 2:
                    segments_gen, info = result
                    segments = list(segments_gen)
                    text = "".join(getattr(s, "text", "") for s in segments)
                elif isinstance(result, str):
                    text = result
            except Exception as e:
                self.logger.error(f"Whisper transcribe error: {e}")
                return

            if text:
                text = text.strip().lower()
                process_time = (time.time() - start_time) * 1000
                print(f"🎤 Detected: '{text}' ({process_time:.0f}ms)")
                self.logger.debug(f"🎤 Heard: '{text}' ({process_time:.0f}ms)")
                self._execute_fast_command(text)
        except Exception as e:
            self.logger.error(f"Whisper processing error: {e}")



    def _execute_fast_command(self, text: str):
        """Wykonuje komendę po rozpoznaniu tekstu."""
        action = self.mapping_manager.match_command(text)
        self.last_command = text  # dla GUI
        if action:
            self.key_controller.press_key(action)
            self.logger.info(f"🎯 Executed: '{text}' -> {action.upper()}")
        else:
            self.logger.debug(f"❌ No match for: '{text}'")

    def start_listening(self):
        """Rozpoczyna nasłuchiwanie."""
        if self.is_listening:
            self.logger.info("Already listening.")
            return

        self.is_listening = True
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self._init_audio_stream()
        threading.Thread(target=self._periodic_champion_update, daemon=True).start()

        self.logger.info("🚀 Whisper mode active. Listening for commands...")

    def stop_listening(self):
        """Zatrzymuje nasłuchiwanie."""
        if not self.is_listening:
            return

        self.is_listening = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
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
        """Zwraca aktualny stan kontrolera do GUI."""
        mappings_count = len(getattr(self.mapping_manager, "mappings", {}))
        last_command = getattr(self, "last_command", "No commands yet")
        last_update = getattr(self, "last_champion_update", "")

        return {
            "listening": getattr(self, "is_listening", False),
            "champion": getattr(self, "current_champion", None),
            "game_active": self.game_api.is_game_active() if hasattr(self, "game_api") else False,
            "mappings_count": mappings_count,
            "accuracy": "70%",
            "language": getattr(self, "language", "pl_PL"),
            "model": getattr(self, "recognition_model", "whisper"),
            "last_update": last_update,
            "last_command": last_command,
        }
