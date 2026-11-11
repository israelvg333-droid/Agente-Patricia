from __future__ import annotations

from typing import Any

from src.utils.helpers import optional_float

VALID_RECOMMENDATIONS = {
    "continuar",
    "pedir_mas_informacion",
    "escalar_humano",
    "posible_improcedente",
}


def decide_recommendation(
    seriousness_score: float,
    improcedence_score: float,
    semantic: dict[str, Any],
    intent: dict[str, Any],
    coherence: dict[str, Any],
    acoustic: dict[str, Any] | None = None,
    confidence: float | None = None,
) -> tuple[str, list[str]]:
    evidence: list[str] = []
    acoustic = acoustic or {}
    has_location = bool(semantic.get("has_location"))
    has_incident = bool(semantic.get("has_incident_type"))
    completeness = float(semantic.get("completeness_score") or 0.0)
    coherence_score = float(coherence.get("coherence_score") or 0.0)
    has_joke = bool(semantic.get("joke_or_mockery_keywords"))
    anomaly_flags = set(acoustic.get("acoustic_anomaly_flags") or [])
    audio_indicators = acoustic.get("emergency_audio_indicators") or {}
    audio_seriousness = optional_float(audio_indicators.get("seriousness_audio_score"))
    audio_reliability = optional_float(audio_indicators.get("audio_reliability")) or 0.0
    indicator_flags = set(audio_indicators.get("indicator_flags") or [])

    if intent.get("has_high_risk_terms"):
        evidence.append("Se detectaron terminos de alto riesgo; se prioriza seguridad.")
        return "escalar_humano", evidence

    if (
        audio_seriousness is not None
        and audio_seriousness >= 0.72
        and audio_reliability >= 0.45
        and indicator_flags
        & {"stress_vocal_alto", "urgencia_acustica_alta", "desesperacion_probable"}
    ):
        evidence.append(
            "El audio muestra indicadores fuertes de crisis; se prioriza atencion humana."
        )
        return "escalar_humano", evidence

    if confidence is not None and confidence < 0.45:
        evidence.append("La confianza es baja; se debe pedir mas informacion.")
        return "pedir_mas_informacion", evidence

    if has_incident and has_location and coherence_score >= 0.55:
        evidence.append("Hay incidente, ubicacion y coherencia suficiente.")
        return "continuar", evidence

    if (
        audio_seriousness is not None
        and audio_seriousness >= 0.55
        and audio_reliability >= 0.45
        and completeness < 0.75
    ):
        evidence.append("El audio sugiere urgencia, pero falta informacion critica.")
        return "pedir_mas_informacion", evidence

    if (
        completeness < 0.5
        and coherence_score < 0.55
        and anomaly_flags
        and not intent.get("has_high_risk_terms")
        and not (audio_seriousness is not None and audio_seriousness >= 0.55)
    ):
        evidence.append(
            "Baja coherencia, baja completitud y senales acusticas anomalas."
        )
        return "posible_improcedente", evidence

    if improcedence_score >= 0.7 and has_joke and completeness < 0.5 and coherence_score < 0.6:
        evidence.append("Hay risas/broma, baja completitud y coherencia baja.")
        return "posible_improcedente", evidence

    if completeness < 0.75:
        evidence.append("Falta informacion critica para evaluar el reporte.")
        return "pedir_mas_informacion", evidence

    if seriousness_score < 0.45 and improcedence_score > 0.55:
        evidence.append("La estimacion sugiere baja seriedad, sin accion automatica de cierre.")
        return "posible_improcedente", evidence

    evidence.append("El caso conserva incertidumbre operativa.")
    return "pedir_mas_informacion", evidence
