"""Tests para src/scoring/seriousness_scorer.py."""
from __future__ import annotations

from src.audio.acoustic_features import empty_acoustic_features, enrich_with_text_rate
from src.scoring.seriousness_scorer import (
    _estimate_confidence,
    _nested_float,
    score_call,
)
from src.utils.helpers import clamp01, optional_float


def _empty_acoustic(note="test"):
    return enrich_with_text_rate(empty_acoustic_features(note), "texto de prueba")


def _semantic_emergency():
    return {
        "word_count": 20,
        "emergency_keywords": ["ambulancia", "herido"],
        "incident_keywords": ["choque"],
        "joke_or_mockery_keywords": [],
        "has_location": True,
        "has_affected_people": True,
        "has_incident_type": True,
        "completeness_score": 1.0,
        "completeness_items": {},
        "text_is_empty": False,
    }


def _semantic_joke():
    return {
        "word_count": 8,
        "emergency_keywords": [],
        "incident_keywords": [],
        "joke_or_mockery_keywords": ["jaja", "era broma"],
        "has_location": False,
        "has_affected_people": False,
        "has_incident_type": False,
        "completeness_score": 0.0,
        "completeness_items": {},
        "text_is_empty": False,
    }


def _intent_emergency(high_risk=False):
    return {
        "intent": "reporte_emergencia_o_incidente",
        "has_emergency_intent": True,
        "has_high_risk_terms": high_risk,
        "high_risk_terms": ["herido"] if high_risk else [],
    }


def _intent_joke():
    return {
        "intent": "posible_broma_o_interaccion_improcedente",
        "has_emergency_intent": False,
        "has_high_risk_terms": False,
        "high_risk_terms": [],
    }


def _coherence_good():
    return {
        "coherence_score": 0.9,
        "evasive_responses": [],
        "simple_contradictions": [],
        "topic_shift_markers": [],
        "sentence_count": 3,
    }


def _coherence_bad():
    return {
        "coherence_score": 0.2,
        "evasive_responses": ["no se", "no recuerdo"],
        "simple_contradictions": ["era broma / ayuda"],
        "topic_shift_markers": ["otra cosa"],
        "sentence_count": 1,
    }


class TestClamp:
    def test_below_zero(self):
        assert clamp01(-0.5) == 0.0

    def test_above_one(self):
        assert clamp01(1.5) == 1.0

    def test_within_range(self):
        assert clamp01(0.7) == 0.7


class TestOptionalFloat:
    def test_none_returns_none(self):
        assert optional_float(None) is None

    def test_converts_int(self):
        assert optional_float(1) == 1.0

    def test_converts_float_string(self):
        assert optional_float(0.5) == 0.5


class TestNestedFloat:
    def test_extracts_nested(self):
        data = {"silence": {"silence_ratio": 0.3}}
        assert _nested_float(data, "silence", "silence_ratio") == 0.3

    def test_missing_key_returns_none(self):
        assert _nested_float({}, "silence", "silence_ratio") is None

    def test_non_dict_nested_returns_none(self):
        data = {"silence": "not_a_dict"}
        assert _nested_float(data, "silence", "silence_ratio") is None


class TestEstimateConfidence:
    def test_low_word_count_reduces_confidence(self):
        semantic = {"word_count": 3, "completeness_score": 0.0}
        coherence = {"coherence_score": 0.5}
        conf = _estimate_confidence(_empty_acoustic(), semantic, coherence)
        assert conf < 0.6

    def test_many_words_increase_confidence(self):
        semantic = {"word_count": 20, "completeness_score": 0.8}
        coherence = {"coherence_score": 0.9}
        conf = _estimate_confidence(_empty_acoustic(), semantic, coherence)
        assert conf >= 0.5

    def test_confidence_clamped(self):
        semantic = {"word_count": 100, "completeness_score": 1.0}
        coherence = {"coherence_score": 1.0}
        conf = _estimate_confidence(_empty_acoustic(), semantic, coherence)
        assert 0.0 <= conf <= 1.0

    def test_anomaly_flags_reduce_confidence(self):
        acoustic = _empty_acoustic()
        acoustic["acoustic_anomaly_flags"] = ["snr_bajo", "energia_vocal_baja", "alta_proporcion_silencio"]
        acoustic["audio_quality"] = "baja_senal"
        semantic = {"word_count": 15, "completeness_score": 0.5}
        coherence = {"coherence_score": 0.6}
        conf_clean = _estimate_confidence(_empty_acoustic(), semantic, coherence)
        conf_noisy = _estimate_confidence(acoustic, semantic, coherence)
        assert conf_noisy < conf_clean


