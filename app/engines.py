"""Speech engine registry: what is available, what is installed, how to fetch it."""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app import config, paths
from app.logging_setup import get_logger

log = get_logger("engines")

ProgressCallback = Callable[[str, int, int], None]


@dataclass
class Engine:
    id: str
    name: str
    backend: str
    file: Optional[str]
    url: Optional[str]
    size_bytes: int
    sha256: Optional[str]
    speed: str
    quality: str
    bundled: bool
    requires_cuda: bool
    description: dict = field(default_factory=dict)
    model: Optional[str] = None

    @property
    def needs_download(self) -> bool:
        return bool(self.url and self.file)

    def local_path(self) -> Optional[Path]:
        if not self.file:
            return None
        bundled = paths.bundled_dir() / "models" / self.file
        if bundled.is_file():
            return bundled
        return paths.MODELS_DIR / self.file

    def is_installed(self) -> bool:
        if self.backend == "faster-whisper":
            if self.requires_cuda and (not _cuda_available() or not _cuda_dlls_present()):
                return False
            return _faster_whisper_model_installed(self.model or "tiny")
        if not self.needs_download:
            return _cuda_available() if self.requires_cuda else True
        path = self.local_path()
        return bool(path and path.is_file() and path.stat().st_size > 0)


_registry_lock = threading.Lock()
_registry: Optional[list[Engine]] = None
_cancelled: set[str] = set()


def _registry_file() -> Path:
    return paths.bundled_dir() / "data" / "engines.json"


def load_registry(force: bool = False) -> list[Engine]:
    global _registry
    with _registry_lock:
        if _registry is not None and not force:
            return _registry
        raw = json.loads(_registry_file().read_text(encoding="utf-8"))
        _registry = [Engine(**entry) for entry in raw["engines"]]
        return _registry


def _cuda_available() -> bool:
    try:
        import ctranslate2

        return ctranslate2.get_cuda_device_count() > 0
    except Exception:  # noqa: BLE001 - absence of ctranslate2 is a normal state
        pass
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001 - absence of torch is a normal state
        return False


def faster_whisper_cache_dir() -> Path:
    return paths.MODELS_DIR / "faster-whisper"


def _faster_whisper_model_installed(model: str) -> bool:
    """True, gdy snapshot modelu Systran/faster-whisper-{model} lezy w cache."""
    root = faster_whisper_cache_dir() / f"models--Systran--faster-whisper-{model}"
    return any(root.glob("snapshots/*/model.bin"))


def cuda_runtime_dir() -> Path:
    """Katalog, do ktorego aplikacja sciaga biblioteki CUDA u uzytkownika."""
    return paths.DATA_DIR / "cuda" / "bin"


def _cuda_dll_dirs() -> list[Path]:
    """Katalogi z bibliotekami CUDA: nasz katalog danych i kola pip."""
    import sys

    dirs: list[Path] = []
    if cuda_runtime_dir().is_dir():
        dirs.append(cuda_runtime_dir())
    for site in (Path(sys.prefix) / "Lib" / "site-packages", Path(sys.prefix)):
        nvidia = site / "nvidia"
        if nvidia.is_dir():
            dirs.extend(sub / "bin" for sub in nvidia.iterdir() if (sub / "bin").is_dir())
    return dirs


def _cuda_dlls_present() -> bool:
    needed = ("cublas64_12.dll", "cudnn64_9.dll")
    dirs = _cuda_dll_dirs()
    return all(any((d / name).is_file() for d in dirs) for name in needed)


# Kola z PyPI to zwykle zipy. Sciagamy je bez pipa, wiec dziala tez w
# zainstalowanej aplikacji, i wypakowujemy same DLL-e.
_CUDA_WHEEL_PACKAGES = ("nvidia-cublas-cu12", "nvidia-cudnn-cu12")


def _resolve_wheel_url(package: str) -> tuple[str, int]:
    """(url, size) kola win_amd64 najnowszej wersji pakietu z PyPI."""
    import requests

    data = requests.get(f"https://pypi.org/pypi/{package}/json", timeout=30).json()
    for entry in data.get("urls", []):
        name = entry.get("filename", "")
        if name.endswith(".whl") and "win_amd64" in name:
            return entry["url"], int(entry.get("size") or 0)
    raise RuntimeError(f"No win_amd64 wheel for {package}")


def _resolve_cuda_wheels() -> list[tuple[str, str, int]]:
    return [(pkg, *_resolve_wheel_url(pkg)) for pkg in _CUDA_WHEEL_PACKAGES]


