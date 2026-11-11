from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class SilenceStats:
    silence_ratio: float
    pause_count: int
    mean_pause_seconds: float
    longest_pause_seconds: float


def estimate_silence(
    audio: np.ndarray,
    sample_rate: int,
    frame_length: int = 2048,
    hop_length: int = 512,
    threshold_ratio: float = 0.08,
) -> SilenceStats:
    if audio.size == 0:
        return SilenceStats(1.0, 0, 0.0, 0.0)

    frames = _frame_audio(audio, frame_length, hop_length)
    if frames.size == 0:
        return SilenceStats(1.0, 0, 0.0, 0.0)

    rms = np.sqrt(np.mean(frames**2, axis=1))
    threshold = max(float(np.percentile(rms, 20)), float(np.max(rms)) * threshold_ratio)
    silent = rms <= threshold
    pause_lengths = _run_lengths(silent)
    pause_seconds = [length * hop_length / sample_rate for length in pause_lengths]

    return SilenceStats(
        silence_ratio=float(np.mean(silent)),
        pause_count=len(pause_seconds),
        mean_pause_seconds=float(np.mean(pause_seconds)) if pause_seconds else 0.0,
        longest_pause_seconds=float(np.max(pause_seconds)) if pause_seconds else 0.0,
    )


def _frame_audio(audio: np.ndarray, frame_length: int, hop_length: int) -> np.ndarray:
    if audio.size < frame_length:
        return audio.reshape(1, -1)
    frame_count = 1 + (len(audio) - frame_length) // hop_length
    return np.stack(
        [audio[i * hop_length : i * hop_length + frame_length] for i in range(frame_count)]
    )


def _run_lengths(mask: np.ndarray) -> list[int]:
    runs: list[int] = []
    current = 0
    for value in mask:
        if bool(value):
            current += 1
        elif current:
            runs.append(current)
            current = 0
    if current:
        runs.append(current)
    return runs
