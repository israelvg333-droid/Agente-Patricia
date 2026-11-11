"""Tests de integración end-to-end del pipeline completo (resuelve DT-9).

Ejecutan `run_pipeline` real desde la entrada hasta el JSON de salida:
- modo transcript-only sin mocks;
- modo audio con un .wav sintético y ASR simulado (Whisper es una dependencia
  externa pesada; el resto del pipeline —carga, features, indicadores, scoring,
  política y reporte— se ejecuta sin dobles de prueba).
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pytest
import soundfile as sf

import main as main_module
from src.scoring.decision_policy import VALID_RECOMMENDATIONS


def _make_args(**overrides) -> argparse.Namespace:
    base = {
        "audio": None,
        "transcript": None,
        "output_dir": None,
        "language": "es",
        "model": "tiny",
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _synthetic_voice(sample_rate: int = 16000, duration: float = 2.5) -> np.ndarray:
    """Tono de 220 Hz con vibrato y pausa central: F0 dentro del rango de voz."""
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    vibrato = 6.0 * np.sin(2 * np.pi * 5.0 * t)
    audio = 0.4 * np.sin(2 * np.pi * (220.0 * t + vibrato / (2 * np.pi)))
    # Pausa de 0.4 s en el centro para generar estadisticas de silencio.
    start = int(sample_rate * 1.0)
    audio[start : start + int(sample_rate * 0.4)] = 0.0
    return audio.astype(np.float32)


class TestPipelineTranscriptOnly:
    def test_generates_valid_json(self, tmp_path):
        transcript = tmp_path / "llamada.txt"
        transcript.write_text(
            "Necesito una ambulancia, mi esposo se desmayo y no respira, "
            "estamos en la calle Hidalgo 123.",
            encoding="utf-8",
        )
        args = _make_args(
            transcript=str(transcript), output_dir=str(tmp_path / "out")
        )

        output_path = main_module.run_pipeline(args)

        assert output_path.exists()
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["schema_version"] == "1.1"
        assert payload["input"]["mode"] == "transcript_only"
        assert payload["transcription"]["status"] == "ok"
        assert 0.0 <= payload["score"]["seriousness_score"] <= 1.0
        assert 0.0 <= payload["score"]["confidence"] <= 1.0
        assert payload["recommendation"] in VALID_RECOMMENDATIONS
        assert isinstance(payload["evidence"], list)

    def test_acoustic_features_marked_unavailable(self, tmp_path):
        transcript = tmp_path / "llamada.txt"
        transcript.write_text("Quiero reportar un incendio en mi casa.", "utf-8")
        args = _make_args(
            transcript=str(transcript), output_dir=str(tmp_path / "out")
        )

        payload = json.loads(
            main_module.run_pipeline(args).read_text(encoding="utf-8")
        )

        acoustic = payload["acoustic_features"]
        assert acoustic["duration_seconds"] is None
        indicators = acoustic["emergency_audio_indicators"]
        assert indicators["method"] == "not_available"
        assert indicators["seriousness_audio_score"] is None


class TestPipelineAudioMode:
    def test_full_pipeline_with_synthetic_wav(self, tmp_path, monkeypatch):
        sample_rate = 16000
        wav_path = tmp_path / "sintetico.wav"
        sf.write(wav_path, _synthetic_voice(sample_rate), sample_rate)

        def fake_transcribe(audio_path, language="es", model_name="tiny"):
            return {
                "text": "Auxilio hay un incendio en mi casa y hay personas adentro",
                "language": language,
                "model": model_name,
                "status": "ok",
            }

        monkeypatch.setattr(main_module, "transcribe_audio", fake_transcribe)
        args = _make_args(audio=str(wav_path), output_dir=str(tmp_path / "out"))

        output_path = main_module.run_pipeline(args)

        payload = json.loads(output_path.read_text(encoding="utf-8"))
        assert payload["input"]["mode"] == "audio"

        acoustic = payload["acoustic_features"]
        assert acoustic["duration_seconds"] == pytest.approx(2.5, abs=0.1)
        assert acoustic["rms_energy"] > 0
        # 220 Hz esta dentro del rango de voz humana configurado (70-600 Hz).
        assert acoustic["estimated_f0_hz"] is not None
        assert 150.0 <= acoustic["estimated_f0_hz"] <= 300.0
        assert acoustic["pause_count"] >= 1
        for key in (
            "estimated_jitter_ratio",
            "estimated_shimmer_ratio",
            "spectral_rolloff_hz",
            "spectral_bandwidth_hz",
            "spectral_flatness",
        ):
            assert key in acoustic, key

        indicators = acoustic["emergency_audio_indicators"]
        assert indicators["seriousness_audio_score"] is not None
        assert 0.0 <= indicators["audio_reliability"] <= 1.0
        assert "voice_tremor_score" in indicators

        assert payload["recommendation"] in VALID_RECOMMENDATIONS
        assert payload["score"]["audio_priority"] is not None

    def test_speech_rate_enriched_from_transcript(self, tmp_path, monkeypatch):
        sample_rate = 16000
        wav_path = tmp_path / "sintetico.wav"
        sf.write(wav_path, _synthetic_voice(sample_rate), sample_rate)
        monkeypatch.setattr(
            main_module,
            "transcribe_audio",
            lambda audio_path, language="es", model_name="tiny": {
                "text": "una dos tres cuatro cinco seis siete ocho",
                "language": language,
                "model": model_name,
                "status": "ok",
            },
        )
        args = _make_args(audio=str(wav_path), output_dir=str(tmp_path / "out"))

        payload = json.loads(
            main_module.run_pipeline(args).read_text(encoding="utf-8")
        )

        acoustic = payload["acoustic_features"]
        assert acoustic["word_count_from_transcript"] == 8
        # 8 palabras / 2.5 s = 192 wpm
        assert acoustic["approx_speech_rate"] == pytest.approx(192.0, abs=1.0)


class TestPipelineErrors:
    def test_requires_audio_or_transcript(self):
        with pytest.raises(ValueError):
            main_module.run_pipeline(_make_args())

    def test_missing_audio_file_raises(self, tmp_path):
        args = _make_args(audio=str(tmp_path / "no_existe.wav"))
        with pytest.raises(FileNotFoundError):
            main_module.run_pipeline(args)
