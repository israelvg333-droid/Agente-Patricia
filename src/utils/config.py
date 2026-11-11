from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
AUDIO_DIR = DATA_DIR / "audios"
OUTPUT_DIR = DATA_DIR / "outputs"


@dataclass(frozen=True)
class AudioAnalysisConfig:
    """Parametros acusticos ajustables sin tocar la logica del pipeline."""

    sample_rate: int = 16000
    f0_min_hz: float = 70.0
    f0_max_hz: float = 600.0
    analysis_window_seconds: float = 20.0
    high_speech_rate_wpm: float = 185.0
    low_speech_rate_wpm: float = 85.0
    high_energy_variability: float = 0.08
    long_pause_seconds: float = 2.0
    high_silence_ratio: float = 0.65
    low_snr_db: float = 8.0
    clipping_ratio: float = 0.01


@dataclass(frozen=True)
class AppConfig:
    sample_rate: int = 16000
    min_audio_seconds: float = 0.5
    output_dir: Path = OUTPUT_DIR
    audio_dir: Path = AUDIO_DIR
    audio_analysis: AudioAnalysisConfig = field(default_factory=AudioAnalysisConfig)


def ensure_directories() -> None:
    for path in (DATA_DIR, AUDIO_DIR, OUTPUT_DIR):
        path.mkdir(parents=True, exist_ok=True)
