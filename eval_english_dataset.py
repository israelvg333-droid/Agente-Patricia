"""
eval_english_dataset.py
-----------------------
Evaluacion batch del dataset de llamadas en ingles.

Uso:
    python eval_english_dataset.py --audio-dir /ruta/al/dataset [--model tiny]
        [--output results_english.json]

El script acepta archivos .wav, .mp3 y .m4a.
Genera un JSON con el resultado de cada llamada y un resumen estadistico.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".m4a"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluacion batch de dataset en ingles.")
    parser.add_argument(
        "--audio-dir",
        required=True,
        help="Directorio que contiene los archivos de audio (.wav, .mp3, .m4a).",
    )
    parser.add_argument(
        "--model",
        choices=("tiny", "base", "small"),
        default="tiny",
        help="Modelo Whisper a usar (default: tiny).",
    )
    parser.add_argument(
        "--output",
        default="results_english.json",
        help="Nombre del archivo JSON de resultados (default: results_english.json).",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=0,
        help="Limitar a N archivos (0 = sin limite). Util para pruebas rapidas.",
    )
    return parser.parse_args()


def collect_audio_files(directory: str, max_files: int) -> list[Path]:
    base = Path(directory)
    if not base.exists() or not base.is_dir():
        print(f"ERROR: El directorio '{directory}' no existe o no es valido.")
        sys.exit(1)
    files = sorted(
        p for p in base.rglob("*") if p.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    if not files:
        print(f"ERROR: No se encontraron archivos de audio en '{directory}'.")
        sys.exit(1)
    if max_files > 0:
        files = files[:max_files]
    return files


def run_single(audio_path: Path, model: str) -> dict:
    """Ejecuta el pipeline completo en un archivo de audio."""
    import argparse as _ap

    from main import run_pipeline

    fake_args = _ap.Namespace(
        audio=str(audio_path),
        transcript=None,
        output_dir="data/outputs/english_eval",
        language="en",
        model=model,
    )
    try:
        output_path = run_pipeline(fake_args)
        result_text = Path(output_path).read_text(encoding="utf-8")
        result = json.loads(result_text)
        return {
            "file": audio_path.name,
            "status": "ok",
            "score": result.get("score", {}),
            "transcript": result.get("transcription", {}).get("text", ""),
            "word_count": len(result.get("transcription", {}).get("text", "").split()),
        }
    except Exception as exc:
        return {
            "file": audio_path.name,
            "status": "error",
            "error": str(exc),
        }


def summarize(results: list[dict]) -> dict:
    ok = [r for r in results if r["status"] == "ok"]
    errors = [r for r in results if r["status"] == "error"]

    recommendations: dict[str, int] = {}
    seriousness_values: list[float] = []
    improcedence_values: list[float] = []
    confidence_values: list[float] = []

    for r in ok:
        score = r.get("score", {})
        rec = score.get("recommendation", "unknown")
        recommendations[rec] = recommendations.get(rec, 0) + 1
        if "seriousness_score" in score:
            seriousness_values.append(score["seriousness_score"])
        if "improcedence_score" in score:
            improcedence_values.append(score["improcedence_score"])
        if "confidence" in score:
            confidence_values.append(score["confidence"])

    def avg(lst: list[float]) -> float:
        return round(sum(lst) / len(lst), 3) if lst else 0.0

    return {
        "total_files": len(results),
        "processed_ok": len(ok),
        "errors": len(errors),
        "recommendation_distribution": recommendations,
        "avg_seriousness": avg(seriousness_values),
        "avg_improcedence": avg(improcedence_values),
        "avg_confidence": avg(confidence_values),
        "error_files": [r["file"] for r in errors],
    }


def main() -> None:
    args = parse_args()
    audio_files = collect_audio_files(args.audio_dir, args.max_files)
    total = len(audio_files)
    print(f"Archivos encontrados: {total}")
    print(f"Modelo Whisper: {args.model}")
    print("Idioma forzado: en (ingles)")
    print("-" * 50)

    results = []
    start_total = time.time()

    for i, path in enumerate(audio_files, 1):
        t0 = time.time()
        result = run_single(path, args.model)
        elapsed = round(time.time() - t0, 1)
        status_icon = "OK" if result["status"] == "ok" else "ERROR"
        rec = result.get("score", {}).get("recommendation", result.get("error", "-"))
        print(f"[{i:4d}/{total}] {status_icon} | {path.name[:45]:<45} | {rec} | {elapsed}s")
        results.append(result)

    summary = summarize(results)
    total_time = round(time.time() - start_total, 1)
    summary["total_time_seconds"] = total_time

    output = {
        "summary": summary,
        "results": results,
    }
    output_path = Path(args.output)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 50)
    print("RESUMEN")
    print("=" * 50)
    print(f"Total archivos   : {summary['total_files']}")
    print(f"Procesados OK    : {summary['processed_ok']}")
    print(f"Errores          : {summary['errors']}")
    print(f"Tiempo total     : {total_time}s")
    print(f"Avg seriousness  : {summary['avg_seriousness']}")
    print(f"Avg improcedence : {summary['avg_improcedence']}")
    print(f"Avg confidence   : {summary['avg_confidence']}")
    print("\nDistribucion de recomendaciones:")
    for rec, count in sorted(summary["recommendation_distribution"].items(), key=lambda x: -x[1]):
        pct = round(count / max(summary["processed_ok"], 1) * 100, 1)
        print(f"  {rec:<30} {count:4d}  ({pct}%)")
    print(f"\nResultados guardados en: {output_path.resolve()}")


if __name__ == "__main__":
    main()
