"""Historial y estadisticas a partir de los resultados que guarda el pipeline.

La fuente de verdad son los archivos `resultado_*.json` que `save_result`
escribe en el directorio de salida (por defecto `data/outputs/`). Esto incluye
tanto los analisis lanzados desde la interfaz como los ejecutados por CLI con
`main.py`. No se introduce otra base de datos.

La categoria operativa (SERIA / DUDOSA / IMPROCEDENTE) se deriva con el mismo
`map_score_to_category` y `assess_transcript_quality` que usa
`procesar_dataset.py`, de modo que la interfaz y el procesamiento por lotes
clasifican igual.
"""
from __future__ import annotations

import json
import re
import threading
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from src.asr.transcript_quality import assess_transcript_quality, describe_quality_flags
from src.scoring.category_mapper import (
    CATEGORIA_DUDOSA,
    CATEGORIA_IMPROCEDENTE,
    CATEGORIA_SERIA,
    map_score_to_category,
)
from src.utils.config import PROJECT_ROOT
from src.utils.logger import get_logger

logger = get_logger("subagente_seriedad.web.history")

RESULT_ID_PATTERN = re.compile(r"^resultado_[0-9_]+$")
EVALUATION_SUMMARY = PROJECT_ROOT / "reportes" / "resumen_23_guiones_sinteticos.json"
TREND_DAYS = 14


