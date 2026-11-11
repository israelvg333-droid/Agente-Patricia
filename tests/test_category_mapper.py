"""Tests para src/scoring/category_mapper.py."""
from __future__ import annotations

from src.asr.transcript_quality import assess_transcript_quality
from src.scoring.category_mapper import (
    CATEGORIA_DUDOSA,
    CATEGORIA_IMPROCEDENTE,
    CATEGORIA_SERIA,
    VALID_CATEGORIES,
    apply_transcript_quality_adjustment,
    map_score_to_category,
)


def make_score(**overrides):
    score = {
        "seriousness_score": 0.5,
        "improcedence_score": 0.3,
        "confidence": 0.7,
        "recommendation": "pedir_mas_informacion",
        "evidence": ["Evidencia uno.", "Evidencia dos."],
    }
    score.update(overrides)
    return score


class TestDecideCategory:
    def test_escalar_humano_es_seria(self):
        result = map_score_to_category(make_score(recommendation="escalar_humano"),
                                       transcript_word_count=20)
        assert result["categoria"] == CATEGORIA_SERIA

    def test_continuar_es_seria(self):
        result = map_score_to_category(make_score(recommendation="continuar"),
                                       transcript_word_count=20)
        assert result["categoria"] == CATEGORIA_SERIA

    def test_posible_improcedente_es_improcedente(self):
        result = map_score_to_category(
            make_score(recommendation="posible_improcedente"),
            transcript_word_count=20,
        )
        assert result["categoria"] == CATEGORIA_IMPROCEDENTE

    def test_pedir_mas_informacion_ambiguo_es_dudosa(self):
        result = map_score_to_category(
            make_score(seriousness_score=0.5, improcedence_score=0.5),
            transcript_word_count=20,
        )
        assert result["categoria"] == CATEGORIA_DUDOSA

    def test_pedir_mas_informacion_seriedad_alta_es_seria(self):
        result = map_score_to_category(
            make_score(seriousness_score=0.72, improcedence_score=0.2),
            transcript_word_count=20,
        )
        assert result["categoria"] == CATEGORIA_SERIA

    def test_pedir_mas_informacion_improcedencia_alta_es_improcedente(self):
        result = map_score_to_category(
            make_score(seriousness_score=0.2, improcedence_score=0.8),
            transcript_word_count=20,
        )
        assert result["categoria"] == CATEGORIA_IMPROCEDENTE

    def test_transcripcion_fallida_cae_en_dudosa(self):
        result = map_score_to_category(
            make_score(recommendation="posible_improcedente", seriousness_score=0.2),
            transcript_status="error",
            transcript_word_count=0,
        )
        assert result["categoria"] == CATEGORIA_DUDOSA

    def test_transcripcion_vacia_con_audio_serio_mantiene_seria(self):
        result = map_score_to_category(
            make_score(recommendation="escalar_humano", seriousness_score=0.8),
            transcript_word_count=0,
        )
        assert result["categoria"] == CATEGORIA_SERIA

    def test_categoria_siempre_valida(self):
        for rec in ("escalar_humano", "continuar", "pedir_mas_informacion",
                    "posible_improcedente", "valor_desconocido"):
            result = map_score_to_category(make_score(recommendation=rec),
                                           transcript_word_count=20)
            assert result["categoria"] in VALID_CATEGORIES


class TestConfidenceAndJustification:
    def test_confianza_en_rango(self):
        result = map_score_to_category(make_score(), transcript_word_count=20)
        assert 0.0 <= result["confianza"] <= 1.0

    def test_confianza_sube_con_seriedad_fuerte(self):
        low = map_score_to_category(
            make_score(recommendation="escalar_humano", seriousness_score=0.5),
            transcript_word_count=20,
        )
        high = map_score_to_category(
            make_score(recommendation="escalar_humano", seriousness_score=0.95),
            transcript_word_count=20,
        )
        assert high["confianza"] > low["confianza"]

    def test_justificacion_incluye_motivo_y_evidencia(self):
        result = map_score_to_category(make_score(), transcript_word_count=20)
        assert result["justificacion"].startswith(result["motivo_mapeo"])
        assert "Evidencia uno." in result["justificacion"]

    def test_justificacion_limita_evidencia(self):
        score = make_score(evidence=[f"Linea {i}." for i in range(10)])
        result = map_score_to_category(score, transcript_word_count=20)
        assert result["justificacion"].count("Linea") <= 3

    def test_score_vacio_no_falla(self):
        result = map_score_to_category({}, transcript_word_count=0)
        assert result["categoria"] == CATEGORIA_DUDOSA
        assert 0.0 <= result["confianza"] <= 1.0


class TestTranscriptQualityAdjustment:
    def test_transcripcion_normal_no_penaliza(self):
        quality = assess_transcript_quality(
            "hay un incendio en la calle principal con personas heridas "
            "por favor envien bomberos y una ambulancia de inmediato"
        )
        base = map_score_to_category(make_score(), transcript_word_count=18)
        adjusted = map_score_to_category(
            make_score(), transcript_word_count=18, transcript_quality=quality
        )
        assert adjusted["confianza"] == base["confianza"]
        assert adjusted["justificacion"] == base["justificacion"]

    def test_transcripcion_sospechosa_reduce_confianza(self):
        quality = assess_transcript_quality("Title 4")
        base = map_score_to_category(make_score(), transcript_word_count=2)
        adjusted = map_score_to_category(
            make_score(), transcript_word_count=2, transcript_quality=quality
        )
        assert adjusted["confianza"] < base["confianza"]
        assert "Alerta de transcripcion" in adjusted["justificacion"]

    def test_categoria_no_cambia_por_calidad(self):
        quality = assess_transcript_quality("though")
        base = map_score_to_category(
            make_score(recommendation="escalar_humano"), transcript_word_count=1
        )
        adjusted = map_score_to_category(
            make_score(recommendation="escalar_humano"),
            transcript_word_count=1,
            transcript_quality=quality,
        )
        assert adjusted["categoria"] == base["categoria"] == CATEGORIA_SERIA

    def test_alerta_no_se_duplica_en_justificacion(self):
        quality = assess_transcript_quality("Title 4")
        conf1, just1 = apply_transcript_quality_adjustment(0.85, "Motivo.", quality)
        conf2, just2 = apply_transcript_quality_adjustment(conf1, just1, quality)
        assert conf1 < 0.85
        assert just2.count("Alerta de transcripcion") == 1

    def test_quality_none_no_penaliza(self):
        conf, just = apply_transcript_quality_adjustment(0.9, "Motivo.", None)
        assert conf == 0.9
        assert just == "Motivo."
