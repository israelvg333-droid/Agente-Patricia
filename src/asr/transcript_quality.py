"""Evaluacion heuristica de la calidad de una transcripcion ASR.

Whisper (especialmente el modelo tiny) puede producir transcripciones poco
confiables: bucles repetitivos (alucinacion), texto casi vacio o caracteres
fuera del alfabeto esperado. Estas transcripciones degradan el analisis
semantico sin que el pipeline lo advierta.

Este modulo NO altera la transcripcion ni la categoria asignada: produce un
diagnostico auditable (`quality_score`, `flags`, `is_suspect`) que las capas
superiores usan para calibrar la confianza y marcar llamadas para revision
manual. Umbrales derivados del analisis del dataset 911 (2026-07-08).
"""
from __future__ import annotations

import unicodedata
from collections import Counter
from typing import Any

from src.utils.helpers import clamp01

# Palabras minimas para considerar que hay contenido semantico analizable.
MIN_RELIABLE_WORDS = 10
# Proporcion maxima tolerada del 4-grama mas repetido (bucles de Whisper).
MAX_REPETITION_RATIO = 0.05
# Proporcion maxima de letras fuera del alfabeto latino (texto alucinado).
MAX_UNEXPECTED_CHAR_RATIO = 0.02
# Tamano del n-grama usado para medir repeticion.
_NGRAM_SIZE = 4
# Minimo de palabras para que la medicion de repeticion sea significativa.
_MIN_WORDS_FOR_REPETITION = 20

FLAG_MUY_CORTA = "transcripcion_muy_corta"
FLAG_REPETITIVA = "transcripcion_repetitiva"
FLAG_CARACTERES = "caracteres_inesperados"

_FLAG_DESCRIPTIONS = {
    FLAG_MUY_CORTA: "transcripcion muy corta",
    FLAG_REPETITIVA: "patron repetitivo compatible con alucinacion del ASR",
    FLAG_CARACTERES: "caracteres fuera del alfabeto esperado",
}


def assess_transcript_quality(text: str) -> dict[str, Any]:
    """Evalua senales de baja calidad en la transcripcion.

    Devuelve un dict con `word_count`, `repetition_ratio`,
    `unexpected_char_ratio`, `flags`, `quality_score` (0-1) e `is_suspect`.
    """
    words = (text or "").split()
    word_count = len(words)
    repetition = _repetition_ratio(words)
    unexpected = _unexpected_char_ratio(text or "")

    flags: list[str] = []
    if word_count < MIN_RELIABLE_WORDS:
        flags.append(FLAG_MUY_CORTA)
    if repetition > MAX_REPETITION_RATIO:
        flags.append(FLAG_REPETITIVA)
    if unexpected > MAX_UNEXPECTED_CHAR_RATIO:
        flags.append(FLAG_CARACTERES)

    penalty = 0.0
    if FLAG_MUY_CORTA in flags:
        penalty += 0.5 if word_count == 0 else 0.4
    if FLAG_REPETITIVA in flags:
        penalty += min(0.15 + repetition * 2.0, 0.4)
    if FLAG_CARACTERES in flags:
        penalty += min(0.15 + unexpected * 2.0, 0.4)

    return {
        "word_count": word_count,
        "repetition_ratio": round(repetition, 4),
        "unexpected_char_ratio": round(unexpected, 4),
        "flags": flags,
        "quality_score": round(clamp01(1.0 - penalty), 3),
        "is_suspect": bool(flags),
    }


def describe_quality_flags(flags: list[str]) -> str:
    """Convierte los flags a una frase legible para justificaciones."""
    readable = [_FLAG_DESCRIPTIONS.get(flag, flag) for flag in flags]
    return "; ".join(readable)


def _repetition_ratio(words: list[str]) -> float:
    """Frecuencia relativa del n-grama mas repetido; 0.0 si hay pocas palabras."""
    if len(words) < _MIN_WORDS_FOR_REPETITION:
        return 0.0
    lowered = [w.lower() for w in words]
    ngrams = [
        " ".join(lowered[i : i + _NGRAM_SIZE])
        for i in range(len(lowered) - _NGRAM_SIZE + 1)
    ]
    most_common = Counter(ngrams).most_common(1)[0][1]
    return most_common / len(ngrams)


def _unexpected_char_ratio(text: str) -> float:
    """Proporcion de letras fuera del alfabeto latino (senal de alucinacion)."""
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    unexpected = sum(1 for ch in letters if not _is_latin(ch))
    return unexpected / len(letters)


def _is_latin(ch: str) -> bool:
    try:
        return "LATIN" in unicodedata.name(ch)
    except ValueError:
        return False