def classify_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Categoria operativa del resultado, con la misma regla del batch."""
    score = payload.get("score") or {}
    transcription = payload.get("transcription") or {}
    semantic = payload.get("semantic_analysis") or {}
    text = transcription.get("text") or ""
    quality = assess_transcript_quality(text)
    category = map_score_to_category(
        score,
        transcript_status="ok" if transcription.get("status") == "ok" else "error",
        transcript_word_count=int(semantic.get("word_count") or 0),
        transcript_quality=quality,
    )
    category["calidad_transcripcion"] = quality
    return category


def collect_warnings(payload: dict[str, Any]) -> list[str]:
    """Avisos del propio pipeline que el operador debe ver junto al resultado."""
    warnings: list[str] = []
    input_meta = payload.get("input") or {}
    transcription = payload.get("transcription") or {}
    acoustic = payload.get("acoustic_features") or {}
    if transcription.get("status") not in (None, "ok"):
        warnings.append(
            transcription.get("message")
            or f"La transcripción terminó con estado: {transcription.get('status')}."
        )
    if input_meta.get("mode") == "audio" and not acoustic.get("duration_seconds"):
        reason = acoustic.get("note") or "motivo no registrado"
        warnings.append(f"No se pudieron extraer las features acústicas ({reason}).")
    quality = assess_transcript_quality(transcription.get("text") or "")
    if quality.get("is_suspect"):
        detail = describe_quality_flags(quality.get("flags") or [])
        warnings.append(f"Transcripción con alertas de calidad: {detail}.")
    return warnings


def source_name(input_meta: dict[str, Any]) -> str:
    raw = input_meta.get("audio") or input_meta.get("transcript") or ""
    # Los resultados generados en Windows guardan rutas con "\".
    name = raw.replace("\\", "/").rstrip("/").split("/")[-1]
    return name or "(sin archivo)"


class ResultHistory:
    """Lee y resume los JSON del directorio de salida, con cache por mtime."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)
        self._cache: dict[Path, tuple[float, dict[str, Any] | None]] = {}
        self._lock = threading.Lock()

    # -- lectura ---------------------------------------------------------
    def _load(self, path: Path) -> dict[str, Any] | None:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return None
        with self._lock:
            cached = self._cache.get(path)
            if cached and cached[0] == mtime:
                return cached[1]
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            summary = self._summarize(path, payload)
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            logger.warning("Resultado ilegible %s: %s", path.name, exc)
            summary = None
        with self._lock:
            self._cache[path] = (mtime, summary)
        return summary

    def _summarize(self, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
        score = payload.get("score") or {}
        input_meta = payload.get("input") or {}
        acoustic = payload.get("acoustic_features") or {}
        category = classify_payload(payload)
        generated_at = payload.get("generated_at") or datetime.fromtimestamp(
            path.stat().st_mtime
        ).isoformat(timespec="seconds")
        return {
            "id": path.stem,
            "generated_at": generated_at,
            "source": source_name(input_meta),
            "mode": input_meta.get("mode"),
            "categoria": category["categoria"],
            "confianza": category["confianza"],
            "recommendation": score.get("recommendation"),
            "seriousness_score": score.get("seriousness_score"),
            "improcedence_score": score.get("improcedence_score"),
            "pipeline_confidence": score.get("confidence"),
            "duration_seconds": acoustic.get("duration_seconds"),
            "transcription_status": (payload.get("transcription") or {}).get("status"),
            "has_warnings": bool(collect_warnings(payload)),
        }

    def list(self) -> list[dict[str, Any]]:
        if not self.output_dir.exists():
            return []
        items = [
            summary
            for path in self.output_dir.glob("resultado_*.json")
            if (summary := self._load(path)) is not None
        ]
        items.sort(key=lambda item: (item["generated_at"], item["id"]), reverse=True)
        return items

    def get(self, result_id: str) -> dict[str, Any] | None:
        if not RESULT_ID_PATTERN.match(result_id or ""):
            return None
        path = self.output_dir / f"{result_id}.json"
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        category = classify_payload(payload)
        return {
            "id": result_id,
            "file": str(path),
            "source": source_name(payload.get("input") or {}),
            "category": category,
            "warnings": collect_warnings(payload),
            "payload": payload,
        }

    # -- estadisticas ----------------------------------------------------
    def stats(self, today: date | None = None) -> dict[str, Any]:
        items = self.list()
        total = len(items)
        by_category = Counter(item["categoria"] for item in items)
        by_recommendation = Counter(item["recommendation"] or "sin_dato" for item in items)
        by_mode = Counter(item["mode"] or "sin_dato" for item in items)
        confidences = [item["confianza"] for item in items if item["confianza"] is not None]

        today = today or date.today()
        days = [today - timedelta(days=offset) for offset in range(TREND_DAYS - 1, -1, -1)]
        per_day = {day.isoformat(): Counter() for day in days}
        for item in items:
            key = (item["generated_at"] or "")[:10]
            if key in per_day:
                per_day[key][item["categoria"]] += 1

        return {
            "total": total,
            "categorias": {
                CATEGORIA_SERIA: by_category.get(CATEGORIA_SERIA, 0),
                CATEGORIA_DUDOSA: by_category.get(CATEGORIA_DUDOSA, 0),
                CATEGORIA_IMPROCEDENTE: by_category.get(CATEGORIA_IMPROCEDENTE, 0),
            },
            "tasa_alerta": round(by_category.get(CATEGORIA_IMPROCEDENTE, 0) / total, 4)
            if total
            else None,
            "confianza_promedio": round(sum(confidences) / len(confidences), 3)
            if confidences
            else None,
            "recomendaciones": dict(by_recommendation),
            "modos": dict(by_mode),
            "tendencia": [
                {
                    "fecha": day,
                    CATEGORIA_SERIA: counts.get(CATEGORIA_SERIA, 0),
                    CATEGORIA_DUDOSA: counts.get(CATEGORIA_DUDOSA, 0),
                    CATEGORIA_IMPROCEDENTE: counts.get(CATEGORIA_IMPROCEDENTE, 0),
                }
                for day, counts in per_day.items()
            ],
            "ultimo_analisis": items[0]["generated_at"] if items else None,
            "evaluacion": load_evaluation_summary(),
        }


def load_evaluation_summary(path: Path = EVALUATION_SUMMARY) -> dict[str, Any] | None:
    """Exactitud medida por `scripts/run_synthetic_evaluation.py`, si existe."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if "exactitud" not in data:
        return None
    return {
        "exactitud": data.get("exactitud"),
        "aciertos": data.get("aciertos"),
        "total": data.get("total"),
        "fuente": path.relative_to(PROJECT_ROOT).as_posix()
        if path.is_relative_to(PROJECT_ROOT)
        else path.name,
    }
