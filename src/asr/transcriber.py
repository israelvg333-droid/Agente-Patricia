from __future__ import annotations

from pathlib import Path
from typing import Any


def transcribe_audio(
    audio_path: str | Path, language: str = "es", model_name: str = "tiny"
) -> dict[str, Any]:
    path = Path(audio_path)
    try:
        import whisper
    except ImportError:
        return {
            "text": "",
            "engine": "fallback_required",
            "language": language,
            "status": "whisper_not_installed",
            "message": "Whisper no esta instalado. Use --transcript archivo.txt.",
        }

    try:
        model = whisper.load_model(model_name)
        result = _transcribe_with_fallback(model, path, language)
    except Exception as exc:
        return {
            "text": "",
            "engine": f"openai-whisper-local-{model_name}",
            "model": model_name,
            "language": language,
            "status": "whisper_error",
            "message": (
                "Whisper no pudo transcribir el audio. Verifique que ffmpeg este "
                f"instalado y disponible en PATH. Detalle: {exc}"
            ),
        }
    return {
        "text": (result.get("text") or "").strip(),
        "engine": f"openai-whisper-local-{model_name}",
        "model": model_name,
        "language": result.get("language", language),
        "status": "ok",
        "segments": result.get("segments", []),
    }


def _transcribe_with_fallback(model: Any, path: Path, language: str) -> dict[str, Any]:
    try:
        return model.transcribe(str(path), language=language)
    except FileNotFoundError:
        from src.audio.preprocessing import load_audio

        audio, _ = load_audio(path, sample_rate=16000)
        return model.transcribe(audio, language=language)


def read_manual_transcript(transcript_path: str | Path) -> dict[str, Any]:
    path = Path(transcript_path)
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo de transcripcion: {path}")
    if path.suffix.lower() != ".txt":
        raise ValueError("La transcripcion manual debe ser un archivo .txt")
    return {
        "text": path.read_text(encoding="utf-8").strip(),
        "engine": "manual_txt",
        "language": "es",
        "status": "ok",
        "source": str(path),
    }
