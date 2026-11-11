from __future__ import annotations

from typing import Any

from src.scoring.decision_policy import decide_recommendation
from src.utils.helpers import clamp01, optional_float


def score_call(
    acoustic: dict[str, Any],
    semantic: dict[str, Any],
    intent: dict[str, Any],
    coherence: dict[str, Any],
) -> dict[str, Any]:
    evidence: list[str] = []
    completeness = float(semantic.get("completeness_score") or 0.0)
    coherence_score = float(coherence.get("coherence_score") or 0.0)
    has_emergency = bool(semantic.get("emergency_keywords") or semantic.get("incident_keywords"))
    has_location = bool(semantic.get("has_location"))
    has_joke = bool(semantic.get("joke_or_mockery_keywords"))
    silence_ratio = _nested_float(acoustic, "silence", "silence_ratio")
    mean_energy = optional_float(acoustic.get("mean_energy"))
    max_energy = optional_float(acoustic.get("max_energy"))
    clipping_ratio = optional_float(acoustic.get("clipping_ratio"))
    snr_db = optional_float(acoustic.get("estimated_snr_db"))
    longest_pause = optional_float(acoustic.get("longest_pause_seconds"))
    energy_std = optional_float(acoustic.get("energy_std"))
    anomaly_flags = set(acoustic.get("acoustic_anomaly_flags") or [])
    audio_quality = acoustic.get("audio_quality")
    audio_indicators = acoustic.get("emergency_audio_indicators") or {}
    audio_seriousness = optional_float(audio_indicators.get("seriousness_audio_score"))
    audio_reliability = optional_float(audio_indicators.get("audio_reliability"))
    stress_score = optional_float(audio_indicators.get("stress_vocal_score"))
    urgency_score = optional_float(audio_indicators.get("urgency_score"))
    nervousness_score = optional_float(audio_indicators.get("nervousness_score"))
    calm_score = optional_float(audio_indicators.get("calm_score"))
    indicator_flags = set(audio_indicators.get("indicator_flags") or [])
    has_reliable_audio_urgency = (
        audio_seriousness is not None
        and audio_seriousness >= 0.55
        and (audio_reliability or 0.0) >= 0.45
    )
    semantic_context_supports_seriousness = has_emergency or has_reliable_audio_urgency

    seriousness = 0.2
    if audio_seriousness is not None:
        reliability_weight = 0.55 if (audio_reliability or 0.0) >= 0.45 else 0.35
        seriousness += reliability_weight * audio_seriousness
    seriousness += 0.18 if has_emergency else 0.0
    if semantic_context_supports_seriousness:
        seriousness += 0.12 if has_location else 0.0
        seriousness += 0.12 * completeness
        seriousness += 0.08 * coherence_score
    seriousness += _acoustic_seriousness_adjustment(anomaly_flags, audio_quality)
    if calm_score is not None and calm_score >= 0.75 and not has_emergency:
        seriousness -= 0.08
    if intent.get("has_high_risk_terms"):
        seriousness += 0.2
        evidence.append("Terminos de alto riesgo presentes.")
    if has_joke:
        seriousness -= 0.25
        evidence.append("Se detectaron terminos asociados a broma o burla.")
    if silence_ratio is not None and silence_ratio > 0.65:
        seriousness -= 0.08
        evidence.append("Alta proporcion de silencio.")
    if (
        mean_energy is not None
        and max_energy is not None
        and mean_energy < 0.025
        and max_energy < 0.12
    ):
        seriousness -= 0.04
        evidence.append("Energia vocal baja.")
    if longest_pause is not None and longest_pause >= 2.0:
        seriousness -= 0.03
        evidence.append("Pausas prolongadas detectadas.")
    if energy_std is not None and energy_std > 0.08:
        evidence.append("Variabilidad acustica detectada.")
    evidence.extend(_audio_indicator_evidence(audio_indicators))
    if audio_quality in {"baja_senal", "mucho_silencio", "muy_corta"}:
        evidence.append("Audio con posible mala calidad.")
    if clipping_ratio is not None and clipping_ratio > 0.01:
        evidence.append("Posible clipping o saturacion en el audio.")
    if snr_db is not None and snr_db < 8.0:
        evidence.append("SNR aproximado bajo; posible ruido de fondo.")

    improcedence = 0.1
    improcedence += 0.35 if has_joke else 0.0
    improcedence += 0.2 if completeness < 0.5 else 0.0
    improcedence += 0.2 if coherence_score < 0.55 else 0.0
    improcedence += 0.1 if not has_emergency else 0.0
    improcedence += 0.1 if silence_ratio is not None and silence_ratio > 0.75 else 0.0
    improcedence += _acoustic_improcedence_adjustment(anomaly_flags, completeness, coherence_score)
    if calm_score is not None and calm_score >= 0.75 and not has_emergency:
        improcedence += 0.08
    if indicator_flags & {"stress_vocal_alto", "urgencia_acustica_alta", "desesperacion_probable"}:
        improcedence -= 0.08
    if intent.get("has_high_risk_terms"):
        improcedence -= 0.25

    seriousness = clamp01(seriousness)
    improcedence = clamp01(improcedence)
    confidence = _estimate_confidence(acoustic, semantic, coherence)
    recommendation, policy_evidence = decide_recommendation(
        seriousness,
        improcedence,
        semantic,
        intent,
        coherence,
        acoustic=acoustic,
        confidence=confidence,
    )
    evidence.extend(policy_evidence)
    evidence.extend(_semantic_evidence(semantic, intent, coherence))

    return {
        "seriousness_score": round(seriousness, 3),
        "improcedence_score": round(improcedence, 3),
        "confidence": round(confidence, 3),
        "recommendation": recommendation,
        "evidence": evidence,
        "audio_priority": {
            "used": audio_seriousness is not None,
            "seriousness_audio_score": audio_seriousness,
            "audio_reliability": audio_reliability,
            "stress_vocal_score": stress_score,
            "urgency_score": urgency_score,
            "nervousness_score": nervousness_score,
        },
        "safety_note": (
            "Estimacion probabilistica. No recomienda colgar ni cerrar llamadas automaticamente."
        ),
    }


