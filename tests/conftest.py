"""Fixtures compartidos para los tests del subagente de seriedad."""
from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture()
def sine_wave():
    """Audio sintético: onda seno de 440 Hz, 3 segundos, 16 kHz."""
    sample_rate = 16000
    duration = 3.0
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    audio = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    return audio, sample_rate


@pytest.fixture()
def silence_wave():
    """Audio sintético: silencio de 2 segundos, 16 kHz."""
    sample_rate = 16000
    audio = np.zeros(int(sample_rate * 2.0), dtype=np.float32)
    return audio, sample_rate


@pytest.fixture()
def empty_wave():
    """Array de audio vacío."""
    return np.array([], dtype=np.float32), 16000


@pytest.fixture()
def minimal_acoustic():
    """Features acústicas mínimas para pruebas de scoring (modo transcript-only)."""
    from src.audio.acoustic_features import empty_acoustic_features, enrich_with_text_rate
    return enrich_with_text_rate(
        empty_acoustic_features("test"), "llamada de prueba con información básica"
    )


@pytest.fixture()
def acoustic_with_anomalies():
    """Features acústicas con anomalías simuladas para pruebas de scoring."""
    return {
        "duration_seconds": 5.0,
        "rms_energy": 0.003,
        "mean_energy": 0.003,
        "max_energy": 0.01,
        "energy_std": 0.001,
        "peak_amplitude": 0.01,
        "zero_crossing_rate": 0.05,
        "silence_ratio": 0.8,
        "pause_count": 3,
        "mean_pause_seconds": 1.5,
        "longest_pause_seconds": 3.0,
        "silence": {
            "silence_ratio": 0.8,
            "pause_count": 3,
            "mean_pause_seconds": 1.5,
            "longest_pause_seconds": 3.0,
        },
        "audio_quality": "mucho_silencio",
        "clipping_ratio": 0.0,
        "estimated_snr_db": 5.0,
        "acoustic_anomaly_flags": [
            "alta_proporcion_silencio",
            "energia_vocal_baja",
            "pausas_prolongadas",
            "posible_mala_calidad_audio",
            "snr_bajo",
        ],
        "approx_speech_rate": None,
        "word_count_from_transcript": 5,
        "mfcc_mean": None,
        "mfcc_std": None,
        "spectral_centroid_hz": None,
        "estimated_f0_hz": None,
        "estimated_f0_min_hz": None,
        "estimated_f0_max_hz": None,
        "estimated_f0_std_hz": None,
        "estimated_tempo_bpm": None,
        "emergency_audio_indicators": {
            "stress_vocal_score": None,
            "urgency_score": None,
            "nervousness_score": None,
            "desperation_score": None,
            "calm_score": None,
            "aggression_score": None,
            "voice_instability_score": None,
            "audio_reliability": 0.0,
            "seriousness_audio_score": None,
            "indicator_flags": [],
            "method": "not_available",
            "note": "test",
        },
    }
