"""Tor audio: mikrofon, VAD, kolejka, transkrypcja.

Sama logika VAD zostala bez zmian, bo dziala. Zmienilo sie otoczenie: model
bierze sie z app.engines, jezyk z ustawien, a rozpoznany tekst leci do
VoiceService, ktory dopasowuje komende i wysyla zdarzenia do panelu.

sounddevice i webrtcvad importuja sie dopiero przy starcie nasluchu, wiec ten
modul mozna zaimportowac na maszynie bez karty dzwiekowej.
"""

from __future__ import annotations

import collections
import threading
import time
from collections.abc import Callable
from queue import Empty, Queue
from typing import Any

from app import config
from app.config import Settings
from app.logging_setup import get_logger
from controller.transcriber import Transcriber
from controls.mapping_manager import MappingManager
from game.ability_manager import AbilityManager
from game.lol_game_client_api import LoLGameClientAPI

log = get_logger("controller")

SAMPLE_RATE = 16000



def resolve_audio_device(value):
    """Ustawienie urzadzenia na cos, co przyjmie sounddevice, albo None.

    Wartosc to nazwa urzadzenia (nowy zapis) albo indeks PortAudio (stary
    zapis). Indeksy zmieniaja sie miedzy uruchomieniami, wiec indeks bez
    pokrycia w istniejacym wejsciu audio wraca do urzadzenia domyslnego.
    """
    if value in (None, "", "default"):
        return None
    try:
        import sounddevice as sd

        devices = list(sd.query_devices())
    except Exception:
        return None

    try:
        index = int(value)
    except (TypeError, ValueError):
        # Nazwa z panelu. Wybieramy indeks sami, bo sounddevice wymaga
        # jednoznacznej nazwy, a stare API maja zduplikowane wpisy.
        name = str(value)
        try:
            hostapis = list(sd.query_hostapis())
        except Exception:
            hostapis = []

        def api_rank(info: dict) -> int:
            # MME i DirectSound przeprobkowuja same, wiec 16 kHz zawsze
            # dziala. WASAPI w trybie dzielonym wymaga natywnej czestotliwosci
            # i konczy sie bledem Invalid sample rate.
            hostapi = info.get("hostapi")
            api_name = hostapis[hostapi].get("name", "") if 0 <= (hostapi or -1) < len(hostapis) else ""
            if "MME" in api_name:
                return 0
            if "DirectSound" in api_name:
                return 1
            return 2

        matches = []
        for idx, info in enumerate(devices):
            if info.get("max_input_channels", 0) <= 0:
                continue
            device_name = info.get("name", "")
            # Nazwy w MME sa uciete do 31 znakow, porownujemy prefiksami.
            shorter = min(len(device_name), len(name))
            if shorter and device_name[:shorter] == name[:shorter]:
                matches.append((api_rank(info), idx))
        if matches:
            matches.sort()
            return matches[0][1]
        log.warning("Audio device %r not found, using the default one", value)
        return None

    if 0 <= index < len(devices) and devices[index].get("max_input_channels", 0) > 0:
        return index
    log.warning("Audio device index %s is stale, using the default one", index)
    return None


class _EnergyVad:
    """Zapasowy detektor mowy, gdy webrtcvad nie dziala.

    Prog adaptacyjny na RMS ramki: szum ustala baze, mowa musi ja wyraznie
    przebic. Interfejs zgodny z webrtcvad.Vad.
    """

    def __init__(self, ratio: float = 2.5, floor: float = 0.006) -> None:
        self._ratio = ratio
        self._floor = floor
        self._noise = 0.01

    def is_speech(self, audio_bytes: bytes, _sample_rate: int) -> bool:
        import numpy as np

        frame = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        if frame.size == 0:
            return False
        rms = float(np.sqrt(np.mean(frame * frame)))
        threshold = max(self._floor, self._noise * self._ratio)
        speech = rms > threshold
        if not speech:
            # Wolno adaptowany szum tla, tylko na ramkach ciszy.
            self._noise = 0.95 * self._noise + 0.05 * rms
        return speech

