"""Tests para src/asr/transcript_quality.py."""
from __future__ import annotations

from src.asr.transcript_quality import (
    FLAG_CARACTERES,
    FLAG_MUY_CORTA,
    FLAG_REPETITIVA,
    assess_transcript_quality,
    describe_quality_flags,
)

NORMAL_TRANSCRIPT = (
    "911 what is your emergency? There is a fire in my building on Main Street "
    "please send the fire department quickly. My neighbor is still inside the "
    "apartment and there is a lot of smoke coming out of the second floor."
)


class TestNormalTranscript:
    def test_no_flags(self):
        result = assess_transcript_quality(NORMAL_TRANSCRIPT)
        assert result["flags"] == []
        assert result["is_suspect"] is False

    def test_quality_score_maxima(self):
        result = assess_transcript_quality(NORMAL_TRANSCRIPT)
        assert result["quality_score"] == 1.0

    def test_word_count(self):
        result = assess_transcript_quality("uno dos tres cuatro")
        assert result["word_count"] == 4


class TestShortTranscript:
    def test_empty_text_flagged(self):
        result = assess_transcript_quality("")
        assert FLAG_MUY_CORTA in result["flags"]
        assert result["is_suspect"] is True
        assert result["quality_score"] <= 0.5

    def test_one_word_flagged(self):
        result = assess_transcript_quality("though")
        assert FLAG_MUY_CORTA in result["flags"]
        assert result["quality_score"] < 1.0

    def test_ten_words_not_flagged(self):
        result = assess_transcript_quality("one two three four five six seven eight nine ten")
        assert FLAG_MUY_CORTA not in result["flags"]


class TestRepetitiveTranscript:
    def test_whisper_loop_flagged(self):
        # Patron tipico de alucinacion: la misma frase repetida muchas veces.
        text = "can you hold on a second please " * 12
        result = assess_transcript_quality(text)
        assert FLAG_REPETITIVA in result["flags"]
        assert result["repetition_ratio"] > 0.05

    def test_normal_speech_not_flagged(self):
        result = assess_transcript_quality(NORMAL_TRANSCRIPT)
        assert FLAG_REPETITIVA not in result["flags"]

    def test_short_text_repetition_not_measured(self):
        # Con menos de 20 palabras la repeticion no es significativa.
        result = assess_transcript_quality("help help help help help")
        assert FLAG_REPETITIVA not in result["flags"]
        assert result["repetition_ratio"] == 0.0


class TestUnexpectedCharacters:
    def test_cyrillic_and_hangul_flagged(self):
        text = (
            "You may say hey alright merc поэтому you prefer to get champions "
            "to get 엄청 количе for the day and everything else in the call today"
        )
        result = assess_transcript_quality(text)
        assert FLAG_CARACTERES in result["flags"]

    def test_english_text_not_flagged(self):
        result = assess_transcript_quality(NORMAL_TRANSCRIPT)
        assert FLAG_CARACTERES not in result["flags"]

    def test_spanish_accents_not_flagged(self):
        text = (
            "por favor envíen una ambulancia rápido a la colonia centro hay un "
            "señor herido en la esquina de la avenida principal cerca del parque"
        )
        result = assess_transcript_quality(text)
        assert FLAG_CARACTERES not in result["flags"]


class TestQualityScore:
    def test_score_en_rango(self):
        for text in ("", "hola", NORMAL_TRANSCRIPT, "abc " * 100):
            result = assess_transcript_quality(text)
            assert 0.0 <= result["quality_score"] <= 1.0

    def test_mas_flags_menor_score(self):
        short = assess_transcript_quality("Title 4")
        normal = assess_transcript_quality(NORMAL_TRANSCRIPT)
        assert short["quality_score"] < normal["quality_score"]


class TestDescribeFlags:
    def test_flags_conocidos_legibles(self):
        text = describe_quality_flags([FLAG_MUY_CORTA, FLAG_REPETITIVA])
        assert "muy corta" in text
        assert "repetitivo" in text

    def test_flag_desconocido_se_conserva(self):
        assert describe_quality_flags(["otro_flag"]) == "otro_flag"
