"""Tests para src/scoring/decision_policy.py."""
from __future__ import annotations

from src.scoring.decision_policy import decide_recommendation


def _make_semantic(
    has_location=True,
    has_incident=True,
    completeness=0.75,
    emergency_kw=None,
    incident_kw=None,
    joke_kw=None,
):
    return {
        "has_location": has_location,
        "has_incident_type": has_incident,
        "completeness_score": completeness,
        "emergency_keywords": emergency_kw or [],
        "incident_keywords": incident_kw or ["accidente"],
        "joke_or_mockery_keywords": joke_kw or [],
        "completeness_items": {},
    }


def _make_intent(has_high_risk=False, intent="reporte_emergencia_o_incidente"):
    return {
        "intent": intent,
        "has_emergency_intent": True,
        "has_high_risk_terms": has_high_risk,
        "high_risk_terms": ["herido"] if has_high_risk else [],
    }


def _make_coherence(score=0.8):
    return {
        "coherence_score": score,
        "evasive_responses": [],
        "simple_contradictions": [],
        "topic_shift_markers": [],
    }


class TestDecideRecommendation:
    def test_high_risk_always_escalates(self):
        intent = _make_intent(has_high_risk=True)
        rec, evidence = decide_recommendation(
            0.3, 0.3, _make_semantic(), intent, _make_coherence()
        )
        assert rec == "escalar_humano"
        assert len(evidence) > 0

    def test_low_confidence_requests_more_info(self):
        rec, evidence = decide_recommendation(
            0.5, 0.2, _make_semantic(), _make_intent(), _make_coherence(),
            confidence=0.3,
        )
        assert rec == "pedir_mas_informacion"

    def test_complete_incident_continues(self):
        semantic = _make_semantic(has_location=True, has_incident=True, completeness=0.9)
        rec, evidence = decide_recommendation(
            0.7, 0.1, semantic, _make_intent(), _make_coherence(score=0.9),
            confidence=0.7,
        )
        assert rec == "continuar"

    def test_low_completeness_requests_more_info(self):
        semantic = _make_semantic(has_location=False, has_incident=False, completeness=0.25)
        rec, _ = decide_recommendation(
            0.3, 0.2, semantic, _make_intent(), _make_coherence(score=0.9),
            confidence=0.6,
        )
        assert rec == "pedir_mas_informacion"

    def test_joke_low_completeness_marks_improcedente(self):
        semantic = _make_semantic(
            has_location=False, has_incident=False, completeness=0.25,
            joke_kw=["jaja"], incident_kw=[]
        )
        intent = _make_intent(has_high_risk=False, intent="posible_broma_o_interaccion_improcedente")
        rec, _ = decide_recommendation(
            0.1, 0.85, semantic, intent, _make_coherence(score=0.3),
            confidence=0.6,
        )
        assert rec == "posible_improcedente"

    def test_acoustic_anomalies_low_completeness_improcedente(self):
        semantic = _make_semantic(
            has_location=False, has_incident=False, completeness=0.25
        )
        intent = _make_intent(has_high_risk=False)
        acoustic = {
            "acoustic_anomaly_flags": [
                "alta_proporcion_silencio",
                "energia_vocal_baja",
            ]
        }
        rec, _ = decide_recommendation(
            0.2, 0.4, semantic, intent, _make_coherence(score=0.4),
            acoustic=acoustic,
            confidence=0.6,
        )
        assert rec == "posible_improcedente"

    def test_high_audio_crisis_escalates_even_with_incomplete_text(self):
        semantic = _make_semantic(
            has_location=False, has_incident=False, completeness=0.25, incident_kw=[]
        )
        acoustic = {
            "emergency_audio_indicators": {
                "seriousness_audio_score": 0.78,
                "audio_reliability": 0.8,
                "indicator_flags": ["stress_vocal_alto", "urgencia_acustica_alta"],
            }
        }
        rec, evidence = decide_recommendation(
            0.7, 0.2, semantic, _make_intent(), _make_coherence(score=0.5),
            acoustic=acoustic,
            confidence=0.7,
        )

        assert rec == "escalar_humano"
        assert evidence

    def test_returns_tuple_with_list(self):
        rec, evidence = decide_recommendation(
            0.5, 0.5, _make_semantic(), _make_intent(), _make_coherence()
        )
        assert isinstance(rec, str)
        assert isinstance(evidence, list)
        assert rec in {
            "continuar",
            "pedir_mas_informacion",
            "escalar_humano",
            "posible_improcedente",
        }