class TestScoreCall:
    def test_emergency_call_high_seriousness(self):
        result = score_call(
            _empty_acoustic(),
            _semantic_emergency(),
            _intent_emergency(high_risk=True),
            _coherence_good(),
        )
        assert result["seriousness_score"] >= 0.7
        assert result["improcedence_score"] < 0.4
        assert result["recommendation"] == "escalar_humano"

    def test_joke_call_low_seriousness(self):
        result = score_call(
            _empty_acoustic(),
            _semantic_joke(),
            _intent_joke(),
            _coherence_bad(),
        )
        assert result["seriousness_score"] < 0.5
        assert result["improcedence_score"] >= result["seriousness_score"]

    def test_non_emergency_semantic_details_do_not_inflate_seriousness(self):
        acoustic = {
            "duration_seconds": 670.0,
            "mean_energy": 0.051,
            "max_energy": 0.369,
            "energy_std": 0.074,
            "longest_pause_seconds": 68.0,
            "silence": {"silence_ratio": 0.64},
            "audio_quality": "posible_saturacion",
            "clipping_ratio": 0.0,
            "estimated_snr_db": 57.0,
            "acoustic_anomaly_flags": [
                "pausas_prolongadas",
                "posible_mala_calidad_audio",
            ],
            "emergency_audio_indicators": {
                "seriousness_audio_score": 0.453,
                "audio_reliability": 0.6,
                "stress_vocal_score": 0.583,
                "urgency_score": 0.219,
                "nervousness_score": 0.738,
                "calm_score": 0.573,
                "indicator_flags": ["nerviosismo_alto", "voz_inestable"],
            },
        }
        semantic = {
            "word_count": 762,
            "emergency_keywords": [],
            "incident_keywords": [],
            "joke_or_mockery_keywords": [],
            "has_location": True,
            "has_affected_people": True,
            "has_incident_type": False,
            "completeness_score": 0.75,
            "completeness_items": {},
            "text_is_empty": False,
        }
        intent = {
            "intent": "indeterminado",
            "has_emergency_intent": False,
            "has_high_risk_terms": False,
            "high_risk_terms": [],
        }
        coherence = {
            "coherence_score": 0.7,
            "evasive_responses": ["no se", "no tengo"],
            "simple_contradictions": [],
            "topic_shift_markers": [],
            "sentence_count": 96,
        }

        result = score_call(acoustic, semantic, intent, coherence)

        assert result["seriousness_score"] < 0.5
        assert result["audio_priority"]["seriousness_audio_score"] == 0.453

    def test_output_fields_present(self):
        result = score_call(
            _empty_acoustic(),
            _semantic_emergency(),
            _intent_emergency(),
            _coherence_good(),
        )
        required = {
            "seriousness_score",
            "improcedence_score",
            "confidence",
            "recommendation",
            "evidence",
            "safety_note",
        }
        assert required.issubset(result.keys())

    def test_scores_in_range(self):
        result = score_call(
            _empty_acoustic(),
            _semantic_emergency(),
            _intent_emergency(),
            _coherence_good(),
        )
        assert 0.0 <= result["seriousness_score"] <= 1.0
        assert 0.0 <= result["improcedence_score"] <= 1.0
        assert 0.0 <= result["confidence"] <= 1.0

    def test_recommendation_is_valid(self):
        valid = {"continuar", "pedir_mas_informacion", "escalar_humano", "posible_improcedente"}
        result = score_call(
            _empty_acoustic(),
            _semantic_emergency(),
            _intent_emergency(),
            _coherence_good(),
        )
        assert result["recommendation"] in valid

    def test_evidence_is_list(self):
        result = score_call(
            _empty_acoustic(),
            _semantic_joke(),
            _intent_joke(),
            _coherence_bad(),
        )
        assert isinstance(result["evidence"], list)
