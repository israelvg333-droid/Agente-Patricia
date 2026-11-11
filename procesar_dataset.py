"""
procesar_dataset.py
-------------------
Procesamiento batch del dataset de llamadas 911: transcribe cada audio con el
ASR del proyecto (Whisper local), ejecuta el pipeline completo de analisis
(acustico, semantico, intencion, coherencia, scoring) y clasifica cada llamada
en SERIA, DUDOSA o IMPROCEDENTE.

Uso:
    python procesar_dataset.py [--audio-dir RUTA] [--model tiny] [--workers 3]

Salidas (en el directorio del proyecto por defecto):
    dataset_clasificado/{seria,dudosa,improcedente}/   copias de los audios
    clasificacion_dataset.csv
    clasificacion_dataset.json
    RESUMEN_DATASET.md
    errores_procesamiento.log

El procesamiento es reanudable: los resultados se guardan de forma
incremental en un checkpoint JSONL y las ejecuciones posteriores omiten los
archivos ya procesados.

Reprocesamiento selectivo (sin tocar el resto del checkpoint):
    python procesar_dataset.py --redo-sospechosos --model base
        Retranscribe los audios con alertas de calidad de transcripcion.
    python procesar_dataset.py --redo-archivo call_506.mp3
        Reprocesa archivos especificos (incluye registros con error).
    python procesar_dataset.py --redo-acustico
        Backfill acustico: recalcula features y re-puntua los registros que no
        tienen `features_acusticas` persistidas, reutilizando la transcripcion
        guardada (no carga Whisper). Genera/actualiza features_dataset.csv.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.asr.transcript_quality import assess_transcript_quality
from src.scoring.category_mapper import (
    VALID_CATEGORIES,
    apply_transcript_quality_adjustment,
    map_score_to_category,
)
from src.utils.config import AppConfig

SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aac", ".wma"}
LOW_CONFIDENCE_THRESHOLD = 0.60
CHECKPOINT_NAME = "clasificacion_dataset.partial.jsonl"

# Columnas exportadas a CSV y JSON (mismo orden en ambos formatos).
EXPORT_FIELDS = [
    "archivo",
    "ruta_original",
    "duracion_segundos",
    "transcripcion",
    "categoria",
    "confianza",
    "justificacion",
    "alertas_transcripcion",
    "calidad_transcripcion",
    "seriousness_score",
    "pipeline_confidence",
    "recommendation",
]

# Features acusticas escalares que se aplanan al registro del checkpoint y al
# CSV de entrenamiento (una columna por feature; mismo nombre que en
# extract_acoustic_features).
_SCALAR_ACOUSTIC_FIELDS = [
    "duration_seconds",
    "rms_energy",
    "mean_energy",
    "max_energy",
    "energy_std",
    "peak_amplitude",
    "zero_crossing_rate",
    "estimated_tempo_bpm",
    "estimated_f0_hz",
    "estimated_f0_min_hz",
    "estimated_f0_max_hz",
    "estimated_f0_std_hz",
    "estimated_jitter_ratio",
    "estimated_shimmer_ratio",
    "spectral_centroid_hz",
    "spectral_rolloff_hz",
    "spectral_bandwidth_hz",
    "spectral_flatness",
    "silence_ratio",
    "pause_count",
    "mean_pause_seconds",
    "longest_pause_seconds",
    "approx_speech_rate",
    "clipping_ratio",
    "estimated_snr_db",
]
_MFCC_COUNT = 13
_INDICATOR_FIELDS = [
    "stress_vocal_score",
    "urgency_score",
    "nervousness_score",
    "desperation_score",
    "calm_score",
    "aggression_score",
    "voice_instability_score",
    "voice_tremor_score",
    "audio_reliability",
    "seriousness_audio_score",
]

# Orden canonico de columnas del vector de features (checkpoint y CSV).
ACOUSTIC_FEATURE_FIELDS = (
    _SCALAR_ACOUSTIC_FIELDS
    + [f"mfcc_mean_{i:02d}" for i in range(1, _MFCC_COUNT + 1)]
    + [f"mfcc_std_{i:02d}" for i in range(1, _MFCC_COUNT + 1)]
    + _INDICATOR_FIELDS
    + ["audio_quality", "acoustic_anomaly_flags"]
)

FEATURES_CSV_NAME = "features_dataset.csv"
# Metadatos y objetivos que acompanan a las features en el CSV de entrenamiento.
FEATURES_CSV_CONTEXT = [
    "archivo",
    "categoria",
    "confianza",
    "seriousness_score",
    "improcedence_score",
    "pipeline_confidence",
    "recommendation",
    "calidad_transcripcion",
]


def flatten_acoustic_features(acoustic: dict[str, Any]) -> dict[str, Any]:
    """Aplana el dict de features acusticas a un registro tabular estable.

    Expande los vectores MFCC a una columna por coeficiente, extrae los
    indicadores acusticos de emergencia con su nombre original y serializa las
    listas de flags como texto. Las claves resultantes son exactamente
    `ACOUSTIC_FEATURE_FIELDS` (valores ausentes quedan en None).
    """
    flat: dict[str, Any] = {key: acoustic.get(key) for key in _SCALAR_ACOUSTIC_FIELDS}
    for prefix in ("mfcc_mean", "mfcc_std"):
        values = acoustic.get(prefix) or []
        for i in range(_MFCC_COUNT):
            flat[f"{prefix}_{i + 1:02d}"] = values[i] if i < len(values) else None
    indicators = acoustic.get("emergency_audio_indicators") or {}
    for key in _INDICATOR_FIELDS:
        flat[key] = indicators.get(key)
    flat["audio_quality"] = acoustic.get("audio_quality")
    flat["acoustic_anomaly_flags"] = "; ".join(
        acoustic.get("acoustic_anomaly_flags") or []
    )
    return flat

# Estado por proceso worker: el modelo Whisper se carga una sola vez.
_WORKER_MODEL: Any = None
_WORKER_CONFIG: AppConfig | None = None


# ---------------------------------------------------------------------------
# Worker (se ejecuta en procesos hijos)
# ---------------------------------------------------------------------------

def _init_worker(model_name: str, torch_threads: int, load_model: bool = True) -> None:
    """Inicializa cada proceso worker: limita hilos y precarga Whisper.

    Con `load_model=False` (backfill acustico) no se carga Whisper: el worker
    solo extrae features y re-puntua con la transcripcion ya guardada.
    """
    global _WORKER_MODEL, _WORKER_CONFIG
    os.environ.setdefault("NUMBA_CACHE_DIR", str(PROJECT_ROOT / ".numba_cache"))
    try:
        import torch

        torch.set_num_threads(max(1, torch_threads))
    except Exception:
        pass
    if load_model:
        import whisper

        _WORKER_MODEL = whisper.load_model(model_name)
    _WORKER_CONFIG = AppConfig()


def _worker_process_audio(
    path_str: str,
    language: str,
    model_name: str,
    stored: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pipeline completo para un audio. Nunca lanza: reporta errores en el dict.

    `stored` es el registro previo del checkpoint: si se pasa, la transcripcion
    guardada se reutiliza y no se invoca Whisper (modo backfill acustico).
    """
    path = Path(path_str)
    started = time.time()
    try:
        record = _analyze_audio(path, language, model_name, stored=stored)
    except Exception as exc:
        record = {
            "archivo": path.name,
            "ruta_original": str(path),
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "duracion_segundos": None,
            "transcripcion": "",
            "categoria": None,
            "confianza": None,
            "justificacion": "",
        }
    record["tiempo_proceso_segundos"] = round(time.time() - started, 1)
    return record


