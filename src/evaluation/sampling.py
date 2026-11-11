"""Muestreo estratificado para el etiquetado manual del dataset clasificado.

Estrategia (sesion 2026-07-08 de MEJORAS_PROYECTO.md): todas las llamadas
DUDOSAS e IMPROCEDENTES (las clases minoritarias, donde el sistema tiene
menos evidencia) mas una muestra aleatoria reproducible de SERIAS.
"""
from __future__ import annotations

import random
import unicodedata
from typing import Any

from src.scoring.category_mapper import (
    CATEGORIA_SERIA,
    VALID_CATEGORIES,
)

DEFAULT_SERIAS_SAMPLE = 15
DEFAULT_SEED = 20260714


def normalize_label(raw: str | None) -> str | None:
    """Normaliza una etiqueta manual a su forma canonica (SERIA/DUDOSA/IMPROCEDENTE).

    Tolera espacios, minusculas y acentos (p. ej. "dudosa ", "Improcedente").
    Devuelve None para vacios o etiquetas fuera del universo valido; el
    llamador decide si eso es "pendiente de etiquetar" o un error.
    """
    if raw is None:
        return None
    text = unicodedata.normalize("NFKD", raw.strip().upper())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text if text in VALID_CATEGORIES else None


def stratified_labeling_sample(
    records: list[dict[str, Any]],
    serias: int = DEFAULT_SERIAS_SAMPLE,
    seed: int = DEFAULT_SEED,
) -> list[dict[str, Any]]:
    """Selecciona los registros a etiquetar manualmente.

    - Incluye todos los registros cuya categoria del sistema NO es SERIA
      (DUDOSA e IMPROCEDENTE completas).
    - Agrega `serias` registros SERIA elegidos con `random.Random(seed)`
      (reproducible); si hay menos, se incluyen todos.
    - Excluye registros sin categoria valida (p. ej. audios que fallaron).
    - Devuelve la muestra ordenada por nombre de archivo para que la hoja de
      etiquetado no agrupe por categoria (etiquetado ciego).
    """
    minority = [
        record
        for record in records
        if record.get("categoria") in VALID_CATEGORIES
        and record.get("categoria") != CATEGORIA_SERIA
    ]
    serias_pool = [record for record in records if record.get("categoria") == CATEGORIA_SERIA]
    if len(serias_pool) > serias:
        serias_pool = random.Random(seed).sample(serias_pool, serias)
    sample = minority + serias_pool
    return sorted(sample, key=lambda record: str(record.get("archivo", "")))
