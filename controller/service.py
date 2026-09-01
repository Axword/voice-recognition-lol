"""Fasada silnika glosowego.

Serwer rozmawia z silnikiem wylacznie przez ten modul. Import jest lekki:
sounddevice, pywhispercpp i pynput pojawiaja sie dopiero w metodach, ktore ich
naprawde potrzebuja, a konstruktor nie dotyka ani mikrofonu, ani modelu. Dzieki
temu `from controller.service import get_service` dziala w CI bez karty
dzwiekowej i bez zainstalowanego Whispera.

Wstrzykiwanie transkrypcji na potrzeby testow:

    service.set_transcriber(lambda pcm: "flash")   # albo service._transcriber = fn

Funkcja dostaje surowy PCM 16 kHz mono int16 i zwraca tekst. feed_pcm() puszcza
wynik dokladnie ta sama sciezka co zywe audio: czyszczenie tekstu, dopasowanie
komendy, wcisniecie klawisza, zdarzenie 'heard'.
"""

from __future__ import annotations

import random
import threading
import time
from collections.abc import Callable
from typing import Any

from app import config, engines, version
from app.config import Settings
from app.logging_setup import get_logger
from controller.transcriber import clean_text
from controls.key_controller import KeyController
from controls.mapping_manager import MappingManager

log = get_logger("service")

EventSink = Callable[[dict], None]
TranscriberFn = Callable[[bytes], str]

COMBO_DELAY = 0.05
RANDOM_ABILITIES = ("q", "w", "e", "r")