def _analyze_audio(
    path: Path,
    language: str,
    model_name: str,
    stored: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from src.audio.acoustic_features import (
        empty_acoustic_features,
        enrich_with_text_rate,
        extract_acoustic_features,
    )
    from src.audio.preprocessing import load_audio
    from src.scoring.seriousness_scorer import score_call
    from src.semantic.coherence_analyzer import analyze_coherence
    from src.semantic.intent_analyzer import analyze_intent
    from src.semantic.text_analyzer import analyze_text

    config = _WORKER_CONFIG or AppConfig()

    # Se decodifica una sola vez a 16 kHz mono: sirve para Whisper y features.
    audio, sample_rate = load_audio(path, sample_rate=config.sample_rate)
    duration = round(len(audio) / float(sample_rate), 3)

    if stored is not None:
        # Backfill acustico: la transcripcion previa del checkpoint sigue siendo
        # valida (el ASR no cambio); solo se recalculan features y scoring.
        transcript_status = stored.get("transcripcion_status") or "ok"
        transcript_text = (stored.get("transcripcion") or "").strip()
        detected_language = stored.get("idioma_detectado", language)
        asr_label = stored.get("modelo_asr") or f"openai-whisper-local-{model_name}"
    else:
        transcript_status = "ok"
        transcript_text = ""
        asr_label = f"openai-whisper-local-{model_name}"
        try:
            # condition_on_previous_text=False y temperature=0.0 reducen los bucles
            # repetitivos (alucinaciones) de Whisper en audios largos o ruidosos.
            result = _WORKER_MODEL.transcribe(
                audio,
                language=language,
                fp16=False,
                temperature=0.0,
                condition_on_previous_text=False,
            )
            transcript_text = (result.get("text") or "").strip()
            detected_language = result.get("language", language)
        except Exception as exc:
            transcript_status = f"whisper_error: {exc}"
            detected_language = language

    try:
        acoustic = extract_acoustic_features(audio, sample_rate, config.audio_analysis)
    except Exception as exc:
        acoustic = empty_acoustic_features(str(exc))
    acoustic = enrich_with_text_rate(acoustic, transcript_text)

    semantic = analyze_text(transcript_text)
    intent = analyze_intent(semantic)
    coherence = analyze_coherence(transcript_text)
    score = score_call(acoustic, semantic, intent, coherence)

    quality = assess_transcript_quality(transcript_text)
    category = map_score_to_category(
        score,
        transcript_status="ok" if transcript_status == "ok" else "error",
        transcript_word_count=int(semantic.get("word_count") or 0),
        transcript_quality=quality,
    )

    return {
        "archivo": path.name,
        "ruta_original": str(path),
        "status": "ok",
        "duracion_segundos": duration,
        "transcripcion": transcript_text,
        "categoria": category["categoria"],
        "confianza": category["confianza"],
        "justificacion": category["justificacion"],
        "idioma_detectado": detected_language,
        "transcripcion_status": transcript_status,
        "modelo_asr": asr_label,
        "recommendation": score.get("recommendation"),
        "seriousness_score": score.get("seriousness_score"),
        "improcedence_score": score.get("improcedence_score"),
        "pipeline_confidence": score.get("confidence"),
        "calidad_transcripcion": quality["quality_score"],
        "alertas_transcripcion": quality["flags"],
        "features_acusticas": flatten_acoustic_features(acoustic),
    }


# ---------------------------------------------------------------------------
# Orquestacion (proceso principal)
# ---------------------------------------------------------------------------

def collect_audio_files(directory: Path) -> list[Path]:
    return sorted(
        p
        for p in directory.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def load_checkpoint(checkpoint_path: Path) -> dict[str, dict[str, Any]]:
    """Carga resultados previos indexados por ruta original."""
    records: dict[str, dict[str, Any]] = {}
    if not checkpoint_path.exists():
        return records
    for line in checkpoint_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
            records[record["ruta_original"]] = record
        except (json.JSONDecodeError, KeyError):
            continue
    return records


def ensure_transcript_quality(record: dict[str, Any]) -> dict[str, Any]:
    """Retro-rellena la evaluacion de calidad en registros de checkpoints previos.

    Los registros generados antes de incorporar `assess_transcript_quality` no
    traen los campos de calidad; se calculan desde la transcripcion guardada y,
    si es sospechosa, se ajustan confianza y justificacion con la misma regla
    que aplica el pipeline. Idempotente: no toca registros que ya los traen.
    """
    if record.get("status") != "ok" or "calidad_transcripcion" in record:
        return record
    quality = assess_transcript_quality(record.get("transcripcion") or "")
    record["calidad_transcripcion"] = quality["quality_score"]
    record["alertas_transcripcion"] = quality["flags"]
    confianza, justificacion = apply_transcript_quality_adjustment(
        float(record.get("confianza") or 0.0),
        record.get("justificacion") or "",
        quality,
    )
    record["confianza"] = round(confianza, 2)
    record["justificacion"] = justificacion
    return record


def select_redo_paths(
    previous: dict[str, dict[str, Any]],
    files: list[Path],
    redo_suspects: bool,
    redo_names: list[str],
) -> list[str]:
    """Rutas del checkpoint que deben reprocesarse selectivamente.

    - `redo_suspects`: registros ok con alertas de calidad de transcripcion
      (se retro-rellena la calidad primero, para checkpoints antiguos).
    - `redo_names`: nombres de archivo exactos (incluye registros con error).

    Solo se consideran archivos que siguen existiendo en el dataset actual.
    No reescribe el checkpoint: los registros nuevos se anexan y superseden a
    los antiguos porque `load_checkpoint` conserva la ultima linea por ruta.
    """
    available = {str(p) for p in files}
    names = set(redo_names)
    selected: list[str] = []
    for path, record in previous.items():
        if path not in available:
            continue
        ensure_transcript_quality(record)
        is_suspect = record.get("status") == "ok" and bool(
            record.get("alertas_transcripcion")
        )
        if (redo_suspects and is_suspect) or record.get("archivo") in names:
            selected.append(path)
    return sorted(selected)


def select_acoustic_backfill_paths(
    previous: dict[str, dict[str, Any]], files: list[Path]
) -> list[str]:
    """Rutas de registros ok sin `features_acusticas` persistidas (backfill).

    Solo considera archivos que siguen existiendo en el dataset actual. Los
    registros con error se excluyen: no tienen transcripcion que reutilizar
    (para esos usar `--redo-archivo`, que si retranscribe).
    """
    available = {str(p) for p in files}
    return sorted(
        path
        for path, record in previous.items()
        if path in available
        and record.get("status") == "ok"
        and "features_acusticas" not in record
    )


def remove_category_copies(archivo: str, classified_dir: Path) -> None:
    """Borra copias previas del audio en dataset_clasificado/ (todas las categorias).

    Necesario al reprocesar: si la categoria cambia, la copia vieja quedaria
    huerfana en la carpeta de la categoria anterior.
    """
    for categoria in VALID_CATEGORIES:
        stale = classified_dir / categoria.lower() / archivo
        if stale.exists():
            stale.unlink()


def append_checkpoint(checkpoint_path: Path, record: dict[str, Any]) -> None:
    with checkpoint_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_error(log_path: Path, record: dict[str, Any]) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(
            f"[{timestamp}] {record['archivo']} | {record['ruta_original']} | "
            f"{record.get('error', 'error desconocido')}\n"
        )


def copy_to_category(record: dict[str, Any], classified_dir: Path) -> None:
    """Copia (no mueve) el audio a la carpeta de su categoria."""
    categoria = record.get("categoria")
    if categoria not in VALID_CATEGORIES:
        return
    destination_dir = classified_dir / categoria.lower()
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / record["archivo"]
    source = Path(record["ruta_original"])
    if not destination.exists() and source.exists():
        shutil.copy2(source, destination)


def format_hms(seconds: float) -> str:
    seconds = int(round(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def write_csv(records: list[dict[str, Any]], csv_path: Path) -> None:
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=EXPORT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            row = {key: record.get(key, "") for key in EXPORT_FIELDS}
            if isinstance(row.get("alertas_transcripcion"), list):
                row["alertas_transcripcion"] = "; ".join(row["alertas_transcripcion"])
            writer.writerow(row)


def write_json(records: list[dict[str, Any]], json_path: Path) -> None:
    payload = [{key: record.get(key) for key in EXPORT_FIELDS} for record in records]
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def write_features_csv(records: list[dict[str, Any]], csv_path: Path) -> int:
    """Escribe el CSV tabular de features acusticas para entrenamiento supervisado.

    Una fila por registro ok con `features_acusticas`; las columnas son los
    metadatos/objetivos (`FEATURES_CSV_CONTEXT`) mas `ACOUSTIC_FEATURE_FIELDS`.
    Devuelve el numero de filas escritas; con 0 no crea el archivo (checkpoint
    sin backfill acustico aplicado).
    """
    rows = [
        r for r in records if r.get("status") == "ok" and r.get("features_acusticas")
    ]
    if not rows:
        return 0
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=FEATURES_CSV_CONTEXT + ACOUSTIC_FEATURE_FIELDS,
            extrasaction="ignore",
        )
        writer.writeheader()
        for record in rows:
            row = {key: record.get(key, "") for key in FEATURES_CSV_CONTEXT}
            row.update(record["features_acusticas"])
            writer.writerow(row)
    return len(rows)


def build_summary_markdown(
    records: list[dict[str, Any]],
    total_found: int,
    audio_dir: Path,
    wall_seconds: float,
    model_name: str,
    language: str,
    report_only: bool = False,
) -> str:
    ok = [r for r in records if r.get("status") == "ok"]
    errors = [r for r in records if r.get("status") != "ok"]
    durations = [r["duracion_segundos"] for r in ok if r.get("duracion_segundos")]
    counts = {cat: sum(1 for r in ok if r.get("categoria") == cat) for cat in
              ("SERIA", "DUDOSA", "IMPROCEDENTE")}
    total_ok = len(ok)

    def pct(n: int) -> str:
        return f"{(n / total_ok * 100):.1f}%" if total_ok else "0.0%"

    def mean_of(values: list[float]) -> str:
        return f"{sum(values) / len(values):.2f}" if values else "-"

    low_confidence = sorted(
        (r for r in ok if (r.get("confianza") or 0.0) < LOW_CONFIDENCE_THRESHOLD),
        key=lambda r: r.get("confianza") or 0.0,
    )
    failed_transcripts = [r for r in ok if r.get("transcripcion_status") != "ok"]
    empty_transcripts = [r for r in ok if not (r.get("transcripcion") or "").strip()]
    suspect_transcripts = sorted(
        (r for r in ok if r.get("alertas_transcripcion")),
        key=lambda r: r.get("calidad_transcripcion") or 0.0,
    )

    category_rows = []
    for cat in ("SERIA", "DUDOSA", "IMPROCEDENTE"):
        sub = [r for r in ok if r.get("categoria") == cat]
        conf = [r["confianza"] for r in sub if r.get("confianza") is not None]
        seri = [r["seriousness_score"] for r in sub if r.get("seriousness_score") is not None]
        category_rows.append(
            f"| {cat} | {counts[cat]} | {pct(counts[cat])} | {mean_of(conf)} | {mean_of(seri)} |"
        )

    lines = [
        "# Resumen de clasificacion del dataset 911",
        "",
        f"Fecha de generacion: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Ruta analizada: `{audio_dir}`",
        f"ASR: openai-whisper-local-{model_name} (idioma forzado: {language})",
        "",
        "## Totales",
        "",
        f"- Total de audios encontrados: **{total_found}**",
        f"- Total de audios procesados: **{len(records)}**",
        f"- Procesados con exito: **{total_ok}**",
        f"- Con error: **{len(errors)}**",
        "",
        "## Distribucion por categoria",
        "",
        "| Categoria | Total | Porcentaje | Confianza media | Seriedad media |",
        "|---|---:|---:|---:|---:|",
        *category_rows,
        "",
        "## Duraciones",
        "",
    ]
    if durations:
        total_audio = sum(durations)
        lines.extend(
            [
                f"- Duracion promedio: {sum(durations) / len(durations):.1f} s",
                f"- Duracion minima: {min(durations):.1f} s",
                f"- Duracion maxima: {max(durations):.1f} s",
                "- Duracion total de audio procesado: "
                f"{format_hms(total_audio)} ({total_audio:.0f} s)",
            ]
        )
    else:
        lines.append("- No hay duraciones disponibles.")
    wall_clock_line = (
        "- Tiempo total de procesamiento (wall clock): no aplica "
        "(reporte regenerado desde checkpoint)"
        if report_only
        else f"- Tiempo total de procesamiento (wall clock): {format_hms(wall_seconds)}"
    )
    lines.extend(
        [
            wall_clock_line,
            "",
            f"## Clasificaciones de baja confianza (< {LOW_CONFIDENCE_THRESHOLD:.2f})",
            "",
        ]
    )
    if low_confidence:
        lines.append(
            f"Se detectaron **{len(low_confidence)}** clasificaciones con confianza "
            "baja que requieren revision manual:"
        )
        lines.append("")
        lines.extend(["| archivo | categoria | confianza | justificacion |", "|---|---|---:|---|"])
        for r in low_confidence:
            justif = (r.get("justificacion") or "").replace("|", "/")[:180]
            lines.append(
                f"| {r['archivo']} | {r['categoria']} | {r['confianza']:.2f} | {justif} |"
            )
    else:
        lines.append("No se detectaron clasificaciones por debajo del umbral.")

    lines.extend(["", "## Transcripciones sospechosas", ""])
    if suspect_transcripts:
        lines.append(
            f"Se detectaron **{len(suspect_transcripts)}** transcripciones con senales "
            "de baja calidad (muy cortas, repetitivas o con caracteres inesperados). "
            "Su evidencia semantica es poco confiable y conviene revisarlas manualmente:"
        )
        lines.append("")
        lines.extend(
            ["| archivo | categoria | confianza | calidad | alertas |", "|---|---|---:|---:|---|"]
        )
        for r in suspect_transcripts:
            alerts = ", ".join(r.get("alertas_transcripcion") or [])
            calidad = r.get("calidad_transcripcion")
            calidad_txt = f"{calidad:.2f}" if calidad is not None else "-"
            lines.append(
                f"| {r['archivo']} | {r['categoria']} | {r['confianza']:.2f} | "
                f"{calidad_txt} | {alerts} |"
            )
    else:
        lines.append("No se detectaron transcripciones sospechosas.")

    lines.extend(["", "## Errores", ""])
    if errors:
        lines.append(f"{len(errors)} audios fallaron (ver `errores_procesamiento.log`):")
        lines.append("")
        for r in errors:
            lines.append(f"- {r['archivo']}: {r.get('error', 'error desconocido')}")
    else:
        lines.append("No se registraron errores de procesamiento.")

    lines.extend(["", "## Observaciones", ""])
    observations = [
        "El dataset proviene de grabaciones reales de despacho 911 en ingles; el "
        "pipeline uso los diccionarios bilingues (es/en) del analizador semantico.",
        "El dataset fue previamente filtrado por duracion (solo audios <= 5 min, "
        "ver `reportes/reporte_filtrado_duracion.md`).",
        "Los audios se COPIARON a `dataset_clasificado/` para conservar el dataset "
        "original intacto.",
    ]
    if failed_transcripts:
        observations.append(
            f"{len(failed_transcripts)} audios no pudieron transcribirse y se "
            "clasificaron solo con evidencia acustica."
        )
    if empty_transcripts:
        observations.append(
            f"{len(empty_transcripts)} audios produjeron transcripcion vacia "
            "(posible silencio, ruido o solo tonos); tienden a caer en DUDOSA."
        )
    if suspect_transcripts:
        observations.append(
            f"{len(suspect_transcripts)} transcripciones fueron marcadas como "
            "sospechosas; su confianza fue reducida automaticamente y la alerta "
            "quedo registrada en la justificacion."
        )
    if total_ok:
        avg_conf = sum(r.get("confianza") or 0.0 for r in ok) / total_ok
        observations.append(f"Confianza promedio de clasificacion: {avg_conf:.2f}.")
    observations.append(
        "La clasificacion es heuristica y auditable, no un modelo entrenado; no "
        "debe usarse para cerrar llamadas automaticamente."
    )
    lines.extend(f"- {obs}" for obs in observations)
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clasifica en batch un dataset de llamadas 911 (SERIA/DUDOSA/IMPROCEDENTE)."
    )
    parser.add_argument(
        "--audio-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "audios" / "911_recordings",
        help="Directorio raiz con los audios (se recorre recursivamente).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT,
        help="Directorio donde se generan reportes y dataset_clasificado/.",
    )
    parser.add_argument("--model", choices=("tiny", "base", "small"), default="tiny")
    parser.add_argument("--language", default="en", help="Idioma para Whisper.")
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="Procesos paralelos (cada uno carga su propio modelo Whisper).",
    )
    parser.add_argument(
        "--torch-threads",
        type=int,
        default=2,
        help="Hilos de torch por worker (evita sobresuscripcion de CPU).",
    )
    parser.add_argument(
        "--max-files", type=int, default=0, help="Limitar a N archivos (0 = todos)."
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Ignora el checkpoint previo y reprocesa todo.",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="No procesa audios nuevos: genera reportes solo con el checkpoint existente.",
    )
    parser.add_argument(
        "--redo-sospechosos",
        action="store_true",
        help=(
            "Reprocesa los audios del checkpoint cuya transcripcion tiene alertas "
            "de calidad (util con --model base para retranscribir alucinaciones)."
        ),
    )
    parser.add_argument(
        "--redo-archivo",
        action="append",
        default=[],
        metavar="NOMBRE",
        help="Reprocesa un archivo especifico del checkpoint (repetible).",
    )
    parser.add_argument(
        "--redo-acustico",
        action="store_true",
        help=(
            "Backfill acustico: recalcula features y re-puntua los registros del "
            "checkpoint sin `features_acusticas`, reutilizando la transcripcion "
            "guardada (no carga Whisper)."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    audio_dir = args.audio_dir.resolve()
    output_dir = args.output_dir.resolve()
    if not audio_dir.is_dir():
        print(f"ERROR: no existe el directorio de audios: {audio_dir}")
        raise SystemExit(1)
    output_dir.mkdir(parents=True, exist_ok=True)
    classified_dir = output_dir / "dataset_clasificado"
    checkpoint_path = output_dir / CHECKPOINT_NAME
    error_log_path = output_dir / "errores_procesamiento.log"
    error_log_path.touch(exist_ok=True)

    files = collect_audio_files(audio_dir)
    total_found = len(files)
    if args.max_files > 0:
        files = files[: args.max_files]

    selective = args.redo_sospechosos or bool(args.redo_archivo)
    if args.report_only and (selective or args.redo_acustico):
        print("ERROR: --report-only no es compatible con los modos --redo-*.")
        raise SystemExit(1)
    if args.redo_acustico and (selective or args.fresh):
        print("ERROR: --redo-acustico no es compatible con --fresh ni otros modos --redo-*.")
        raise SystemExit(1)

    previous = {} if args.fresh else load_checkpoint(checkpoint_path)
    if args.fresh and checkpoint_path.exists():
        checkpoint_path.unlink()

    old_redo: dict[str, dict[str, Any]] = {}
    if selective:
        redo_paths = select_redo_paths(
            previous, files, args.redo_sospechosos, args.redo_archivo
        )
        old_redo = {path: previous.pop(path) for path in redo_paths}
        for record in old_redo.values():
            remove_category_copies(record["archivo"], classified_dir)
        print(f"Reprocesamiento selectivo: {len(old_redo)} audios del checkpoint.", flush=True)
    elif args.redo_acustico:
        redo_paths = select_acoustic_backfill_paths(previous, files)
        old_redo = {path: previous.pop(path) for path in redo_paths}
        for record in old_redo.values():
            remove_category_copies(record["archivo"], classified_dir)
        print(
            f"Backfill acustico: {len(old_redo)} registros sin features persistidas.",
            flush=True,
        )

    pending = [p for p in files if str(p) not in previous]
    if args.redo_acustico:
        # En modo backfill solo se tocan registros del checkpoint; los audios
        # nunca procesados requieren ASR y se dejan para una corrida normal.
        skipped_new = sum(1 for p in pending if str(p) not in old_redo)
        if skipped_new:
            print(
                f"Nota: {skipped_new} audios sin registro previo se omiten en "
                "--redo-acustico (requieren ASR; usar una corrida normal).",
                flush=True,
            )
        pending = [p for p in pending if str(p) in old_redo]
    reused = len(files) - len(pending)
    if args.report_only:
        print(
            f"Modo report-only: se omiten {len(pending)} audios pendientes; "
            f"se reportan los {reused} ya procesados.",
            flush=True,
        )
        pending = []

    print(f"Ruta analizada        : {audio_dir}", flush=True)
    print(f"Audios encontrados    : {total_found}", flush=True)
    print(f"A procesar en este run: {len(pending)} (reusados de checkpoint: {reused})", flush=True)
    print(f"Modelo Whisper        : {args.model} | idioma: {args.language}", flush=True)
    print(f"Workers               : {args.workers} (x{args.torch_threads} hilos torch)", flush=True)
    print("-" * 70, flush=True)

    records: dict[str, dict[str, Any]] = dict(previous)
    start = time.time()
    done_count = 0

    if pending:
        with ProcessPoolExecutor(
            max_workers=args.workers,
            initializer=_init_worker,
            initargs=(args.model, args.torch_threads, not args.redo_acustico),
        ) as executor:
            futures = {
                executor.submit(
                    _worker_process_audio,
                    str(path),
                    args.language,
                    args.model,
                    old_redo.get(str(path)) if args.redo_acustico else None,
                ): path
                for path in pending
            }
            for future in as_completed(futures):
                record = future.result()
                records[record["ruta_original"]] = record
                append_checkpoint(checkpoint_path, record)
                done_count += 1

                if record["status"] == "ok":
                    copy_to_category(record, classified_dir)
                    detail = f"{record['categoria']} ({record['confianza']:.2f})"
                else:
                    log_error(error_log_path, record)
                    detail = f"ERROR: {record.get('error', '')[:60]}"

                elapsed = time.time() - start
                rate = elapsed / done_count
                remaining = rate * (len(pending) - done_count)
                progress = (done_count + reused) / len(files) * 100
                print(
                    f"[{done_count + reused:4d}/{len(files)}] {progress:5.1f}% | "
                    f"{record['archivo']:<20} | {detail:<40} | "
                    f"{record.get('tiempo_proceso_segundos', 0):6.1f}s | "
                    f"ETA {format_hms(remaining)}",
                    flush=True,
                )

    # Asegura copias tambien para registros reusados del checkpoint.
    for record in records.values():
        if record.get("status") == "ok":
            copy_to_category(record, classified_dir)

    # Retro-rellena la evaluacion de calidad de transcripcion en registros de
    # checkpoints previos (permite regenerar reportes sin reprocesar audio).
    for record in records.values():
        ensure_transcript_quality(record)

    ordered = [records[str(p)] for p in files if str(p) in records]
    wall_seconds = time.time() - start

    write_csv(ordered, output_dir / "clasificacion_dataset.csv")
    write_json(ordered, output_dir / "clasificacion_dataset.json")
    features_rows = write_features_csv(ordered, output_dir / FEATURES_CSV_NAME)
    summary = build_summary_markdown(
        ordered,
        total_found,
        audio_dir,
        wall_seconds,
        args.model,
        args.language,
        report_only=args.report_only,
    )
    (output_dir / "RESUMEN_DATASET.md").write_text(summary, encoding="utf-8")

    ok = [r for r in ordered if r.get("status") == "ok"]
    errors = [r for r in ordered if r.get("status") != "ok"]
    counts = {cat: sum(1 for r in ok if r.get("categoria") == cat) for cat in
              ("SERIA", "DUDOSA", "IMPROCEDENTE")}

    print("\n" + "=" * 70, flush=True)
    print("Procesamiento terminado", flush=True)
    print(f"\nRuta analizada:\n{audio_dir}\n", flush=True)
    print(f"Audios encontrados: {total_found}", flush=True)
    print(f"Audios analizados : {len(ordered)}", flush=True)
    print(f"\nSERIA        : {counts['SERIA']}", flush=True)
    print(f"DUDOSA       : {counts['DUDOSA']}", flush=True)
    print(f"IMPROCEDENTE : {counts['IMPROCEDENTE']}", flush=True)
    print(f"Errores      : {len(errors)}", flush=True)
    print("\nArchivos generados:", flush=True)
    print("  clasificacion_dataset.csv", flush=True)
    print("  clasificacion_dataset.json", flush=True)
    if features_rows:
        print(f"  {FEATURES_CSV_NAME} ({features_rows} filas con features acusticas)", flush=True)
    print("  RESUMEN_DATASET.md", flush=True)
    print("  errores_procesamiento.log", flush=True)
    print("  dataset_clasificado/ (copias por categoria)", flush=True)

    if old_redo:
        print("\nComparacion de audios reprocesados (antes -> despues):", flush=True)
        for path in sorted(old_redo):
            old = old_redo[path]
            new = records.get(path, {})
            old_alerts = "; ".join(old.get("alertas_transcripcion") or []) or "sin alertas"
            new_alerts = "; ".join(new.get("alertas_transcripcion") or []) or "sin alertas"
            print(
                f"  {old.get('archivo', '?'):<15} "
                f"{old.get('categoria')}({old.get('confianza')}) [{old_alerts}] -> "
                f"{new.get('categoria')}({new.get('confianza')}) [{new_alerts}]",
                flush=True,
            )

    print(f"\nTiempo total: {format_hms(wall_seconds)}", flush=True)


if __name__ == "__main__":
    main()