def _download_cuda_runtime(
    engine_id: str,
    wheels: list[tuple[str, str, int]],
    report: Optional[Callable[[int], None]] = None,
) -> None:
    """Sciaga cuBLAS i cuDNN do katalogu danych aplikacji.

    ``report`` dostaje laczna liczbe pobranych bajtow, zeby wolajacy mogl
    zlozyc z tego postep obejmujacy takze pobranie modelu.
    """
    import io
    import zipfile

    import requests

    target = cuda_runtime_dir()
    target.mkdir(parents=True, exist_ok=True)

    done = 0
    for pkg, url, _size in wheels:
        log.info("Downloading CUDA runtime %s", pkg)
        buffer = io.BytesIO()
        with requests.get(url, stream=True, timeout=60) as response:
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if engine_id in _cancelled:
                    raise InterruptedError(f"Download of {engine_id} cancelled")
                buffer.write(chunk)
                done += len(chunk)
                if report:
                    report(done)
        with zipfile.ZipFile(buffer) as wheel:
            for info in wheel.infolist():
                name = info.filename
                if name.endswith(".dll") and "/bin/" in name.replace("\\", "/"):
                    out = target / Path(name).name
                    with wheel.open(info) as src, out.open("wb") as dst:
                        while block := src.read(1024 * 1024):
                            dst.write(block)
    log.info("CUDA runtime ready in %s", target)


def prepare_cuda_runtime() -> None:
    """Dopina biblioteki cuBLAS/cuDNN z pakietow pip do procesu.

    ctranslate2 laduje je zwyklym LoadLibrary, wiec preladowanie przez ctypes
    i PATH wystarcza. Brak bibliotek nie jest bledem: moga byc systemowe.
    """
    import os

    dirs = _cuda_dll_dirs()
    if not dirs:
        return
    os.environ["PATH"] = os.pathsep.join(str(d) for d in dirs) + os.pathsep + os.environ.get("PATH", "")
    import ctypes

    for name in ("cublasLt64_12.dll", "cublas64_12.dll", "cudnn64_9.dll"):
        for directory in dirs:
            candidate = directory / name
            if candidate.is_file():
                try:
                    ctypes.WinDLL(str(candidate))
                except OSError as exc:
                    log.warning("Could not preload %s: %s", candidate, exc)
                break


def list_engines() -> list[dict]:
    """Registry plus install state, shaped for the panel."""
    settings = config.load()
    result = []
    for engine in load_registry():
        if engine.requires_cuda and not _cuda_available():
            continue
        result.append(
            {
                "id": engine.id,
                "name": engine.name,
                "backend": engine.backend,
                "speed": engine.speed,
                "quality": engine.quality,
                "size_bytes": engine.size_bytes,
                "installed": engine.is_installed(),
                "active": engine.id == settings.engine_id,
                "requires_cuda": engine.requires_cuda,
                "description": engine.description,
            }
        )
    return result


def get(engine_id: str) -> Optional[Engine]:
    for engine in load_registry():
        if engine.id == engine_id:
            return engine
    return None


def active_engine_id() -> str:
    return config.load().engine_id


def resolve_active() -> Engine:
    """The configured engine, falling back to the first installed one."""
    engine = get(active_engine_id())
    if engine and engine.is_installed():
        return engine
    for candidate in load_registry():
        if candidate.is_installed() and not candidate.requires_cuda:
            log.warning("Engine %s unavailable, falling back to %s", active_engine_id(), candidate.id)
            return candidate
    raise RuntimeError("No speech engine installed")


def cancel_download(engine_id: str) -> None:
    _cancelled.add(engine_id)


def ensure_faster_whisper_importable() -> None:
    """Import faster_whisper, w razie potrzeby bez PyAV.

    faster_whisper importuje av (dekoder plikow audio) na poziomie modulu, a
    Smart App Control potrafi zablokowac jego niepodpisane DLL-e. Aplikacja
    podaje gotowe tablice PCM, wiec dekoder nie jest potrzebny: przy
    zablokowanym av wstawiamy pusty stub.
    """
    import sys
    import types

    try:
        import faster_whisper  # noqa: F401

        return
    except ImportError as exc:
        try:
            import av  # noqa: F401

            raise exc  # av dziala, przyczyna lezy gdzie indziej
        except ImportError:
            pass

        log.warning("PyAV unavailable (%s), loading faster-whisper without it", exc)
        for name in [m for m in sys.modules if m == "av" or m.startswith(("av.", "faster_whisper"))]:
            del sys.modules[name]

        stub = types.ModuleType("av")
        stub.__version__ = "0.0.0-stub"

        def _blocked(*_args, **_kwargs):
            raise RuntimeError("PyAV is blocked on this system, only raw PCM input works")

        stub.open = _blocked
        audio_stub = types.ModuleType("av.audio")
        stub.audio = audio_stub
        sys.modules["av"] = stub
        sys.modules["av.audio"] = audio_stub
        import faster_whisper  # noqa: F401