class LoLVoiceController:
    def __init__(
        self,
        settings: Settings | None = None,
        mapping_manager: MappingManager | None = None,
        transcriber: Transcriber | None = None,
        on_text: Callable[[str], Any] | None = None,
        game_api: LoLGameClientAPI | None = None,
        ability_manager: AbilityManager | None = None,
    ) -> None:
        self.settings = settings or config.load()
        self.is_listening = False

        self.SAMPLE_RATE = SAMPLE_RATE
        self.CHUNK_DURATION_MS = 20
        self.CHUNK_SIZE = int(self.SAMPLE_RATE * self.CHUNK_DURATION_MS / 1000)
        self.PADDING_DURATION_MS = 60
        self.NUM_PADDING_CHUNKS = int(self.PADDING_DURATION_MS / self.CHUNK_DURATION_MS)

        self.SILENCE_CHUNKS_THRESHOLD = 3
        self.MIN_SPEECH_CHUNKS = 2

        self.game_api = game_api or LoLGameClientAPI()
        self.mapping_manager = mapping_manager or MappingManager(self.settings)
        self.ability_manager = ability_manager or AbilityManager(self.game_api, language=self.settings.language)
        self.transcriber = transcriber or Transcriber()
        self.on_text = on_text

        self.vad: Any | None = None
        self.stream: Any | None = None

        self.audio_queue: Queue = Queue(maxsize=10)
        self.processing_thread: threading.Thread | None = None

        self.ring_buffer: collections.deque = collections.deque(maxlen=self.NUM_PADDING_CHUNKS)
        self.triggered = False
        self.speech_buffer: list[bytes] = []
        self.silence_counter = 0
        self.speech_counter = 0

        self.last_command = ""
        self.last_champion_update = ""
        self.current_champion_name: str | None = None
        self.game_active = False

    # --- model --------------------------------------------------------

    @property
    def language(self) -> str:
        return self.settings.language

    def load_engine(self) -> None:
        """Laduje model, jesli jeszcze nie jest zaladowany."""
        if not self.transcriber.loaded:
            self.transcriber.load()
        if self.vad is None:
            try:
                import webrtcvad

                self.vad = webrtcvad.Vad(2)  # 2 to kompromis miedzy czuloscia a szumem
            except (ImportError, OSError) as exc:
                # Smart App Control potrafi zablokowac DLL webrtcvad. Prosty
                # VAD energetyczny na numpy jest gorszy, ale zawsze dziala.
                log.warning("webrtcvad unavailable (%s), using the energy fallback VAD", exc)
                self.vad = _EnergyVad()

    # --- petla stanu gry ----------------------------------------------

    def _periodic_game_state_update(self, interval_seconds: float = 2.0) -> None:
        """Odswieza tryb, bohatera i mapowania umiejetnosci."""
        last_mode = self.mapping_manager.mode

        while self.is_listening:
            time.sleep(interval_seconds)
            try:
                self.settings = config.load()
                current_mode = self.settings.recognition_mode
                if current_mode != last_mode:
                    log.info("Recognition mode changed to '%s', rebuilding mappings", current_mode)
                    self.mapping_manager.mode = current_mode
                    last_mode = current_mode

                self.game_active = self.game_api.is_game_active()
                if self.game_active:
                    new_champion_name = self.game_api.get_current_champion()

                    if (new_champion_name and self.current_champion_name != new_champion_name) or (
                        self.mapping_manager.mode == "spells"
                    ):
                        if self.current_champion_name != new_champion_name:
                            self.current_champion_name = new_champion_name
                            self.last_champion_update = time.strftime("%H:%M:%S")
                            log.info("Champion detected: %s", self.current_champion_name)

                        champion_mappings = self.ability_manager.create_voice_mappings_from_api(
                            self.current_champion_name
                        )
                        if champion_mappings:
                            normalized_new = {
                                self.mapping_manager.normalize(k): v for k, v in champion_mappings.items()
                            }
                            if normalized_new != self.mapping_manager.champion_spell_mappings:
                                self.mapping_manager.load_champion_mappings(champion_mappings)
                                log.debug("Refreshed ability mappings for %s", self.current_champion_name)
                elif self.current_champion_name is not None:
                    log.info("Game session ended, reverting to default mappings")
                    self.current_champion_name = None
                    self.mapping_manager.reset_to_default()
            except Exception as exc:  # petla tla nie moze umrzec
                log.warning("Game state update failed: %s", exc)

    # --- audio --------------------------------------------------------

    def _resolve_device(self):
        return resolve_audio_device(self.settings.audio_device)

    def _init_audio_stream(self) -> bool:
        try:
            import sounddevice as sd

            self.stream = sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                channels=1,
                dtype="int16",
                blocksize=self.CHUNK_SIZE,
                device=self._resolve_device(),
                callback=self._audio_stream_callback,
                latency="low",
            )
            self.stream.start()
            log.info("Audio stream active")
            return True
        except Exception as exc:  # brak mikrofonu to blad uzytkownika, nie crash
            log.error("Failed to start audio stream: %s", exc)
            self.is_listening = False
            return False

    def _audio_stream_callback(self, indata, frames, time_info, status) -> None:
        """Detekcja mowy: bufor pierscieniowy przed startem, licznik ciszy po."""
        if not self.is_listening:
            return

        if status:
            log.warning("Audio status: %s", status)

        try:
            audio_bytes = indata.tobytes()
            is_speech = self.vad.is_speech(audio_bytes, self.SAMPLE_RATE)

            if self.triggered:
                self.speech_buffer.append(audio_bytes)

                if is_speech:
                    self.silence_counter = 0
                    self.speech_counter += 1
                else:
                    self.silence_counter += 1

                    if self.silence_counter >= self.SILENCE_CHUNKS_THRESHOLD:
                        if self.speech_counter >= self.MIN_SPEECH_CHUNKS:
                            audio_data = b"".join(self.speech_buffer)
                            if not self.audio_queue.full():
                                self.audio_queue.put_nowait(audio_data)

                        self.speech_buffer.clear()
                        self.triggered = False
                        self.silence_counter = 0
                        self.speech_counter = 0
            else:
                self.ring_buffer.append((audio_bytes, is_speech))
                num_voiced = len([f for f, speech in self.ring_buffer if speech])

                if num_voiced > 0.5 * self.ring_buffer.maxlen:
                    self.triggered = True
                    self.speech_buffer.extend(f for f, _s in self.ring_buffer)
                    self.ring_buffer.clear()
                    self.silence_counter = 0
                    self.speech_counter = num_voiced

        except Exception as exc:  # callback audio nie moze rzucac
            log.error("Error in audio callback: %s", exc)

    def _processing_worker(self) -> None:
        """Dedykowany watek transkrypcji, zeby nie blokowac callbacku audio."""
        while self.is_listening:
            try:
                audio_data = self.audio_queue.get(timeout=0.1)
            except Empty:
                continue
            if audio_data:
                self.process_audio(audio_data)

    def process_audio(self, audio_data_bytes: bytes) -> str:
        """Transkrybuje fragment PCM i przekazuje tekst dalej."""
        try:
            if not audio_data_bytes or len(audio_data_bytes) < 1000:
                return ""

            start_time = time.time()
            text = self.transcriber.transcribe_pcm(audio_data_bytes, self.settings.language)
            if not text:
                return ""

            elapsed_ms = (time.time() - start_time) * 1000
            log.debug("Heard '%s' (%.0f ms)", text, elapsed_ms)
            self.last_command = text
            if self.on_text:
                self.on_text(text)
            return text
        except Exception as exc:  # blad modelu nie moze zabic watku
            log.error("Transcription error: %s", exc)
            return ""

    # --- cykl zycia ---------------------------------------------------

    def start_listening(self) -> bool:
        if self.is_listening:
            log.info("Already listening")
            return True

        self.load_engine()
        self.is_listening = True

        self.processing_thread = threading.Thread(target=self._processing_worker, daemon=True)
        self.processing_thread.start()

        if not self._init_audio_stream():
            return False

        threading.Thread(target=self._periodic_game_state_update, daemon=True).start()
        log.info("Listening for commands")
        return True

    def stop_listening(self) -> None:
        if not self.is_listening:
            return

        self.is_listening = False

        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as exc:  # zamykanie strumienia bywa kapryzne
                log.warning("Error closing audio stream: %s", exc)
            self.stream = None
            log.info("Audio stream stopped")

        if self.processing_thread:
            self.processing_thread.join(timeout=1)
            self.processing_thread = None

        log.info("Listening stopped")

    def get_status(self) -> dict:
        return {
            "listening": self.is_listening,
            "champion": self.current_champion_name,
            "game_active": self.game_active,
            "mappings_count": len(self.mapping_manager.active_mappings),
            "language": self.settings.language,
            "last_update": self.last_champion_update,
            "last_command": self.last_command,
        }
