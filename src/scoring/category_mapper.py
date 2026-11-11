"""Mapeo del score del pipeline a categorias operativas de dataset.

Convierte la salida de `score_call` (seriousness_score, improcedence_score,
confidence, recommendation, evidence) en una de tres categorias:

- SERIA: evidencia clara de emergencia real.
- DUDOSA: evidencia insuficiente o contradictoria.
- IMPROCEDENTE: claramente no corresponde a una emergencia.

El mapeo es una capa de presentacion sobre la politica de decision existente;
no altera el scoring ni la politica conservadora del proyecto.
"""
from __future__ import annotations

from typing import Any

from src.asr.transcript_quality import describe_quality_flags
from src.utils.helpers import clamp01

CATEGORIA_SERIA = "SERIA"
CATEGORIA_DUDOSA = "DUDOSA"
CATEGORIA_IMPROCEDENTE = "IMPROCEDENTE"

VALID_CATEGORIES = {CATEGORIA_SERIA, CATEGORIA_DUDOSA, CATEGORIA_IMPROCEDENTE}

_MAX_EVIDENCE_LINES = 3


def map_score_to_category(
    score: dict[str, Any],
    transcript_status: str = "ok",
    transcript_word_count: int = 0,
    transcript_quality: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Deriva categoria, confianza y justificacion desde el score del pipeline.

    `transcript_quality` (opcional) es la salida de
    `src.asr.transcript_quality.assess_transcript_quality`; cuando la
    transcripcion es sospechosa, solo reduce la confianza y lo documenta en la
    justificacion: la categoria nunca cambia por calidad de transcripcion.
    """
    seriousness = float(score.get("seriousness_score") or 0.0)
    improcedence = float(score.get("improcedence_score") or 0.0)
    base_confidence = float(score.get("confidence") or 0.0)
    recommendation = score.get("recommendation") or "pedir_mas_informacion"

    transcript_failed = transcript_status != "ok" or transcript_word_count == 0

    categoria, motivo = _decide_category(
        recommendation, seriousness, improcedence, transcript_failed
    )
    confianza = _category_confidence(categoria, seriousness, improcedence, base_confidence)
    justificacion = _build_justification(motivo, score.get("evidence") or [])
    confianza, justificacion = apply_transcript_quality_adjustment(
        confianza, justificacion, transcript_quality
    )

    return {
        "categoria": categoria,
        "confianza": round(confianza, 2),
        "justificacion": justificacion,
        "motivo_mapeo": motivo,
        "recommendation": recommendation,
    }


def apply_transcript_quality_adjustment(
    confianza: float,
    justificacion: str,
    transcript_quality: dict[str, Any] | None,
) -> tuple[float, str]:
    """Reduce la confianza cuando la transcripcion es sospechosa.

    Factor lineal en [0.5, 1.0] segun `quality_score`: una transcripcion
    perfecta no penaliza; una completamente degradada reduce la confianza a la
    mitad. Anexa la alerta a la justificacion para mantener trazabilidad.
    """
    if not transcript_quality or not transcript_quality.get("is_suspect"):
        return confianza, justificacion
    quality_score = float(transcript_quality.get("quality_score") or 0.0)
    adjusted = clamp01(confianza * (0.5 + 0.5 * quality_score))
    detail = describe_quality_flags(transcript_quality.get("flags") or [])
    note = f"Alerta de transcripcion ({detail}): confianza reducida."
    if note not in justificacion:
        justificacion = f"{justificacion} {note}".strip()
    return adjusted, justificacion


def _decide_category(
    recommendation: str,
    seriousness: float,
    improcedence: float,
    transcript_failed: bool,
) -> tuple[str, str]:
    if transcript_failed and seriousness < 0.6:
        return (
            CATEGORIA_DUDOSA,
            "Transcripcion vacia o fallida: no hay evidencia suficiente para decidir.",
        )
    if recommendation == "escalar_humano":
        return (
            CATEGORIA_SERIA,
            "Terminos o indicadores de alto riesgo: se trata como emergencia real.",
        )
    if recommendation == "continuar":
        return (
            CATEGORIA_SERIA,
            "Incidente, ubicacion y coherencia suficientes: reporte consistente con emergencia.",
        )
    if recommendation == "posible_improcedente":
        return (
            CATEGORIA_IMPROCEDENTE,
            "Senales de broma, incoherencia o ausencia de emergencia dominan el analisis.",
        )
    # recommendation == "pedir_mas_informacion" u otro valor desconocido.
    if seriousness >= 0.60 and improcedence < 0.50:
        return (
            CATEGORIA_SERIA,
            "Score de seriedad alto pese a informacion incompleta: se prioriza seguridad.",
        )
    if improcedence >= 0.65 and seriousness < 0.40:
        return (
            CATEGORIA_IMPROCEDENTE,
            "Score de improcedencia alto y seriedad baja sin terminos de riesgo.",
        )
    return (
        CATEGORIA_DUDOSA,
        "Evidencia insuficiente o ambigua para confirmar o descartar la emergencia.",
    )


def _category_confidence(
    categoria: str, seriousness: float, improcedence: float, base_confidence: float
) -> float:
    """Combina la confianza del pipeline con la fuerza de la categoria asignada."""
    if categoria == CATEGORIA_SERIA:
        strength = seriousness
    elif categoria == CATEGORIA_IMPROCEDENTE:
        strength = improcedence
    else:
        # En DUDOSA la ambiguedad misma es la senal: scores cercanos dan mas confianza.
        strength = 1.0 - abs(seriousness - improcedence)
    return clamp01(0.55 * base_confidence + 0.45 * strength)


def _build_justification(motivo: str, evidence: list[str]) -> str:
    lines = [motivo]
    seen = {motivo}
    for item in evidence:
        if item and item not in seen:
            lines.append(item)
            seen.add(item)
        if len(lines) >= 1 + _MAX_EVIDENCE_LINES:
            break
    return " ".join(lines)
