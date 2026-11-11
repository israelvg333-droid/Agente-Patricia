from __future__ import annotations

from typing import Any


def analyze_intent(text_analysis: dict[str, Any]) -> dict[str, Any]:
    has_emergency = bool(text_analysis.get("emergency_keywords"))
    has_incident = bool(text_analysis.get("incident_keywords"))
    has_joke = bool(text_analysis.get("joke_or_mockery_keywords"))

    if has_emergency or has_incident:
        intent = "reporte_emergencia_o_incidente"
    elif has_joke:
        intent = "posible_broma_o_interaccion_improcedente"
    elif text_analysis.get("text_is_empty"):
        intent = "sin_contenido"
    else:
        intent = "indeterminado"

    risk_terms = {
        # Spanish
        "arma", "balazo", "disparo", "herido", "sangre", "incendio",
        "secuestro", "infarto", "ambulancia", "violencia",
        # English
        "gun", "weapon", "gunshot", "shot", "shooting", "injured", "bleeding",
        "blood", "fire", "kidnapping", "heart attack", "ambulance", "violence",
        "stabbing", "dead", "dying", "assault",
    }
    high_risk_matches = sorted(set(text_analysis.get("emergency_keywords", [])) & risk_terms)

    return {
        "intent": intent,
        "has_emergency_intent": has_emergency or has_incident,
        "has_high_risk_terms": bool(high_risk_matches),
        "high_risk_terms": high_risk_matches,
    }
