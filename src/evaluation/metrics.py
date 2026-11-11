"""Metricas de evaluacion para la clasificacion de llamadas.

Funciones puras para comparar las categorias del sistema contra etiquetas
manuales: matriz de confusion, precision/recall/F1 por clase, exactitud,
macro-F1, AUROC binaria y Brier score.

No dependen de sklearn: el volumen de datos esperado (decenas de llamadas
etiquetadas) no justifica la dependencia y las formulas cerradas son
auditables linea por linea.
"""
from __future__ import annotations

from typing import Any


def confusion_matrix(
    y_true: list[str], y_pred: list[str], labels: list[str] | None = None
) -> dict[str, dict[str, int]]:
    """Matriz de confusion como dict anidado: matrix[real][predicha] = conteo.

    `labels` fija el orden y el universo de clases; si se omite, se usan las
    clases observadas en orden alfabetico. Pares con longitud distinta lanzan
    ValueError porque indican un join de datos defectuoso.
    """
    if len(y_true) != len(y_pred):
        raise ValueError(
            f"y_true ({len(y_true)}) y y_pred ({len(y_pred)}) deben tener la misma longitud."
        )
    if labels is None:
        labels = sorted(set(y_true) | set(y_pred))
    matrix = {true: {pred: 0 for pred in labels} for true in labels}
    for true, pred in zip(y_true, y_pred, strict=True):
        if true not in matrix or pred not in matrix[true]:
            raise ValueError(f"Etiqueta fuera del universo declarado: real={true!r} pred={pred!r}")
        matrix[true][pred] += 1
    return matrix


def per_class_metrics(matrix: dict[str, dict[str, int]]) -> dict[str, dict[str, Any]]:
    """Precision, recall, F1 y soporte por clase a partir de la matriz.

    Las divisiones por cero (clase sin predicciones o sin ejemplos reales)
    devuelven None en la metrica afectada, para distinguir "no evaluable"
    de un cero genuino.
    """
    labels = list(matrix.keys())
    result: dict[str, dict[str, Any]] = {}
    for label in labels:
        tp = matrix[label][label]
        support = sum(matrix[label].values())
        predicted = sum(matrix[true][label] for true in labels)
        precision = tp / predicted if predicted else None
        recall = tp / support if support else None
        if precision and recall and (precision + recall) > 0:
            f1: float | None = 2 * precision * recall / (precision + recall)
        elif precision is None or recall is None:
            f1 = None
        else:
            f1 = 0.0
        result[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }
    return result


def accuracy(matrix: dict[str, dict[str, int]]) -> float | None:
    total = sum(sum(row.values()) for row in matrix.values())
    if total == 0:
        return None
    correct = sum(matrix[label][label] for label in matrix)
    return correct / total


def macro_f1(per_class: dict[str, dict[str, Any]]) -> float | None:
    """Promedio simple de F1 sobre las clases con soporte > 0."""
    scores = [
        metrics["f1"]
        for metrics in per_class.values()
        if metrics["support"] > 0 and metrics["f1"] is not None
    ]
    if not scores:
        return None
    return sum(scores) / len(scores)


def binary_auroc(y_true: list[int], scores: list[float]) -> float | None:
    """AUROC por rangos (Mann-Whitney) con correccion de empates.

    `y_true` usa 1 para la clase positiva y 0 para la negativa. Devuelve None
    si falta alguna de las dos clases (la curva ROC no esta definida).
    """
    if len(y_true) != len(scores):
        raise ValueError("y_true y scores deben tener la misma longitud.")
    n_pos = sum(1 for y in y_true if y == 1)
    n_neg = len(y_true) - n_pos
    if n_pos == 0 or n_neg == 0:
        return None

    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        mean_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = mean_rank
        i = j + 1

    rank_sum_pos = sum(rank for rank, y in zip(ranks, y_true, strict=True) if y == 1)
    return (rank_sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def brier_score(y_true: list[int], probabilities: list[float]) -> float | None:
    """Error cuadratico medio entre probabilidad estimada y etiqueta binaria.

    Util como proxy de calibracion aunque `seriousness_score` no sea una
    probabilidad calibrada: valores altos indican scores lejos de las
    etiquetas reales.
    """
    if len(y_true) != len(probabilities):
        raise ValueError("y_true y probabilities deben tener la misma longitud.")
    if not y_true:
        return None
    return sum(
        (prob - y) ** 2 for prob, y in zip(probabilities, y_true, strict=True)
    ) / len(y_true)
