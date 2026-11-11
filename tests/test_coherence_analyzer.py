"""Tests para src/semantic/coherence_analyzer.py."""
from __future__ import annotations

from src.semantic.coherence_analyzer import analyze_coherence


class TestAnalyzeCoherence:
    def test_clean_coherent_text(self):
        text = (
            "Hay un accidente en la calle principal. "
            "Una persona está herida. Necesito una ambulancia."
        )
        result = analyze_coherence(text)
        assert result["coherence_score"] >= 0.8
        assert result["evasive_responses"] == []
        assert result["simple_contradictions"] == []

    def test_evasive_responses_detected(self):
        result = analyze_coherence("no se que paso, quien sabe, no quiero decir nada")
        assert len(result["evasive_responses"]) >= 2
        assert result["coherence_score"] < 1.0

    def test_contradiction_detected(self):
        result = analyze_coherence("no paso nada pero era una emergencia grave")
        assert len(result["simple_contradictions"]) > 0
        assert result["coherence_score"] < 0.8

    def test_topic_shift_detected(self):
        result = analyze_coherence("hay un problema serio, otra cosa, saludos a todos")
        assert len(result["topic_shift_markers"]) > 0

    def test_empty_text_low_coherence(self):
        result = analyze_coherence("")
        assert result["coherence_score"] <= 0.85
        assert result["sentence_count"] == 0

    def test_score_clamped_to_zero(self):
        text = (
            "no se, quien sabe, da igual, no importa, no recuerdo, "
            "era broma / ayuda, no paso nada / emergencia, "
            "mentira / urgente, otra cosa, saludos, musica"
        )
        result = analyze_coherence(text)
        assert result["coherence_score"] >= 0.0

    def test_score_range(self):
        for text in ["", "ayuda urgente", "hay un herido en la calle"]:
            result = analyze_coherence(text)
            assert 0.0 <= result["coherence_score"] <= 1.0

    def test_sentence_count(self):
        result = analyze_coherence("Primera oración. Segunda oración. Tercera.")
        assert result["sentence_count"] == 3
