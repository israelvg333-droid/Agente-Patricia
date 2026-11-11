from __future__ import annotations

import pytest

from src.audio.emergency_indicators import (
    _audio_reliability,
    _invert,
    _mean_valid,
    _range,
    _score_above,
    _score_between,
    derive_emergency_audio_indicators,
    empty_emergency_audio_indicators,
)


def test_empty_indicators_are_explicitly_unavailable():
    result = empty_emergency_audio_indicators("sin_audio")

    assert result["seriousness_audio_score"] is None
    assert result["audio_reliability"] == 0.0
    assert result["method"] == "not_available"


def test_high_stress_audio_features_raise_audio_seriousness():
    features = {
        "duration_seconds": 18.0,
        "energy_std": 0.13,
        "mean_energy": 0.12,
        "max_energy": 0.55,
        "estimated_f0_hz": 250.0,
        "estimated_f0_min_hz": 110.0,
        "estimated_f0_max_hz": 390.0,
        "estimated_f0_std_hz": 85.0,
        "approx_speech_rate": 225.0,
        "silence_ratio": 0.12,
        "pause_count": 4,
        "longest_pause_seconds": 0.8,
        "estimated_snr_db": 20.0,
        "clipping_ratio": 0.0,
        "zero_crossing_rate": 0.12,
        "spectral_centroid_hz": 2600.0,
        "audio_quality": "aceptable",
    }

    result = derive_emergency_audio_indicators(features)

    assert result["seriousness_audio_score"] >= 0.6
    assert "stress_vocal_alto" in result["indicator_flags"]
    assert result["audio_reliability"] >= 0.8


def test_calm_features_keep_audio_seriousness_lower():
    features = {
        "duration_seconds": 20.0,
        "energy_std": 0.01,
        "mean_energy": 0.03,
        "max_energy": 0.1,
        "estimated_f0_hz": 150.0,
        "estimated_f0_min_hz": 130.0,
        "estimated_f0_max_hz": 170.0,
        "estimated_f0_std_hz": 8.0,
        "approx_speech_rate": 120.0,
        "silence_ratio": 0.25,
        "pause_count": 2,
        "longest_pause_seconds": 0.6,
        "estimated_snr_db": 18.0,
        "clipping_ratio": 0.0,
        "zero_crossing_rate": 0.04,
        "spectral_centroid_hz": 1400.0,
        "audio_quality": "aceptable",
    }

    result = derive_emergency_audio_indicators(features)

    assert result["seriousness_audio_score"] < 0.35
    assert result["calm_score"] >= 0.6


class TestScoreAbove:
    def test_below_low_is_zero(self):
        assert _score_above(0.01, 0.05, 0.2) == 0.0

    def test_above_high_is_one(self):
        assert _score_above(0.5, 0.05, 0.2) == 1.0

    def test_midpoint_is_half(self):
        assert _score_above(0.125, 0.05, 0.2) == pytest.approx(0.5)

    def test_none_propagates(self):
        assert _score_above(None, 0.05, 0.2) is None

    def test_degenerate_range_is_zero(self):
        assert _score_above(0.5, 0.2, 0.2) == 0.0


class TestScoreBetween:
    def test_inside_range_is_one(self):
        assert _score_between(120.0, 90.0, 165.0) == 1.0

    def test_far_outside_decreases(self):
        near = _score_between(170.0, 90.0, 165.0)
        far = _score_between(300.0, 90.0, 165.0)
        assert far < near < 1.0

    def test_none_propagates(self):
        assert _score_between(None, 90.0, 165.0) is None


class TestMeanValid:
    def test_ignores_none(self):
        assert _mean_valid((0.4, None, 0.8)) == pytest.approx(0.6)

    def test_all_none_is_zero(self):
        assert _mean_valid((None, None)) == 0.0

    def test_clamps_to_unit_range(self):
        assert _mean_valid((1.5, 1.5)) == 1.0


class TestSmallHelpers:
    def test_invert(self):
        assert _invert(0.3) == pytest.approx(0.7)
        assert _invert(None) is None

    def test_range(self):
        assert _range(100.0, 250.0) == 150.0
        assert _range(250.0, 100.0) == 0.0
        assert _range(None, 250.0) is None


