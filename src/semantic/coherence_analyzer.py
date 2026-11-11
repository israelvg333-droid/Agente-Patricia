from __future__ import annotations

import re
from typing import Any

from src.semantic.text_analyzer import normalize_text

EVASIVE_PATTERNS = [
    # Spanish
    "no se", "quien sabe", "no quiero decir", "luego te digo", "no importa",
    "da igual", "adivina", "no tengo", "no recuerdo",
    # English
    "i don't know", "who knows", "i don't want to say", "never mind",
    "it doesn't matter", "doesn't matter", "forget it", "i forget",
    "i can't remember", "i have no idea", "i won't say",
]
CONTRADICTION_PATTERNS = [
    # Spanish
    ("no paso nada", "emergencia"),
    ("no hay heridos", "herido"),
    ("era broma", "ayuda"),
    ("mentira", "urgente"),
    # English
    ("nothing happened", "emergency"),
    ("no one is hurt", "injured"),
    ("it was a joke", "help"),
    ("just kidding", "urgent"),
    ("no one is injured", "bleeding"),
    ("everything is fine", "emergency"),
]
TOPIC_SHIFT_TERMS = [
    # Spanish
    "otra cosa", "cambiando de tema", "mejor hablemos", "saludos",
    "musica", "videojuego", "tarea",
    # English
    "anyway", "by the way", "changing the subject", "let's talk about",
    "music", "video game", "homework", "never mind that", "forget that",
]


def analyze_coherence(text: str) -> dict[str, Any]:
    normalized = normalize_text(text)
    sentences = [s.strip() for s in re.split(r"[.!?\n]+", normalized) if s.strip()]
    evasive = [p for p in EVASIVE_PATTERNS if p in normalized]
    contradictions = [
        f"{a} / {b}" for a, b in CONTRADICTION_PATTERNS if a in normalized and b in normalized
    ]
    topic_shifts = [term for term in TOPIC_SHIFT_TERMS if term in normalized]

    penalty = 0.0
    penalty += min(len(evasive) * 0.15, 0.35)
    penalty += min(len(contradictions) * 0.25, 0.5)
    penalty += min(len(topic_shifts) * 0.2, 0.4)
    if len(sentences) <= 1 and len(normalized.split()) < 8:
        penalty += 0.15

    coherence_score = max(0.0, 1.0 - penalty)
    return {
        "coherence_score": round(coherence_score, 3),
        "evasive_responses": evasive,
        "simple_contradictions": contradictions,
        "topic_shift_markers": topic_shifts,
        "sentence_count": len(sentences),
    }
