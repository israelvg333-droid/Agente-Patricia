from __future__ import annotations

from typing import Any

from src.utils.config import AudioAnalysisConfig
from src.utils.helpers import clamp01, optional_float


def derive_emergency_audio_indicators(
    features: dict[str, Any],
    config: AudioAnalysisConfig | None = None,
) -> dict[str, Any]:
    """Deriva indicadores paralinguisticos explicables para llamadas de emergencia.

    No reemplaza a un modelo SER entrenado. Provee una capa baseline auditable para
    priorizar audio sobre texto mientras se construye un dataset etiquetado.
    """

    cfg = config or AudioAnalysisConfig()
    energy_std = optional_float(features.get("energy_std"))
    mean_energy = optional_float(features.get("mean_energy"))
    max_energy = optional_float(features.get("max_energy"))
    f0_std = optional_float(features.get("estimated_f0_std_hz"))
    f0_mean = optional_float(features.get("estimated_f0_hz"))
    f0_range = _range(
        optional_float(features.get("estimated_f0_min_hz")),
        optional_float(features.get("estimated_f0_max_hz")),
    )
    speech_rate = optional_float(features.get("approx_speech_rate"))
    silence_ratio = optional_float(features.get("silence_ratio"))
    pause_count = optional_float(features.get("pause_count"))
    longest_pause = optional_float(features.get("longest_pause_seconds"))
    snr_db = optional_float(features.get("estimated_snr_db"))
    clipping_ratio = optional_float(features.get("clipping_ratio"))
    zcr = optional_float(features.get("zero_crossing_rate"))
    spectral_centroid = optional_float(features.get("spectral_centroid_hz"))
    jitter_ratio = optional_float(features.get("estimated_jitter_ratio"))
    shimmer_ratio = optional_float(features.get("estimated_shimmer_ratio"))

    stress = _mean_valid(
        (
            _score_above(energy_std, 0.035, 0.14),
            _score_above(f0_std, 18.0, 95.0),
            _score_above(f0_range, 60.0, 260.0),
            _score_above(speech_rate, cfg.high_speech_rate_wpm - 25.0, 260.0),
            _score_above(max_energy, 0.12, 0.55),
        )
    )
    urgency = _mean_valid(
        (
            _score_above(speech_rate, 135.0, 240.0),
            _score_above(mean_energy, 0.035, 0.16),
            _score_above(max_energy, 0.16, 0.6),
            _invert(_score_above(silence_ratio, 0.35, 0.75)),
        )
    )
    nervousness = _mean_valid(
        (
            _score_above(f0_std, 15.0, 85.0),
            _score_above(energy_std, 0.03, 0.12),
            _score_above(pause_count, 2.0, 18.0),
            _score_above(longest_pause, 0.8, 3.5),
            _score_above(zcr, 0.08, 0.25),
        )
    )
    desperation = _mean_valid(
        (
            stress,
            urgency,
            _score_above(f0_mean, 185.0, 360.0),
            _score_above(f0_range, 90.0, 280.0),
        )
    )
    calm = _mean_valid(
        (
            1.0 - stress,
            1.0 - nervousness,
            _score_between(speech_rate, 90.0, 165.0),
            _score_between(silence_ratio, 0.08, 0.45),
        )
    )
    aggression = _mean_valid(
        (
            _score_above(mean_energy, 0.07, 0.2),
            _score_above(max_energy, 0.25, 0.75),
            _score_above(spectral_centroid, 1800.0, 4200.0),
            _score_above(zcr, 0.09, 0.25),
        )
    )
    voice_instability = _mean_valid(
        (
            _score_above(f0_std, 20.0, 100.0),
            _score_above(f0_range, 80.0, 300.0),
            _score_above(energy_std, 0.035, 0.14),
        )
    )
    # Nuevo indicador aditivo (2026-07-14): temblor vocal desde jitter/shimmer
    # aproximados. No participa aun en seriousness_audio_score para preservar la
    # comparabilidad con el dataset 911 ya procesado; se integrara al score tras
    # la calibracion con etiquetado manual.
    # Umbrales ajustados a la distribucion observada en llamadas 911 reales
    # (jitter aproximado trama a trama ~0.12-0.45; el jitter clasico ciclo a
    # ciclo es un orden de magnitud menor y no aplica a esta aproximacion).
    voice_tremor = _mean_valid(
        (
            _score_above(jitter_ratio, 0.12, 0.45),
            _score_above(shimmer_ratio, 0.12, 0.32),
            _score_above(f0_std, 25.0, 110.0),
        )
    )
    audio_reliability = _audio_reliability(features, snr_db, clipping_ratio, silence_ratio)

    seriousness_from_audio = clamp01(
        0.3 * stress
        + 0.25 * urgency
        + 0.2 * nervousness
        + 0.15 * desperation
        + 0.1 * voice_instability
        - 0.12 * calm
    )
    if audio_reliability < 0.45:
        seriousness_from_audio *= 0.85

    flags = _indicator_flags(
        stress=stress,
        urgency=urgency,
        nervousness=nervousness,
        desperation=desperation,
        calm=calm,
        aggression=aggression,
        voice_instability=voice_instability,
        voice_tremor=voice_tremor,
        audio_reliability=audio_reliability,
    )

    return {
        "stress_vocal_score": round(stress, 3),
        "urgency_score": round(urgency, 3),
        "nervousness_score": round(nervousness, 3),
        "desperation_score": round(desperation, 3),
        "calm_score": round(calm, 3),
        "aggression_score": round(aggression, 3),
        "voice_instability_score": round(voice_instability, 3),
        "voice_tremor_score": round(voice_tremor, 3),
        "audio_reliability": round(audio_reliability, 3),
        "seriousness_audio_score": round(clamp01(seriousness_from_audio), 3),
        "indicator_flags": flags,
        "method": "heuristic_prosody_energy_pause_f0_baseline",
    }