class TestAudioReliability:
    def _features(self, quality="aceptable", duration=20.0):
        return {"audio_quality": quality, "duration_seconds": duration}

    def test_good_audio_high_reliability(self):
        score = _audio_reliability(self._features(), snr_db=20.0,
                                   clipping_ratio=0.0, silence_ratio=0.2)
        assert score >= 0.8

    def test_no_duration_zero_base(self):
        score = _audio_reliability(
            self._features(quality="no_evaluada", duration=None),
            snr_db=None, clipping_ratio=None, silence_ratio=None,
        )
        assert score == 0.0

    def test_bad_quality_penalized(self):
        good = _audio_reliability(self._features(), snr_db=20.0,
                                  clipping_ratio=0.0, silence_ratio=0.2)
        bad = _audio_reliability(self._features(quality="ruido_alto"), snr_db=5.0,
                                 clipping_ratio=0.05, silence_ratio=0.8)
        assert bad < good
        assert 0.0 <= bad <= 1.0


class TestIndicatorFlags:
    def test_low_reliability_flag_present(self):
        features = {
            "duration_seconds": 10.0,
            "audio_quality": "baja_senal",
            "mean_energy": 0.001,
            "max_energy": 0.01,
            "silence_ratio": 0.9,
        }
        result = derive_emergency_audio_indicators(features)
        assert "baja_confiabilidad_audio" in result["indicator_flags"]

    def test_scores_always_in_unit_range(self):
        features = {
            "duration_seconds": 15.0,
            "energy_std": 0.5,
            "mean_energy": 0.9,
            "max_energy": 1.0,
            "estimated_f0_std_hz": 300.0,
            "approx_speech_rate": 500.0,
            "audio_quality": "aceptable",
        }
        result = derive_emergency_audio_indicators(features)
        for key in ("stress_vocal_score", "urgency_score", "nervousness_score",
                    "desperation_score", "calm_score", "aggression_score",
                    "voice_instability_score", "audio_reliability",
                    "seriousness_audio_score"):
            assert 0.0 <= result[key] <= 1.0, key

    def test_features_vacios_no_fallan(self):
        result = derive_emergency_audio_indicators({})
        assert result["seriousness_audio_score"] == 0.0
        assert result["audio_reliability"] == 0.0
        assert "baja_confiabilidad_audio" in result["indicator_flags"]

class TestVoiceTremorScore:
    """Indicador nuevo 2026-07-14: temblor vocal desde jitter/shimmer aproximados."""

    def test_high_jitter_and_shimmer_give_high_tremor(self):
        features = {
            "duration_seconds": 10.0,
            "audio_quality": "aceptable",
            "estimated_jitter_ratio": 0.5,
            "estimated_shimmer_ratio": 0.4,
            "estimated_f0_std_hz": 130.0,
        }
        result = derive_emergency_audio_indicators(features)
        assert result["voice_tremor_score"] >= 0.65
        assert "temblor_vocal_probable" in result["indicator_flags"]

    def test_stable_voice_gives_low_tremor(self):
        features = {
            "duration_seconds": 10.0,
            "audio_quality": "aceptable",
            "estimated_jitter_ratio": 0.005,
            "estimated_shimmer_ratio": 0.02,
            "estimated_f0_std_hz": 5.0,
        }
        result = derive_emergency_audio_indicators(features)
        assert result["voice_tremor_score"] < 0.2
        assert "temblor_vocal_probable" not in result["indicator_flags"]

    def test_missing_jitter_shimmer_falls_back_to_f0_std(self):
        features = {
            "duration_seconds": 10.0,
            "audio_quality": "aceptable",
            "estimated_f0_std_hz": 120.0,
        }
        result = derive_emergency_audio_indicators(features)
        assert 0.0 <= result["voice_tremor_score"] <= 1.0
        assert result["voice_tremor_score"] > 0.5

    def test_all_missing_gives_zero_tremor(self):
        result = derive_emergency_audio_indicators({})
        assert result["voice_tremor_score"] == 0.0

    def test_tremor_does_not_change_seriousness_audio_score(self):
        base = {
            "duration_seconds": 12.0,
            "audio_quality": "aceptable",
            "energy_std": 0.06,
            "mean_energy": 0.05,
            "max_energy": 0.3,
            "estimated_f0_std_hz": 40.0,
            "silence_ratio": 0.3,
        }
        with_tremor = dict(base)
        with_tremor["estimated_jitter_ratio"] = 0.2
        with_tremor["estimated_shimmer_ratio"] = 0.6

        score_base = derive_emergency_audio_indicators(base)
        score_tremor = derive_emergency_audio_indicators(with_tremor)
        # El temblor es aditivo/informativo: no altera el score primario hasta
        # que se calibre con etiquetado manual (comparabilidad con dataset 911).
        assert (
            score_base["seriousness_audio_score"]
            == score_tremor["seriousness_audio_score"]
        )

    def test_empty_indicators_include_tremor_key(self):
        result = empty_emergency_audio_indicators()
        assert result["voice_tremor_score"] is None
