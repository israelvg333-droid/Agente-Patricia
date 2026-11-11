"""Tests para src/semantic/text_analyzer.py."""
from __future__ import annotations

from src.semantic.text_analyzer import (
    _find_terms,
    _has_address_like_text,
    analyze_text,
    normalize_text,
)


class TestNormalizeText:
    def test_lowercase(self):
        assert normalize_text("EMERGENCIA") == "emergencia"

    def test_removes_accents(self):
        assert normalize_text("médico") == "medico"
        assert normalize_text("incéndio") == "incendio"

    def test_empty_string(self):
        assert normalize_text("") == ""

    def test_mixed(self):
        result = normalize_text("Señor, ¿Hay heridos?")
        assert "senor" in result
        assert "hay" in result
        assert "heridos" in result


class TestFindTerms:
    def test_finds_single_word(self):
        found = _find_terms("hubo un accidente grave", {"accidente", "fuego"})
        assert "accidente" in found
        assert "fuego" not in found

    def test_finds_multiword_phrase(self):
        found = _find_terms("era broma lo que dije", {"era broma", "emergencia"})
        assert "era broma" in found

    def test_word_boundary_respected(self):
        found = _find_terms("ayudando al paciente", {"ayuda"})
        assert "ayuda" not in found

    def test_empty_text(self):
        found = _find_terms("", {"emergencia"})
        assert found == []


class TestHasAddressLikeText:
    def test_detects_number(self):
        assert _has_address_like_text("en el numero 45 de la avenida") is True

    def test_detects_hash_number(self):
        assert _has_address_like_text("casa #12 del barrio") is True

    def test_no_address(self):
        assert _has_address_like_text("hubo un problema") is False


class TestAnalyzeText:
    def test_empty_text(self):
        result = analyze_text("")
        assert result["word_count"] == 0
        assert result["text_is_empty"] is True
        assert result["completeness_score"] == 0.0

    def test_emergency_keywords_detected(self):
        result = analyze_text(
            "Hay un herido en la calle principal número 5 colonia centro norte"
        )
        assert "herido" in result["emergency_keywords"]
        assert result["has_location"] is True
        assert result["word_count"] >= 12
        assert result["completeness_score"] > 0.5

    def test_joke_keywords_detected(self):
        result = analyze_text("jaja era una broma no paso nada")
        assert len(result["joke_or_mockery_keywords"]) > 0

    def test_incident_keywords_detected(self):
        result = analyze_text("hubo un choque en la carretera hay personas heridas")
        assert len(result["incident_keywords"]) > 0
        assert result["has_incident_type"] is True

    def test_completeness_all_items(self):
        text = (
            "Hay un accidente en la calle 5 colonia centro, "
            "hay un herido, una persona lesionada, "
            "necesito una ambulancia urgente por favor"
        )
        result = analyze_text(text)
        assert result["completeness_score"] == 1.0

    def test_completeness_partial(self):
        # Tiene tipo de incidente (choque) pero sin ubicación, sin víctima y pocas palabras
        result = analyze_text("hubo un choque y un accidente")
        assert 0.0 < result["completeness_score"] < 1.0

    def test_victim_hints_detected(self):
        result = analyze_text("hay una persona herida en la avenida")
        assert result["has_affected_people"] is True