def empty_emergency_audio_indicators(reason: str = "sin_audio") -> dict[str, Any]:
    return {
        "stress_vocal_score": None,
        "urgency_score": None,
        "nervousness_score": None,
        "desperation_score": None,
        "calm_score": None,
        "aggression_score": None,
        "voice_instability_score": None,
        "voice_tremor_score": None,
        "audio_reliability": 0.0,
        "seriousness_audio_score": None,
        "indicator_flags": [],
        "method": "not_available",
        "note": reason,
    }


def _audio_reliability(
    features: dict[str, Any],
    snr_db: float | None,
    clipping_ratio: float | None,
    silence_ratio: float | None,
) -> float:
    quality = features.get("audio_quality")
    score = 0.7 if features.get("duration_seconds") else 0.0
    if quality == "aceptable":
        score += 0.2
    if quality in {"baja_senal", "mucho_silencio", "ruido_alto", "posible_saturacion"}:
        score -= 0.2
    if snr_db is not None:
        score += 0.1 if snr_db >= 12.0 else -0.1
    if clipping_ratio is not None and clipping_ratio > 0.01:
        score -= 0.1
    if silence_ratio is not None and silence_ratio > 0.75:
        score -= 0.15
    return clamp01(score)


def _indicator_flags(**scores: float) -> list[str]:
    thresholds = {
        "stress_vocal_alto": scores["stress"] >= 0.65,
        "urgencia_acustica_alta": scores["urgency"] >= 0.65,
        "nerviosismo_alto": scores["nervousness"] >= 0.65,
        "desesperacion_probable": scores["desperation"] >= 0.7,
        "voz_inestable": scores["voice_instability"] >= 0.65,
        "temblor_vocal_probable": scores["voice_tremor"] >= 0.65,
        "calma_predominante": scores["calm"] >= 0.7,
        "agresividad_acustica": scores["aggression"] >= 0.7,
        "baja_confiabilidad_audio": scores["audio_reliability"] < 0.45,
    }
    return [name for name, enabled in thresholds.items() if enabled]


def _mean_valid(values: tuple[float | None, ...]) -> float:
    valid = [value for value in values if value is not None]
    if not valid:
        return 0.0
    return clamp01(sum(valid) / len(valid))


def _score_above(value: float | None, low: float, high: float) -> float | None:
    if value is None:
        return None
    if high <= low:
        return 0.0
    return clamp01((value - low) / (high - low))


def _score_between(value: float | None, low: float, high: float) -> float | None:
    if value is None:
        return None
    if low <= value <= high:
        return 1.0
    midpoint = (low + high) / 2.0
    distance = min(abs(value - low), abs(value - high))
    return clamp01(1.0 - distance / max(midpoint, 1.0))


def _invert(value: float | None) -> float | None:
    if value is None:
        return None
    return 1.0 - value


def _range(low: float | None, high: float | None) -> float | None:
    if low is None or high is None:
        return None
    return max(0.0, high - low)


