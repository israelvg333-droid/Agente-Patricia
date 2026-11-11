from __future__ import annotations

from pathlib import Path
from typing import Any

SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".wma"}


def validate_audio_path(audio_path: str | Path) -> Path:
    path = Path(audio_path)
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo de audio: {path}")
    if path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_AUDIO_EXTENSIONS))
        raise ValueError(f"Formato no soportado: {path.suffix}. Use {supported}")
    return path


def load_audio(audio_path: str | Path, sample_rate: int = 16000) -> tuple[Any, int]:
    """Carga audio con librosa si esta disponible."""
    path = validate_audio_path(audio_path)
    try:
        import librosa
    except ImportError as exc:
        raise RuntimeError(
            "Para analizar audio instale dependencias: pip install -r requirements.txt. "
            "Tambien puede usar --transcript para ejecutar solo el analisis textual."
        ) from exc

    try:
        audio, sr = librosa.load(path, sr=sample_rate, mono=True)
    except Exception as exc:
        raise RuntimeError(
            f"No se pudo cargar el audio {path}. Verifique que el formato sea valido "
            "y que ffmpeg/libsndfile pueda decodificarlo, especialmente para .mp3 o .m4a."
        ) from exc
    if audio.size == 0:
        raise ValueError("El archivo de audio no contiene muestras utiles.")
    return normalize_audio(audio), sr


def normalize_audio(audio: Any) -> Any:
    import numpy as np

    clean = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
    return np.clip(clean, -1.0, 1.0)
