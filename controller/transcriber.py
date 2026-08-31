"""Zamiana surowego PCM na tekst.

Model jest wybierany przez app.engines.resolve_active(), wiec nie ma tu zadnej
zaszytej sciezki do pliku. Wszystkie ciezkie importy (pywhispercpp,
faster_whisper, numpy) siedza w metodach, zeby modul dal sie zaimportowac w CI.
"""

from __future__ import annotations

import re
from typing import Any

from app import engines
from app.logging_setup import get_logger

log = get_logger("transcriber")

_CLEAN_PATTERN = re.compile(r"[^\w\sąćęłńóśźż]")


def clean_text(text: str) -> str:
    """Male litery, bez interpunkcji, bez bialych znakow na brzegach."""
    return _CLEAN_PATTERN.sub("", (text or "").lower().strip()).strip()


def whisper_language(language: str) -> str:
    """pl_PL -> pl, en_US -> en."""
    return (language or "pl_PL").split("_")[0].lower()


class Transcriber:
    """Cienka fasada nad backendami Whispera."""

    def __init__(self, engine_id: str | None = None, n_threads: int = 6) -> None:
        self.engine_id = engine_id
        self.n_threads = n_threads
        self.backend: str | None = None
        self.engine: Any | None = None
        self.model: Any | None = None

    @property
    def loaded(self) -> bool:
        return self.model is not None

    def load(self) -> None:
        """Laduje aktywny silnik. Rzuca RuntimeError, gdy nic nie da sie zaladowac."""
        engine = engines.get(self.engine_id) if self.engine_id else None
        if engine is None or not engine.is_installed():
            engine = engines.resolve_active()

        try:
            self._load_engine(engine)
            return
        except Exception as exc:
            # Zablokowany DLL albo uszkodzony model nie moze konczyc sprawy,
            # gdy inny zainstalowany silnik jest w stanie dzialac.
            log.warning("Engine %s failed to load (%s), trying the other installed engines", engine.id, exc)
            for candidate in engines.load_registry():
                if candidate.id == engine.id or not candidate.is_installed():
                    continue
                try:
                    self._load_engine(candidate)
                    log.warning("Fell back to engine %s", candidate.id)
                    return
                except Exception as fallback_exc:
                    log.warning("Fallback engine %s failed too: %s", candidate.id, fallback_exc)
            raise

    def _load_engine(self, engine) -> None:
        if engine.backend == "pywhispercpp":
            self._load_pywhispercpp(engine)
        elif engine.backend == "faster-whisper":
            self._load_faster_whisper(engine)
        else:
            raise RuntimeError(f"Unknown engine backend: {engine.backend}")
        self.engine = engine
        self.engine_id = engine.id

    def _load_pywhispercpp(self, engine) -> None:
        import pywhispercpp.model as pw

        model_path = engine.local_path()
        if model_path is None or not model_path.is_file():
            raise RuntimeError(f"Model file missing for engine {engine.id}")
        # Nowsze wydania nazywaja klase Model, starsze Whisper.
        factory = getattr(pw, "Model", None) or getattr(pw, "Whisper", None)
        if factory is None:
            raise RuntimeError("pywhispercpp has no Model class")
        self.model = factory(str(model_path), n_threads=self.n_threads)
        self.backend = "pywhispercpp"
        log.info("Loaded engine %s from %s", engine.id, model_path)

    @staticmethod
    def _import_faster_whisper():
        """WhisperModel z obejsciem zablokowanego PyAV, patrz app.engines."""
        engines.ensure_faster_whisper_importable()
        from faster_whisper import WhisperModel

        return WhisperModel

    def _load_faster_whisper(self, engine) -> None:
        WhisperModel = self._import_faster_whisper()
        name = engine.model or "tiny"
        device = "cuda" if engine.requires_cuda else "cpu"
        if device == "cuda":
            engines.prepare_cuda_runtime()
        download_root = str(engines.faster_whisper_cache_dir())

        if device == "cuda":
            self.model = WhisperModel(name, device="cuda", compute_type="float16", download_root=download_root)
        else:
            self.model = WhisperModel(
                name, device="cpu", compute_type="int8", cpu_threads=self.n_threads, download_root=download_root
            )
        self.backend = f"faster-whisper-{device}"
        log.info("Loaded engine %s (faster-whisper, %s)", engine.id, device)

    def transcribe_pcm(self, pcm: bytes, language: str = "pl_PL") -> str:
        """PCM 16 kHz mono int16 na tekst."""
        import numpy as np

        if not pcm:
            return ""
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        return self.transcribe_array(audio, language)

    def transcribe_array(self, audio, language: str = "pl_PL") -> str:
        """Ten sam tor co transcribe_pcm, ale dla gotowej tablicy float32."""
        if not self.loaded:
            self.load()
        lang = whisper_language(language)

        if self.backend == "pywhispercpp":
            result = self.model.transcribe(audio, language=lang)
            segments = result[0] if isinstance(result, tuple) else result
            text = "".join(getattr(segment, "text", "") for segment in segments)
        elif (self.backend or "").startswith("faster-whisper"):
            segments, _info = self.model.transcribe(
                audio,
                language=lang,
                beam_size=1,
                best_of=1,
                temperature=0.0,
                vad_filter=False,
                without_timestamps=True,
                word_timestamps=False,
                condition_on_previous_text=False,
            )
            text = "".join(segment.text for segment in segments)
        else:
            raise RuntimeError("Transcriber not loaded")

        return clean_text(text)