def _semantic_evidence(
    semantic: dict[str, Any], intent: dict[str, Any], coherence: dict[str, Any]
) -> list[str]:
    evidence = []
    if semantic.get("emergency_keywords"):
        evidence.append(f"Palabras de emergencia: {', '.join(semantic['emergency_keywords'])}.")
    if semantic.get("incident_keywords"):
        evidence.append(f"Tipo de incidente detectado: {', '.join(semantic['incident_keywords'])}.")
    if semantic.get("has_location"):
        evidence.append("Se detecto posible ubicacion.")
    if semantic.get("has_affected_people"):
        evidence.append("Se mencionan posibles personas afectadas.")
    if coherence.get("evasive_responses"):
        evidence.append(f"Respuestas evasivas: {', '.join(coherence['evasive_responses'])}.")
    if coherence.get("simple_contradictions"):
        evidence.append("Se detectaron contradicciones simples.")
    if intent.get("intent"):
        evidence.append(f"Intencion estimada: {intent['intent']}.")
    return evidence


def _audio_indicator_evidence(indicators: dict[str, Any]) -> list[str]:
    flags = indicators.get("indicator_flags") or []
    if not flags:
        return []
    readable = {
        "stress_vocal_alto": "Stress vocal alto.",
        "urgencia_acustica_alta": "Urgencia acustica alta.",
        "nerviosismo_alto": "Nerviosismo vocal alto.",
        "desesperacion_probable": "Patron acustico compatible con desesperacion.",
        "voz_inestable": "Inestabilidad vocal elevada.",
        "calma_predominante": "Calma acustica predominante.",
        "agresividad_acustica": "Energia/espectro compatibles con agresividad acustica.",
        "baja_confiabilidad_audio": "Baja confiabilidad de los indicadores de audio.",
    }
    return [readable[flag] for flag in flags if flag in readable]


def _estimate_confidence(
    acoustic: dict[str, Any], semantic: dict[str, Any], coherence: dict[str, Any]
) -> float:
    confidence = 0.35
    if semantic.get("word_count", 0) >= 10:
        confidence += 0.2
    if acoustic.get("duration_seconds"):
        confidence += 0.18
    if acoustic.get("audio_quality") == "aceptable":
        confidence += 0.1
    indicators = acoustic.get("emergency_audio_indicators") or {}
    audio_reliability = optional_float(indicators.get("audio_reliability"))
    if audio_reliability is not None:
        confidence += 0.12 * audio_reliability
    low_quality = {"baja_senal", "mucho_silencio", "ruido_alto", "posible_saturacion"}
    if acoustic.get("audio_quality") in low_quality:
        confidence -= 0.1
    if acoustic.get("acoustic_anomaly_flags"):
        confidence -= min(len(acoustic["acoustic_anomaly_flags"]) * 0.03, 0.12)
    confidence += 0.1 * float(semantic.get("completeness_score") or 0.0)
    confidence += 0.1 * float(coherence.get("coherence_score") or 0.0)
    return clamp01(confidence)


def _nested_float(data: dict[str, Any], key: str, nested_key: str) -> float | None:
    value = data.get(key, {})
    if not isinstance(value, dict):
        return None
    nested = value.get(nested_key)
    return float(nested) if nested is not None else None


def _acoustic_seriousness_adjustment(
    anomaly_flags: set[str], audio_quality: Any
) -> float:
    adjustment = 0.0
    if "variabilidad_acustica" in anomaly_flags:
        adjustment += 0.03
    if "energia_vocal_baja" in anomaly_flags:
        adjustment -= 0.04
    if "alta_proporcion_silencio" in anomaly_flags:
        adjustment -= 0.04
    if audio_quality in {"baja_senal", "mucho_silencio", "ruido_alto", "posible_saturacion"}:
        adjustment -= 0.03
    return adjustment


def _acoustic_improcedence_adjustment(
    anomaly_flags: set[str], completeness: float, coherence_score: float
) -> float:
    if not anomaly_flags:
        return 0.0
    adjustment = 0.0
    if "alta_proporcion_silencio" in anomaly_flags:
        adjustment += 0.08
    if "pausas_prolongadas" in anomaly_flags:
        adjustment += 0.05
    if "energia_vocal_baja" in anomaly_flags:
        adjustment += 0.04
    if completeness < 0.5 and coherence_score < 0.55:
        adjustment += 0.1
    return adjustment
