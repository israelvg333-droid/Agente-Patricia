"""Tests para src/audio/preprocessing.py."""
from __future__ import annotations

import numpy as np
import pytest

from src.audio.preprocessing import normalize_audio, validate_audio_path


class TestValidateAudioPath:
    def test_nonexistent_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            validate_audio_path(tmp_path / "no_existe.wav")

    def test_invalid_extension_raises(self, tmp_path):
        f = tmp_path / "audio.xyz"
        f.write_bytes(b"dummy")
        with pytest.raises(ValueError, match="Formato no soportado"):
            validate_audio_path(f)

    def test_valid_ogg_extension(self, tmp_path):
        f = tmp_path / "audio.ogg"
        f.write_bytes(b"dummy")
        path = validate_audio_path(f)
        assert path == f

    def test_valid_wav_extension(self, tmp_path):
        f = tmp_path / "audio.wav"
        f.write_bytes(b"dummy")
        path = validate_audio_path(f)
        assert path == f

    def test_valid_mp3_extension(self, tmp_path):
        f = tmp_path / "audio.mp3"
        f.write_bytes(b"dummy")
        path = validate_audio_path(f)
        assert path == f

    def test_valid_m4a_extension(self, tmp_path):
        f = tmp_path / "audio.m4a"
        f.write_bytes(b"dummy")
        path = validate_audio_path(f)
        assert path == f

    def test_case_insensitive_extension(self, tmp_path):
        f = tmp_path / "audio.WAV"
        f.write_bytes(b"dummy")
        path = validate_audio_path(f)
        assert path == f


class TestNormalizeAudio:
    def test_clips_above_one(self):
        audio = np.array([2.0, -2.0, 0.5], dtype=np.float32)
        result = normalize_audio(audio)
        assert np.all(result <= 1.0)
        assert np.all(result >= -1.0)

    def test_replaces_nan(self):
        audio = np.array([np.nan, 0.5, -0.5], dtype=np.float32)
        result = normalize_audio(audio)
        assert not np.any(np.isnan(result))
        assert result[0] == 0.0

    def test_replaces_inf(self):
        audio = np.array([np.inf, -np.inf, 0.5], dtype=np.float32)
        result = normalize_audio(audio)
        assert not np.any(np.isinf(result))

    def test_output_dtype_float32(self):
        audio = np.array([0.1, 0.2, 0.3], dtype=np.float64)
        result = normalize_audio(audio)
        assert result.dtype == np.float32

    def test_valid_signal_unchanged(self):
        audio = np.array([0.1, -0.2, 0.3], dtype=np.float32)
        result = normalize_audio(audio)
        np.testing.assert_array_almost_equal(result, audio)
