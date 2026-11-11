"""Tests para src/audio/acoustic_features.py."""
from __future__ import annotations

import numpy as np

from src.audio.acoustic_features import (
    _detect_anomalies,
    _estimate_clipping,
    _estimate_quality,
    _zero_crossing_rate,
    empty_acoustic_features,
    enrich_with_text_rate,
    extract_acoustic_features,
)


class TestZeroCrossingRate:
    def test_constant_positive_signal(self):
        audio = np.ones(1000, dtype=np.float32)
        zcr = _zero_crossing_rate(audio)
        assert zcr == 0.0

    def test_alternating_signal(self):
        audio = np.array([1.0, -1.0, 1.0, -1.0], dtype=np.float32)
        zcr = _zero_crossing_rate(audio)
        assert zcr > 0.5

    def test_empty_audio(self):
        audio = np.array([], dtype=np.float32)
        zcr = _zero_crossing_rate(audio)
        assert zcr == 0.0


class TestEstimateClipping:
    def test_no_clipping(self):
        audio = np.zeros(1000, dtype=np.float32)
        assert _estimate_clipping(audio) == 0.0

    def test_full_clipping(self):
        audio = np.ones(1000, dtype=np.float32)
        assert _estimate_clipping(audio) == 1.0

    def test_partial_clipping(self):
        audio = np.array([0.5, 0.99, 1.0, 0.3, 0.98], dtype=np.float32)
        ratio = _estimate_clipping(audio)
        assert 0.0 < ratio < 1.0

    def test_empty_audio(self):
        audio = np.array([], dtype=np.float32)
        assert _estimate_clipping(audio) == 0.0


class TestEstimateQuality:
    def test_very_short_audio(self):
        quality = _estimate_quality(
            rms=0.1, peak=0.5, silence_ratio=0.1,
            duration=0.3, clipping_ratio=0.0, snr_db=20.0
        )
        assert quality == "muy_corta"

    def test_low_signal(self):
        quality = _estimate_quality(
            rms=0.001, peak=0.01, silence_ratio=0.1,
            duration=2.0, clipping_ratio=0.0, snr_db=20.0
        )
        assert quality == "baja_senal"

    def test_too_much_silence(self):
        quality = _estimate_quality(
            rms=0.1, peak=0.5, silence_ratio=0.8,
            duration=5.0, clipping_ratio=0.0, snr_db=20.0
        )
        assert quality == "mucho_silencio"

    def test_clipping(self):
        quality = _estimate_quality(
            rms=0.5, peak=0.999, silence_ratio=0.1,
            duration=5.0, clipping_ratio=0.05, snr_db=20.0
        )
        assert quality == "posible_saturacion"

    def test_high_noise(self):
        quality = _estimate_quality(
            rms=0.1, peak=0.5, silence_ratio=0.1,
            duration=5.0, clipping_ratio=0.0, snr_db=5.0
        )
        assert quality == "ruido_alto"

    def test_acceptable(self):
        quality = _estimate_quality(
            rms=0.1, peak=0.5, silence_ratio=0.1,
            duration=5.0, clipping_ratio=0.0, snr_db=20.0
        )
        assert quality == "aceptable"


class TestDetectAnomalies:
    def _call(self, **kwargs):
        defaults = dict(
            mean_energy=0.1, max_energy=0.3, silence_ratio=0.2,
            mean_pause_seconds=0.3, longest_pause_seconds=0.5,
            audio_quality="aceptable", clipping_ratio=0.0,
            snr_db=20.0, energy_std=0.02,
        )
        defaults.update(kwargs)
        return _detect_anomalies(**defaults)

    def test_no_anomalies_on_good_audio(self):
        flags = self._call()
        assert flags == []

    def test_high_silence_ratio(self):
        flags = self._call(silence_ratio=0.7)
        assert "alta_proporcion_silencio" in flags

    def test_low_energy(self):
        flags = self._call(mean_energy=0.01, max_energy=0.05)
        assert "energia_vocal_baja" in flags

    def test_long_pause(self):
        flags = self._call(longest_pause_seconds=3.0)
        assert "pausas_prolongadas" in flags

    def test_bad_quality_flag(self):
        flags = self._call(audio_quality="ruido_alto")
        assert "posible_mala_calidad_audio" in flags

    def test_clipping_flag(self):
        flags = self._call(clipping_ratio=0.05)
        assert "posible_clipping" in flags

    def test_low_snr_flag(self):
        flags = self._call(snr_db=5.0)
        assert "snr_bajo" in flags

    def test_energy_variability_flag(self):
        flags = self._call(energy_std=0.15)
        assert "variabilidad_acustica" in flags


class TestEmptyAcousticFeatures:
    def test_returns_dict(self):
        result = empty_acoustic_features()
        assert isinstance(result, dict)

    def test_has_required_fields(self):
        result = empty_acoustic_features()
        required = {
            "duration_seconds", "rms_energy", "mean_energy", "max_energy",
            "energy_std", "peak_amplitude", "zero_crossing_rate",
            "silence_ratio", "audio_quality", "acoustic_anomaly_flags",
            "mfcc_mean", "mfcc_std", "spectral_centroid_hz",
        }
        assert required.issubset(result.keys())

    def test_note_field(self):
        result = empty_acoustic_features("test_reason")
        assert result["note"] == "test_reason"

    def test_anomaly_flags_empty_list(self):
        result = empty_acoustic_features()
        assert result["acoustic_anomaly_flags"] == []

    def test_mfcc_fields_none(self):
        result = empty_acoustic_features()
        assert result["mfcc_mean"] is None
        assert result["mfcc_std"] is None


