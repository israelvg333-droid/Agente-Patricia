"""Funciones auxiliares compartidas entre modulos del pipeline."""
from __future__ import annotations

from typing import Any


def clamp01(value: float) -> float:
    """Restringe un valor al rango [0.0, 1.0]."""
    return max(0.0, min(1.0, value))


def optional_float(value: Any) -> float | None:
    """Convierte el valor a float, preservando None cuando no hay dato."""
    return float(value) if value is not None else None