def _download_faster_whisper(engine: Engine, progress: Optional[ProgressCallback] = None) -> Path:
    """Sciaga snapshot CTranslate2 z Hugging Face do naszego cache."""
    paths.ensure_dirs()
    cache = faster_whisper_cache_dir()
    cache.mkdir(parents=True, exist_ok=True)
    _cancelled.discard(engine.id)

    # Postep obejmuje obie fazy naraz: biblioteki CUDA i model. Inaczej pasek
    # dobiegal do konca, wracal do zera i zamieral na czas pobierania modelu.
    wheels: list[tuple[str, str, int]] = []
    if engine.requires_cuda and not _cuda_dlls_present():
        wheels = _resolve_cuda_wheels()
    cuda_total = sum(size for _pkg, _url, size in wheels)
    model_total = engine.size_bytes or 0
    total = cuda_total + model_total or 1

    if wheels:
        _download_cuda_runtime(
            engine.id,
            wheels,
            lambda done: progress(engine.id, done, total) if progress else None,
        )

    ensure_faster_whisper_importable()
    from faster_whisper.utils import download_model

    # download_model nie raportuje postepu, wiec podgladamy rosnacy katalog.
    watcher = _watch_directory_growth(engine.id, cache, cuda_total, total, progress)
    try:
        result = Path(download_model(engine.model or "tiny", cache_dir=str(cache)))
    finally:
        watcher.set()
    if progress:
        progress(engine.id, total, total)
    return result


def _watch_directory_growth(
    engine_id: str,
    directory: Path,
    offset: int,
    total: int,
    progress: Optional[ProgressCallback],
) -> threading.Event:
    """Raportuje postep na podstawie tego, ile przybylo na dysku."""
    stop = threading.Event()
    if progress is None:
        stop.set()
        return stop

    start_size = _directory_size(directory)

    def watch() -> None:
        while not stop.wait(1.0):
            grown = max(0, _directory_size(directory) - start_size)
            progress(engine_id, min(offset + grown, total - 1), total)

    threading.Thread(target=watch, name=f"progress-{engine_id}", daemon=True).start()
    return stop


def _directory_size(directory: Path) -> int:
    try:
        return sum(entry.stat().st_size for entry in directory.rglob("*") if entry.is_file())
    except OSError:
        return 0


def download(engine_id: str, progress: Optional[ProgressCallback] = None) -> Path:
    """Fetch a model with resume support and checksum verification."""
    import requests

    engine = get(engine_id)
    if engine is None:
        raise KeyError(engine_id)
    if engine.backend == "faster-whisper":
        return _download_faster_whisper(engine, progress)
    if not engine.needs_download:
        raise ValueError(f"Engine {engine_id} has no downloadable model")

    _cancelled.discard(engine_id)
    paths.ensure_dirs()
    target = paths.MODELS_DIR / engine.file
    partial = target.with_suffix(target.suffix + ".part")
    done = partial.stat().st_size if partial.is_file() else 0

    headers = {"Range": f"bytes={done}-"} if done else {}
    with requests.get(engine.url, headers=headers, stream=True, timeout=60) as response:
        if done and response.status_code == 200:
            done = 0  # Server ignored the range request, start over.
        response.raise_for_status()
        total = done + int(response.headers.get("Content-Length", engine.size_bytes or 0))
        mode = "ab" if done else "wb"
        with partial.open(mode) as handle:
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if engine_id in _cancelled:
                    log.info("Download of %s cancelled", engine_id)
                    raise InterruptedError(f"Download of {engine_id} cancelled")
                if not chunk:
                    continue
                handle.write(chunk)
                done += len(chunk)
                if progress:
                    progress(engine_id, done, total)

    if engine.sha256:
        digest = hashlib.sha256()
        with partial.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        if digest.hexdigest() != engine.sha256:
            partial.unlink(missing_ok=True)
            raise ValueError(f"Checksum mismatch for {engine_id}")

    partial.replace(target)
    log.info("Engine %s downloaded to %s", engine_id, target)
    return target


def remove(engine_id: str) -> bool:
    engine = get(engine_id)
    if engine is None or not engine.file:
        return False
    target = paths.MODELS_DIR / engine.file
    if target.is_file():
        target.unlink()
        return True
    return False