class VoiceService:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._settings: Settings | None = None
        self._mapping_manager: MappingManager | None = None
        self._key_controller: KeyController | None = None
        self._controller: Any | None = None
        self._engine: Any | None = None
        self._transcriber: TranscriberFn | None = None
        self._event_sink: EventSink | None = None
        self._listening = False
        self._last_command: str | None = None
        self._last_heard: str | None = None
        self._last_error: str | None = None
        self.update_available = False

    # --- leniwe zaleznosci --------------------------------------------

    @property
    def settings(self) -> Settings:
        if self._settings is None:
            self._settings = config.load()
        return self._settings

    @property
    def mapping_manager(self) -> MappingManager:
        if self._mapping_manager is None:
            self._mapping_manager = MappingManager(self.settings)
        return self._mapping_manager

    @property
    def key_controller(self) -> KeyController:
        if self._key_controller is None:
            self._key_controller = KeyController()
        return self._key_controller

    # --- zdarzenia ----------------------------------------------------

    def set_event_sink(self, fn: EventSink | None) -> None:
        """Rejestruje odbiorce zdarzen 'heard', 'status' i 'log'."""
        self._event_sink = fn

    def _emit(self, event: dict) -> None:
        sink = self._event_sink
        if sink is None:
            return
        try:
            sink(event)
        except Exception as exc:  # odbiorca zdarzen nie moze wywrocic silnika
            log.warning("Event sink failed: %s", exc)

    def _emit_status(self) -> None:
        self._emit({"type": "status", **self.status()})

    def _emit_log(self, level: str, message: str) -> None:
        log.log({"error": 40, "warning": 30}.get(level, 20), "%s", message)
        self._emit({"type": "log", "level": level, "message": message})

    # --- transkrypcja -------------------------------------------------

    def set_transcriber(self, fn: TranscriberFn | None) -> None:
        """Podmienia transkrypcje. fn(pcm: bytes) -> str. None przywraca Whispera."""
        self._transcriber = fn

    def _engine_transcriber(self):
        """Leniwie tworzony obiekt Transcriber z prawdziwym modelem."""
        if self._engine is None:
            from controller.transcriber import Transcriber

            self._engine = Transcriber()
        if not self._engine.loaded:
            self._engine.load()
        return self._engine

    def _transcribe(self, pcm: bytes) -> str:
        if self._transcriber is not None:
            return clean_text(self._transcriber(pcm))
        if self._controller is not None:
            return self._controller.transcriber.transcribe_pcm(pcm, self.settings.language)
        return self._engine_transcriber().transcribe_pcm(pcm, self.settings.language)

    def feed_pcm(self, pcm: bytes) -> str:
        """Wstrzykuje surowy PCM 16 kHz mono int16 i zwraca rozpoznany tekst."""
        try:
            text = self._transcribe(pcm)
        except Exception as exc:  # brak modelu nie moze wywrocic serwera
            self._emit_log("error", f"Transcription failed: {exc}")
            return ""
        if not text:
            return ""
        self.handle_transcript(text)
        return text

    # --- wspolna sciezka komend ---------------------------------------

    def handle_transcript(self, text: str) -> str | list[str] | None:
        """Dopasowuje tekst do akcji i wykonuje ja.

        Zwraca klawisz, liste klawiszy przy lancuchu komend, albo None.
        """
        cleaned = clean_text(text)
        if not cleaned:
            return None

        self._last_heard = cleaned

        # Lancuch ma pierwszenstwo, bo jest wezszy: kazdy czlon musi trafic
        # doslownie. Gdy sie nie sklada, zostaje zwykla pojedyncza komenda.
        matched: Any = None
        if self.settings.combo_enabled:
            sequence = self.mapping_manager.match_sequence(cleaned)
            if sequence:
                matched = sequence
        if matched is None:
            matched = self.mapping_manager.match_command(cleaned)

        self._emit({"type": "heard", "text": cleaned, "matched": matched, "time": time.strftime("%H:%M:%S")})

        if matched is None:
            log.debug("No match for '%s'", cleaned)
            return None

        self._last_command = cleaned
        self._execute(matched, cleaned)
        return matched

    def _resolve_key(self, action: str) -> str:
        """Akcja na faktyczny klawisz.

        "escape" i "random" nie sa nazwami klawiszy, wiec trzeba je zamienic.
        Dotyczy to tak samo pojedynczej komendy, jak i czlonu lancucha.
        """
        if action == "escape":
            return "esc"
        if action == "random":
            return random.choice(RANDOM_ABILITIES)
        return action

    def _execute(self, action, text: str) -> None:
        if isinstance(action, (list, tuple)):
            keys = [self._resolve_key(step) for step in action]
            log.info("Executed '%s' -> %s (chain)", text, " ".join(k.upper() for k in keys))
            for position, key in enumerate(keys):
                if position:
                    time.sleep(COMBO_DELAY)
                self.key_controller.press_key(key)
        elif isinstance(action, str):
            key = self._resolve_key(action)
            self.key_controller.press_key(key)
            log.info("Executed '%s' -> %s", text, key.upper())

    # --- cykl zycia ---------------------------------------------------

    def _ensure_controller(self):
        if self._controller is None:
            from controller.lol_whisp_controller import LoLVoiceController

            self._controller = LoLVoiceController(
                settings=self.settings,
                mapping_manager=self.mapping_manager,
                transcriber=self._engine_transcriber(),
                on_text=self.handle_transcript,
            )
        return self._controller

    def start(self) -> bool:
        """Laduje model i uruchamia nasluch. Idempotentne."""
        with self._lock:
            if self._listening:
                return True
            try:
                controller = self._ensure_controller()
                started = controller.start_listening()
            except Exception as exc:  # brak modelu albo mikrofonu
                self._last_error = str(exc)
                self._emit_log("error", f"Could not start listening: {exc}")
                self._emit_status()
                return False

            self._listening = bool(started and controller.is_listening)
            if not self._listening:
                self._last_error = "audio stream unavailable"
                self._emit_log("error", "Could not start listening, audio stream unavailable")
            else:
                self._last_error = None
                log.info("Listening started")
            self._emit_status()
            return self._listening

    def stop(self) -> bool:
        """Zatrzymuje nasluch i zwalnia strumien audio."""
        with self._lock:
            if self._controller is not None:
                try:
                    self._controller.stop_listening()
                except Exception as exc:  # zamykanie nie moze rzucac dalej
                    log.warning("Error stopping controller: %s", exc)
            self._listening = False
            self._emit_status()
            return True

    @property
    def listening(self) -> bool:
        if self._controller is not None:
            return bool(self._controller.is_listening)
        return self._listening

    # --- ustawienia i silnik ------------------------------------------

    def apply_settings(self, settings: Settings) -> None:
        """Przyjmuje nowe ustawienia: przebudowa mapowan, ewentualne przeladowanie silnika."""
        with self._lock:
            previous = self._settings
            self._settings = settings
            self.mapping_manager.settings = settings
            if self._controller is not None:
                self._controller.settings = settings
                manager = getattr(self._controller, "ability_manager", None)
                if manager is not None:
                    try:
                        manager.set_language(settings.language)
                    except Exception as exc:
                        log.warning("Language switch failed: %s", exc)
            engine_changed = previous is not None and previous.engine_id != settings.engine_id
        if engine_changed:
            threading.Thread(target=self.reload_engine, daemon=True).start()
        self._emit_status()

    def reload_engine(self) -> bool:
        """Przeladowuje model bez restartu procesu."""
        with self._lock:
            was_listening = self.listening
            if was_listening:
                self.stop()
            self._engine = None
            try:
                engine = self._engine_transcriber()
            except Exception as exc:  # model moze byc niezainstalowany
                self._last_error = str(exc)
                self._emit_log("error", f"Engine reload failed: {exc}")
                return False
            if self._controller is not None:
                self._controller.transcriber = engine
            self._emit_log("info", f"Engine loaded: {engine.engine_id}")
        if was_listening:
            self.start()
        else:
            self._emit_status()
        return True

    def _active_engine(self) -> tuple[str, str]:
        """(engine_id, engine_name) bez rzucania, gdy nic nie jest zainstalowane."""
        try:
            engine = engines.resolve_active()
            return engine.id, engine.name
        except Exception:  # brak silnika to stan do pokazania w panelu
            configured = engines.get(self.settings.engine_id)
            return self.settings.engine_id, configured.name if configured else ""

    # --- odczyty dla panelu -------------------------------------------

    def status(self) -> dict:
        """Slownik zgodny z GET /status."""
        engine_id, engine_name = self._active_engine()
        controller = self._controller
        mode = self.mapping_manager.mode
        return {
            "listening": self.listening,
            "game_active": bool(getattr(controller, "game_active", False)),
            "champion": getattr(controller, "current_champion_name", None),
            "mode": mode,
            "engine_id": engine_id,
            "engine_name": engine_name,
            "version": version.get_version(),
            "mappings_count": len(self.mapping_manager.active_mappings),
            "last_command": self._last_command,
            "last_heard": self._last_heard,
            "update_available": self.update_available,
            "error": self._last_error,
        }

    def mappings(self) -> list[dict]:
        """Aktywne mapowania jako [{phrase, key, source}]."""
        return self.mapping_manager.describe_mappings()

    def champion(self) -> str | None:
        return getattr(self._controller, "current_champion_name", None)

    def set_update_available(self, available: bool) -> None:
        """Ustawia flage, ktora updater pokazuje w /status."""
        self.update_available = available
        self._emit_status()

    # --- audio --------------------------------------------------------

    def list_audio_devices(self) -> list[dict]:
        """Wejsciowe urzadzenia audio jako [{id, name, default}]."""
        try:
            import sounddevice as sd

            all_devices = list(sd.query_devices())
            default_input = sd.default.device[0] if sd.default.device else None
            # Nazwy w starych API sa uciete do 31 znakow, wiec domyslne
            # urzadzenie dopasowujemy po prefiksie nazwy.
            default_name = ""
            if default_input is not None and 0 <= default_input < len(all_devices):
                default_name = all_devices[default_input].get("name", "")

            # PortAudio wystawia kazde urzadzenie po kilka razy (MME,
            # DirectSound, WASAPI, WDM-KS). Pokazujemy tylko WASAPI, a gdy go
            # nie ma, pierwsze wystapienie danej nazwy.
            hostapis = list(sd.query_hostapis())
            wasapi = next((i for i, api in enumerate(hostapis) if "WASAPI" in api.get("name", "")), None)

            devices = []
            seen_names: set[str] = set()
            for index, info in enumerate(all_devices):
                if info.get("max_input_channels", 0) <= 0:
                    continue
                if wasapi is not None and info.get("hostapi") != wasapi:
                    continue
                name = info.get("name", f"device {index}")
                if name in seen_names:
                    continue
                seen_names.add(name)
                is_default = bool(default_name) and (
                    name == default_name or name.startswith(default_name) or default_name.startswith(name)
                )
                devices.append({"id": name, "name": name, "default": is_default})
            if not devices:
                for index, info in enumerate(all_devices):
                    if info.get("max_input_channels", 0) <= 0:
                        continue
                    name = info.get("name", f"device {index}")
                    if name in seen_names:
                        continue
                    seen_names.add(name)
                    devices.append({"id": str(index), "name": name, "default": index == default_input})
            return devices
        except Exception as exc:  # brak PortAudio to normalny stan w CI
            log.warning("Audio devices unavailable: %s", exc)
            return []

    def test_microphone(self, seconds: int = 3) -> dict:
        """Nagrywa krotka probke i zwraca {level 0..1, transcript}."""
        result: dict = {"level": 0.0, "transcript": ""}
        try:
            import numpy as np
            import sounddevice as sd

            from controller.lol_whisp_controller import resolve_audio_device

            device = resolve_audio_device(self.settings.audio_device)

            frames = int(16000 * max(1, seconds))
            recording = sd.rec(frames, samplerate=16000, channels=1, dtype="int16", device=device)
            sd.wait()
            audio = np.asarray(recording, dtype=np.int16).reshape(-1)
            if audio.size:
                rms = float(np.sqrt(np.mean((audio.astype(np.float32) / 32768.0) ** 2)))
                result["level"] = round(min(1.0, rms * 4.0), 4)
            pcm = audio.tobytes()
        except Exception as exc:  # brak mikrofonu ma wrocic jako blad, nie wyjatek
            log.warning("Microphone test failed: %s", exc)
            result["error"] = str(exc)
            return result

        try:
            result["transcript"] = self._transcribe(pcm)
        except Exception as exc:  # brak modelu nie psuje pomiaru poziomu
            log.warning("Microphone test transcription failed: %s", exc)
            result["error"] = str(exc)
        return result


_service: VoiceService | None = None
_service_lock = threading.Lock()


def get_service() -> VoiceService:
    """Singleton uzywany przez serwer i testy."""
    global _service
    with _service_lock:
        if _service is None:
            _service = VoiceService()
        return _service


def reset_service() -> None:
    """Kasuje singleton. Uzywane w testach, ktore przestawiaja LOLVOICE_HOME."""
    global _service
    with _service_lock:
        _service = None