class TestEnrichWithTextRate:
    def test_adds_word_count(self):
        features = empty_acoustic_features()
        result = enrich_with_text_rate(features, "hola como estas bien")
        assert result["word_count_from_transcript"] == 4

    def test_speech_rate_none_when_no_duration(self):
        features = empty_acoustic_features()
        result = enrich_with_text_rate(features, "hola como estas")
        assert result["approx_speech_rate"] is None

    def test_speech_rate_calculated_with_duration(self):
        features = empty_acoustic_features()
        features["duration_seconds"] = 60.0
        result = enrich_with_text_rate(features, "hola como estas bien por favor")
        assert result["approx_speech_rate"] is not None
        assert result["approx_speech_rate"] > 0

    def test_empty_transcript(self):
        features = empty_acoustic_features()
        result = enrich_with_text_rate(features, "")
        assert result["word_count_from_transcript"] == 0


class TestExtractAcousticFeatures:
    def test_basic_extraction(self, sine_wave):
        audio, sr = sine_wave
        result = extract_acoustic_features(audio, sr)
        assert result["duration_seconds"] > 0
        assert result["rms_energy"] > 0
        assert isinstance(result["acoustic_anomaly_flags"], list)

    def test_mfcc_in_output(self, sine_wave):
        audio, sr = sine_wave
        result = extract_acoustic_features(audio, sr)
        assert "mfcc_mean" in result
        assert "mfcc_std" in result
        if result["mfcc_mean"] is not None:
            assert len(result["mfcc_mean"]) == 13

    def test_spectral_centroid_in_output(self, sine_wave):
        audio, sr = sine_wave
        result = extract_acoustic_features(audio, sr)
        assert "spectral_centroid_hz" in result

    def test_output_has_required_fields(self, sine_wave):
        audio, sr = sine_wave
        result = extract_acoustic_features(audio, sr)
        required = {
            "duration_seconds", "rms_energy", "mean_energy", "max_energy",
            "energy_std", "peak_amplitude", "zero_crossing_rate",
            "estimated_f0_hz", "silence_ratio", "pause_count",
            "audio_quality", "clipping_ratio", "acoustic_anomaly_flags",
            "mfcc_mean", "mfcc_std", "spectral_centroid_hz",
            "emergency_audio_indicators",
        }
        assert required.issubset(result.keys())

    def test_silence_wave_high_ratio(self, silence_wave):
        audio, sr = silence_wave
        result = extract_acoustic_features(audio, sr)
        assert result["silence_ratio"] > 0.5


class TestVoiceStabilityAndSpectralShape:
    """Features nuevas 2026-07-14: jitter/shimmer aproximados y forma espectral."""

    def test_new_keys_present_in_extraction(self, sine_wave):
        audio, sr = sine_wave
        result = extract_acoustic_features(audio, sr)
        for key in (
            "estimated_jitter_ratio",
            "estimated_shimmer_ratio",
            "spectral_rolloff_hz",
            "spectral_bandwidth_hz",
            "spectral_flatness",
        ):
            assert key in result, key

    def test_new_keys_none_in_empty(self):
        result = empty_acoustic_features()
        assert result["estimated_jitter_ratio"] is None
        assert result["estimated_shimmer_ratio"] is None
        assert result["spectral_rolloff_hz"] is None
        assert result["spectral_bandwidth_hz"] is None
        assert result["spectral_flatness"] is None

    def test_spectral_shape_values_for_sine(self, sine_wave):
        audio, sr = sine_wave
        result = extract_acoustic_features(audio, sr)
        assert result["spectral_rolloff_hz"] is not None
        assert result["spectral_rolloff_hz"] > 0
        assert result["spectral_bandwidth_hz"] is not None
        assert result["spectral_bandwidth_hz"] > 0
        assert result["spectral_flatness"] is not None
        assert 0.0 <= result["spectral_flatness"] <= 1.0

    def test_jitter_low_for_pure_sine(self, sine_wave):
        audio, sr = sine_wave
        result = extract_acoustic_features(audio, sr)
        # Una onda pura de 440 Hz no tiene perturbacion de F0 entre tramas.
        if result["estimated_jitter_ratio"] is not None:
            assert result["estimated_jitter_ratio"] < 0.02

    def test_shimmer_low_for_constant_amplitude(self, sine_wave):
        audio, sr = sine_wave
        result = extract_acoustic_features(audio, sr)
        if result["estimated_shimmer_ratio"] is not None:
            assert result["estimated_shimmer_ratio"] < 0.05

    def test_shimmer_none_for_silence(self, silence_wave):
        audio, sr = silence_wave
        result = extract_acoustic_features(audio, sr)
        assert result["estimated_shimmer_ratio"] is None
