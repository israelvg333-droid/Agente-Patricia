"""Evaluacion del clasificador contra etiquetas manuales.

Flujo en dos pasos:

1. Generar la hoja de etiquetado (muestra estratificada, etiquetado ciego:
   sin categoria ni scores del sistema a la vista):

       python scripts/evaluate.py sample

   Produce `reportes/muestra_etiquetado.csv`. Completar la columna
   `etiqueta_manual` con SERIA, DUDOSA o IMPROCEDENTE escuchando cada audio
   (columna `ruta_original`).

2. Calcular metricas cruzando las etiquetas con la clasificacion del sistema:

       python scripts/evaluate.py evaluate

   Produce `reportes/reporte_evaluacion.md` con matriz de confusion,
   precision/recall/F1 por clase, exactitud, macro-F1, AUROC y Brier score.
   El recall de SERIA es la metrica prioritaria del proyecto.
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.metrics import (
    accuracy,
    binary_auroc,
    brier_score,
    confusion_matrix,
    macro_f1,
    per_class_metrics,
)
from src.evaluation.sampling import (
    DEFAULT_SEED,
    DEFAULT_SERIAS_SAMPLE,
    normalize_label,
    stratified_labeling_sample,
)
from src.scoring.category_mapper import CATEGORIA_SERIA, VALID_CATEGORIES

DEFAULT_DATASET = PROJECT_ROOT / "clasificacion_dataset.csv"
DEFAULT_SAMPLE = PROJECT_ROOT / "reportes" / "muestra_etiquetado.csv"
DEFAULT_REPORT = PROJECT_ROOT / "reportes" / "reporte_evaluacion.md"

SAMPLE_FIELDS = [
    "archivo",
    "ruta_original",
    "duracion_segundos",
    "transcripcion",
    "etiqueta_manual",
    "notas",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    subparsers = parser.add_subparsers(dest="command", required=True)

    sample = subparsers.add_parser(
        "sample", help="Genera la hoja de etiquetado manual (muestra estratificada)."
    )
    sample.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    sample.add_argument("--output", type=Path, default=DEFAULT_SAMPLE)
    sample.add_argument(
        "--serias",
        type=int,
        default=DEFAULT_SERIAS_SAMPLE,
        help="Cantidad de llamadas SERIA a muestrear (ademas de todas las DUDOSAS/IMPROCEDENTES).",
    )
    sample.add_argument("--seed", type=int, default=DEFAULT_SEED)
    sample.add_argument(
        "--force",
        action="store_true",
        help="Sobrescribe la hoja existente aunque contenga etiquetas ya capturadas.",
    )

    evaluate = subparsers.add_parser(
        "evaluate", help="Calcula metricas cruzando etiquetas manuales con el sistema."
    )
    evaluate.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    evaluate.add_argument("--labels", type=Path, default=DEFAULT_SAMPLE)
    evaluate.add_argument("--output", type=Path, default=DEFAULT_REPORT)

    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"No existe el archivo: {path}")
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def run_sample(args: argparse.Namespace) -> None:
    if args.output.exists() and not args.force:
        existing = read_csv(args.output)
        labeled = sum(1 for row in existing if normalize_label(row.get("etiqueta_manual")))
        raise SystemExit(
            f"{args.output} ya existe con {labeled} etiquetas capturadas. "
            "Use --force para regenerarla (se perderian las etiquetas)."
        )
    records = read_csv(args.dataset)
    sample = stratified_labeling_sample(records, serias=args.serias, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=SAMPLE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for record in sample:
            row = {key: record.get(key, "") for key in SAMPLE_FIELDS}
            writer.writerow(row)
    print(f"Hoja de etiquetado generada: {args.output} ({len(sample)} llamadas).")
    print("Complete `etiqueta_manual` con SERIA, DUDOSA o IMPROCEDENTE y ejecute:")
    print("    python scripts/evaluate.py evaluate")


def run_evaluate(args: argparse.Namespace) -> None:
    dataset = {row["archivo"]: row for row in read_csv(args.dataset) if row.get("archivo")}
    labels = read_csv(args.labels)

    joined: list[dict[str, Any]] = []
    pending = 0
    invalid: list[str] = []
    missing: list[str] = []
    for row in labels:
        raw = (row.get("etiqueta_manual") or "").strip()
        label = normalize_label(raw)
        if label is None:
            if raw:
                invalid.append(f"{row.get('archivo')}: {raw!r}")
            else:
                pending += 1
            continue
        system = dataset.get(row.get("archivo", ""))
        if system is None or system.get("categoria") not in VALID_CATEGORIES:
            missing.append(str(row.get("archivo")))
            continue
        joined.append(
            {
                "archivo": row["archivo"],
                "manual": label,
                "sistema": system["categoria"],
                "seriousness_score": _to_float(system.get("seriousness_score")),
            }
        )

    if invalid:
        raise SystemExit(
            "Etiquetas no reconocidas (use SERIA, DUDOSA o IMPROCEDENTE):\n  "
            + "\n  ".join(invalid)
        )
    if not joined:
        raise SystemExit(
            f"Ninguna fila etiquetada en {args.labels} ({pending} pendientes). "
            "Complete `etiqueta_manual` antes de evaluar."
        )

    report = build_report(joined, pending=pending, missing=missing, labels_path=args.labels)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(report)
    print(f"Reporte guardado en: {args.output}")


def build_report(
    joined: list[dict[str, Any]],
    pending: int,
    missing: list[str],
    labels_path: Path,
) -> str:
    universe = sorted(VALID_CATEGORIES)
    y_true = [row["manual"] for row in joined]
    y_pred = [row["sistema"] for row in joined]
    matrix = confusion_matrix(y_true, y_pred, labels=universe)
    per_class = per_class_metrics(matrix)

    binary_true = [1 if row["manual"] == CATEGORIA_SERIA else 0 for row in joined]
    scored = [
        (yt, row["seriousness_score"])
        for yt, row in zip(binary_true, joined, strict=True)
        if row["seriousness_score"] is not None
    ]
    auroc = binary_auroc([yt for yt, _ in scored], [s for _, s in scored]) if scored else None
    brier = brier_score([yt for yt, _ in scored], [s for _, s in scored]) if scored else None

    lines = [
        "# Reporte de evaluacion contra etiquetas manuales",
        "",
        f"Fecha: {datetime.now():%Y-%m-%d %H:%M}",
        f"Fuente de etiquetas: `{labels_path.name}`",
        f"Llamadas evaluadas: {len(joined)} (pendientes de etiquetar: {pending})",
    ]
    if missing:
        lines.append(
            f"Excluidas por no encontrarse en el dataset o carecer de categoria: {len(missing)} "
            f"({', '.join(missing)})"
        )
    lines += [
        "",
        "## Matriz de confusion (filas = etiqueta manual, columnas = sistema)",
        "",
        "| Real \\ Sistema | " + " | ".join(universe) + " |",
        "|---|" + "---|" * len(universe),
    ]
    for true in universe:
        cells = " | ".join(str(matrix[true][pred]) for pred in universe)
        lines.append(f"| **{true}** | {cells} |")

    lines += [
        "",
        "## Metricas por clase",
        "",
        "| Clase | Precision | Recall | F1 | Soporte |",
        "|---|---|---|---|---|",
    ]
    for label in universe:
        metrics = per_class[label]
        lines.append(
            f"| {label} | {_fmt(metrics['precision'])} | {_fmt(metrics['recall'])} "
            f"| {_fmt(metrics['f1'])} | {metrics['support']} |"
        )

    recall_seria = per_class[CATEGORIA_SERIA]["recall"]
    lines += [
        "",
        "## Metricas globales",
        "",
        f"- **Recall de SERIA (metrica prioritaria): {_fmt(recall_seria)}**: proporcion de",
        "  emergencias reales que el sistema clasifico como SERIA. Un valor bajo significa",
        "  emergencias reales degradadas a DUDOSA/IMPROCEDENTE.",
        f"- Exactitud: {_fmt(accuracy(matrix))}",
        f"- Macro-F1: {_fmt(macro_f1(per_class))}",
        f"- AUROC (SERIA vs resto, usando `seriousness_score`): {_fmt(auroc)}",
        f"- Brier score (menor es mejor; `seriousness_score` no esta calibrado como"
        f" probabilidad): {_fmt(brier)}",
        "",
        "## Notas metodologicas",
        "",
        "- La hoja de etiquetado se genero sin mostrar la categoria del sistema",
        "  (etiquetado ciego); el cruce se hace por nombre de archivo.",
        "- La muestra sobre-representa DUDOSAS por diseno: las metricas de SERIA",
        "  son conservadoras respecto al dataset completo.",
        "- AUROC = None indica que la muestra etiquetada no contiene ambas clases.",
    ]
    return "\n".join(lines) + "\n"


def _fmt(value: float | None) -> str:
    return f"{value:.3f}" if value is not None else "n/a"


def _to_float(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def main() -> None:
    args = parse_args()
    if args.command == "sample":
        run_sample(args)
    else:
        run_evaluate(args)


if __name__ == "__main__":
    main()
