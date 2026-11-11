"""Genera, ejecuta y grafica la evaluación de los 23 guiones sintéticos.

Ejecutar desde la raíz del proyecto:
    .venv\\Scripts\\python.exe scripts\\run_synthetic_evaluation.py
"""

from __future__ import annotations

import ast
import csv
import json
import re
import sys
from argparse import Namespace
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from main import run_pipeline  # noqa: E402

DOCUMENT = ROOT / "23_guiones_dataset_prueba.md"
DATASET_DIR = ROOT / "dataset_prueba"
REPORT_DIR = ROOT / "reportes"
RECOMMENDATIONS = [
    "continuar",
    "escalar_humano",
    "pedir_mas_informacion",
    "posible_improcedente",
]


def load_scripts() -> list[tuple[str, str, str, str]]:
    """Extrae la lista GUIONES documentada, manteniendo una sola fuente de verdad."""
    text = DOCUMENT.read_text(encoding="utf-8")
    matches = re.findall(r'^    \("G-\d{2}".*?\),$', text, flags=re.MULTILINE)
    scripts = [ast.literal_eval(item.rstrip(",")) for item in matches]
    if len(scripts) != 23:
        raise ValueError(f"Se esperaban 23 guiones y se encontraron {len(scripts)}.")
    return scripts


def evaluate(identifier: str, text: str) -> dict[str, object]:
    transcript_path = DATASET_DIR / f"{identifier}.txt"
    transcript_path.write_text(text, encoding="utf-8")
    output_path = run_pipeline(
        Namespace(
            audio=None,
            transcript=str(transcript_path),
            output_dir=str(DATASET_DIR / "outputs"),
            language="es",
            model="tiny",
        )
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    return payload["score"]


def write_chart(rows: list[dict[str, object]]) -> Path:
    expected = Counter(str(row["esperado"]) for row in rows)
    obtained = Counter(str(row["obtenido"]) for row in rows)
    labels = [item.replace("_", "\n") for item in RECOMMENDATIONS]
    positions = range(len(RECOMMENDATIONS))

    figure, axes = plt.subplots(1, 2, figsize=(14, 5.5), constrained_layout=True)
    width = 0.36
    axes[0].bar([x - width / 2 for x in positions], [expected[x] for x in RECOMMENDATIONS],
                width, label="Esperado", color="#4C78A8")
    axes[0].bar([x + width / 2 for x in positions], [obtained[x] for x in RECOMMENDATIONS],
                width, label="Obtenido", color="#F58518")
    axes[0].set_xticks(list(positions), labels, fontsize=9)
    axes[0].set_ylabel("Número de guiones")
    axes[0].set_title("Distribución de recomendaciones")
    axes[0].legend()
    axes[0].set_ylim(0, max(8, max(expected.values()), max(obtained.values())) + 1)

    correct = sum(bool(row["correcto"]) for row in rows)
    colors = ["#54A24B" if row["correcto"] else "#E45756" for row in rows]
    axes[1].bar([row["id"] for row in rows], [1 if row["correcto"] else 0 for row in rows], color=colors)
    axes[1].set_ylim(0, 1.15)
    axes[1].set_yticks([0, 1], ["No coincide", "Coincide"])
    axes[1].tick_params(axis="x", rotation=55, labelsize=8)
    axes[1].set_title(f"Resultado por guion — exactitud: {correct}/{len(rows)} ({correct / len(rows):.1%})")

    for axis in axes:
        axis.spines[["top", "right"]].set_visible(False)
    path = REPORT_DIR / "evaluacion_23_guiones_sinteticos.png"
    figure.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(figure)
    return path


def main() -> None:
    DATASET_DIR.mkdir(exist_ok=True)
    REPORT_DIR.mkdir(exist_ok=True)
    scripts = load_scripts()
    rows: list[dict[str, object]] = []
    for identifier, _, expected, text in scripts:
        score = evaluate(identifier, text)
        obtained = str(score["recommendation"])
        row = {
            "id": identifier,
            "archivo": f"{identifier}.txt",
            "modo": "transcript_only",
            "esperado": expected,
            "obtenido": obtained,
            "correcto": obtained == expected,
            "seriousness_score": score["seriousness_score"],
            "improcedence_score": score["improcedence_score"],
            "confidence": score["confidence"],
        }
        rows.append(row)
        print(f"{identifier}: esperado={expected}; obtenido={obtained}")

    csv_path = REPORT_DIR / "resultados_23_guiones_sinteticos.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    correct = sum(bool(row["correcto"]) for row in rows)
    summary = {
        "total": len(rows),
        "aciertos": correct,
        "exactitud": round(correct / len(rows), 4),
        "esperado": dict(Counter(str(row["esperado"]) for row in rows)),
        "obtenido": dict(Counter(str(row["obtenido"]) for row in rows)),
        "grafica": str(write_chart(rows)),
    }
    (REPORT_DIR / "resumen_23_guiones_sinteticos.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
