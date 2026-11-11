from __future__ import annotations

import csv

from procesar_dataset import (
    ACOUSTIC_FEATURE_FIELDS,
    FEATURES_CSV_CONTEXT,
    flatten_acoustic_features,
    remove_category_copies,
    select_acoustic_backfill_paths,
    select_redo_paths,
    write_features_csv,
)
from src.audio.acoustic_features import empty_acoustic_features


def _record(archivo: str, alertas: list[str] | None, status: str = "ok") -> dict:
    return {
        "archivo": archivo,
        "status": status,
        "transcripcion": "texto suficientemente largo para no disparar alertas " * 3,
        "calidad_transcripcion": 1.0,
        "alertas_transcripcion": alertas or [],
        "confianza": 0.9,
        "justificacion": "",
    }


def test_redo_suspects_selects_only_records_with_alerts(tmp_path):
    files = [tmp_path / "a.mp3", tmp_path / "b.mp3"]
    previous = {
        str(files[0]): _record("a.mp3", ["transcripcion_repetitiva"]),
        str(files[1]): _record("b.mp3", None),
    }

    selected = select_redo_paths(previous, files, redo_suspects=True, redo_names=[])

    assert selected == [str(files[0])]


def test_redo_by_name_includes_error_records(tmp_path):
    files = [tmp_path / "fallo.mp3"]
    previous = {str(files[0]): _record("fallo.mp3", None, status="error")}

    selected = select_redo_paths(
        previous, files, redo_suspects=False, redo_names=["fallo.mp3"]
    )

    assert selected == [str(files[0])]


def test_redo_ignores_files_no_longer_in_dataset(tmp_path):
    missing = tmp_path / "borrado.mp3"
    previous = {str(missing): _record("borrado.mp3", ["transcripcion_muy_corta"])}

    selected = select_redo_paths(previous, files=[], redo_suspects=True, redo_names=[])

    assert selected == []


def test_redo_backfills_quality_for_old_checkpoints(tmp_path):
    # Registro de un checkpoint anterior a assess_transcript_quality: sin campos
    # de calidad y con transcripcion de 2 palabras (sospechosa).
    files = [tmp_path / "viejo.mp3"]
    record = {
        "archivo": "viejo.mp3",
        "status": "ok",
        "transcripcion": "Title 4",
        "confianza": 0.85,
        "justificacion": "",
    }
    previous = {str(files[0]): record}

    selected = select_redo_paths(previous, files, redo_suspects=True, redo_names=[])

    assert selected == [str(files[0])]


def test_remove_category_copies_deletes_from_all_categories(tmp_path):
    classified = tmp_path / "dataset_clasificado"
    for categoria in ("seria", "dudosa"):
        target = classified / categoria / "call_1.mp3"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"x")

    remove_category_copies("call_1.mp3", classified)

    assert not (classified / "seria" / "call_1.mp3").exists()
    assert not (classified / "dudosa" / "call_1.mp3").exists()


def test_remove_category_copies_is_noop_without_copies(tmp_path):
    remove_category_copies("inexistente.mp3", tmp_path / "no_existe")


def _acoustic_dict() -> dict:
    return {
        "duration_seconds": 12.5,
        "rms_energy": 0.05,
        "estimated_f0_hz": 210.0,
        "estimated_jitter_ratio": 0.21,
        "mfcc_mean": [float(i) for i in range(13)],
        "mfcc_std": [float(i) * 0.1 for i in range(13)],
        "audio_quality": "aceptable",
        "acoustic_anomaly_flags": ["snr_bajo", "pausas_prolongadas"],
        "emergency_audio_indicators": {
            "urgency_score": 0.7,
            "seriousness_audio_score": 0.55,
            "audio_reliability": 0.8,
        },
    }


def test_flatten_produces_exactly_the_canonical_fields():
    flat = flatten_acoustic_features(_acoustic_dict())

    assert list(flat.keys()) == ACOUSTIC_FEATURE_FIELDS
    assert flat["mfcc_mean_01"] == 0.0
    assert flat["mfcc_mean_13"] == 12.0
    assert flat["mfcc_std_02"] == 0.1
    assert flat["urgency_score"] == 0.7
    assert flat["seriousness_audio_score"] == 0.55
    assert flat["acoustic_anomaly_flags"] == "snr_bajo; pausas_prolongadas"
    # Campos ausentes en el dict de entrada quedan en None, no lanzan KeyError.
    assert flat["spectral_flatness"] is None


def test_flatten_handles_empty_acoustic_features():
    flat = flatten_acoustic_features(empty_acoustic_features("sin_audio"))

    assert list(flat.keys()) == ACOUSTIC_FEATURE_FIELDS
    assert flat["estimated_f0_hz"] is None
    assert flat["mfcc_mean_01"] is None
    assert flat["audio_quality"] == "no_evaluada"
    assert flat["acoustic_anomaly_flags"] == ""


def test_acoustic_backfill_selects_only_ok_records_without_features(tmp_path):
    files = [tmp_path / name for name in ("a.mp3", "b.mp3", "c.mp3")]
    con_features = _record("b.mp3", None)
    con_features["features_acusticas"] = {"rms_energy": 0.1}
    previous = {
        str(files[0]): _record("a.mp3", None),
        str(files[1]): con_features,
        str(files[2]): _record("c.mp3", None, status="error"),
        str(tmp_path / "borrado.mp3"): _record("borrado.mp3", None),
    }

    selected = select_acoustic_backfill_paths(previous, files)

    assert selected == [str(files[0])]


def test_write_features_csv_only_rows_with_features(tmp_path):
    con_features = _record("a.mp3", None)
    con_features["categoria"] = "SERIA"
    con_features["features_acusticas"] = flatten_acoustic_features(_acoustic_dict())
    sin_features = _record("b.mp3", None)
    out = tmp_path / "features.csv"

    written = write_features_csv([con_features, sin_features], out)

    assert written == 1
    with out.open(encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    assert rows[0]["archivo"] == "a.mp3"
    assert rows[0]["categoria"] == "SERIA"
    assert rows[0]["urgency_score"] == "0.7"
    assert list(rows[0].keys()) == FEATURES_CSV_CONTEXT + ACOUSTIC_FEATURE_FIELDS


def test_write_features_csv_skips_file_without_features(tmp_path):
    out = tmp_path / "features.csv"

    written = write_features_csv([_record("a.mp3", None)], out)

    assert written == 0
    assert not out.exists()
