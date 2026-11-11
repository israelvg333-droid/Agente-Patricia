"""Tests para src/audio/vad.py."""
from __future__ import annotations

import numpy as np

from src.audio.vad import SilenceStats, _frame_audio, _run_lengths, estimate_silence


class TestFrameAudio:
    def test_short_audio_single_frame(self):
        audio = np.ones(100, dtype=np.float32)
        frames = _frame_audio(audio, frame_length=512, hop_length=256)
        assert frames.shape == (1, 100)

    def test_normal_audio_multiple_frames(self):
        audio = np.ones(4096, dtype=np.float32)
        frames = _frame_audio(audio, frame_length=2048, hop_length=512)
        assert frames.shape[0] > 1
        assert frames.shape[1] == 2048


class TestRunLengths:
    def test_no_silent_frames(self):
        mask = np.array([False, False, False])
        assert _run_lengths(mask) == []

    def test_one_run(self):
        mask = np.array([True, True, True, False])
        assert _run_lengths(mask) == [3]

    def test_multiple_runs(self):
        mask = np.array([True, True, False, True, False])
        assert _run_lengths(mask) == [2, 1]

    def test_trailing_run(self):
        mask = np.array([False, True, True])
        assert _run_lengths(mask) == [2]


class TestEstimateSilence:
    def test_empty_audio(self, empty_wave):
        audio, sr = empty_wave
        result = estimate_silence(audio, sr)
        assert isinstance(result, SilenceStats)
        assert result.silence_ratio == 1.0
        assert result.pause_count == 0

    def test_pure_silence(self, silence_wave):
        audio, sr = silence_wave
        result = estimate_silence(audio, sr)
        assert result.silence_ratio == 1.0

    def test_sine_wave_not_all_silence(self, sine_wave):
        audio, sr = sine_wave
        result = estimate_silence(audio, sr)
        assert result.silence_ratio < 0.5

    def test_stats_types(self, sine_wave):
        audio, sr = sine_wave
        result = estimate_silence(audio, sr)
        assert isinstance(result.silence_ratio, float)
        assert isinstance(result.pause_count, int)
        assert isinstance(result.mean_pause_seconds, float)
        assert isinstance(result.longest_pause_seconds, float)

    def test_ratio_in_range(self, sine_wave):
        audio, sr = sine_wave
        result = estimate_silence(audio, sr)
        assert 0.0 <= result.silence_ratio <= 1.0
