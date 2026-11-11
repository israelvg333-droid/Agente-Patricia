from __future__ import annotations

import pytest

from src.evaluation.metrics import (
    accuracy,
    binary_auroc,
    brier_score,
    confusion_matrix,
    macro_f1,
    per_class_metrics,
)
from src.evaluation.sampling import normalize_label, stratified_labeling_sample

# ---------------------------------------------------------------------------
# confusion_matrix
# ---------------------------------------------------------------------------


def test_confusion_matrix_counts_matches_and_confusions():
    y_true = ["SERIA", "SERIA", "DUDOSA", "IMPROCEDENTE"]
    y_pred = ["SERIA", "DUDOSA", "DUDOSA", "SERIA"]

    matrix = confusion_matrix(y_true, y_pred)

    assert matrix["SERIA"]["SERIA"] == 1
    assert matrix["SERIA"]["DUDOSA"] == 1
    assert matrix["DUDOSA"]["DUDOSA"] == 1
    assert matrix["IMPROCEDENTE"]["SERIA"] == 1
    assert matrix["IMPROCEDENTE"]["IMPROCEDENTE"] == 0


def test_confusion_matrix_with_explicit_labels_includes_empty_classes():
    matrix = confusion_matrix(["SERIA"], ["SERIA"], labels=["DUDOSA", "IMPROCEDENTE", "SERIA"])

    assert matrix["DUDOSA"] == {"DUDOSA": 0, "IMPROCEDENTE": 0, "SERIA": 0}
    assert matrix["SERIA"]["SERIA"] == 1


def test_confusion_matrix_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        confusion_matrix(["SERIA"], [])


def test_confusion_matrix_rejects_labels_outside_universe():
    with pytest.raises(ValueError):
        confusion_matrix(["SERIA"], ["BROMA"], labels=["SERIA"])


# ---------------------------------------------------------------------------
# per_class_metrics / accuracy / macro_f1
# ---------------------------------------------------------------------------


def test_perfect_classification_yields_ones():
    matrix = confusion_matrix(["SERIA", "DUDOSA"], ["SERIA", "DUDOSA"])
    per_class = per_class_metrics(matrix)

    assert per_class["SERIA"] == {"precision": 1.0, "recall": 1.0, "f1": 1.0, "support": 1}
    assert accuracy(matrix) == 1.0
    assert macro_f1(per_class) == 1.0


def test_recall_counts_misses_of_the_true_class():
    # 3 SERIA reales: 2 detectadas, 1 degradada a DUDOSA -> recall 2/3.
    matrix = confusion_matrix(
        ["SERIA", "SERIA", "SERIA", "DUDOSA"],
        ["SERIA", "SERIA", "DUDOSA", "DUDOSA"],
    )
    per_class = per_class_metrics(matrix)

    assert per_class["SERIA"]["recall"] == pytest.approx(2 / 3)
    assert per_class["SERIA"]["precision"] == 1.0
    assert per_class["DUDOSA"]["precision"] == pytest.approx(1 / 2)


def test_class_never_predicted_has_none_precision_and_zero_recall():
    matrix = confusion_matrix(
        ["IMPROCEDENTE", "SERIA"],
        ["SERIA", "SERIA"],
        labels=["IMPROCEDENTE", "SERIA"],
    )
    per_class = per_class_metrics(matrix)

    assert per_class["IMPROCEDENTE"]["precision"] is None
    assert per_class["IMPROCEDENTE"]["recall"] == 0.0
    assert per_class["IMPROCEDENTE"]["f1"] is None


def test_class_without_real_examples_is_excluded_from_macro_f1():
    matrix = confusion_matrix(
        ["SERIA", "SERIA"],
        ["SERIA", "DUDOSA"],
        labels=["DUDOSA", "SERIA"],
    )
    per_class = per_class_metrics(matrix)

    assert per_class["DUDOSA"]["support"] == 0
    assert per_class["DUDOSA"]["recall"] is None
    # Solo SERIA (soporte > 0) participa en el promedio.
    assert macro_f1(per_class) == per_class["SERIA"]["f1"]


def test_accuracy_of_empty_matrix_is_none():
    matrix = confusion_matrix([], [], labels=["SERIA", "DUDOSA"])

    assert accuracy(matrix) is None
    assert macro_f1(per_class_metrics(matrix)) is None


# ---------------------------------------------------------------------------
# binary_auroc
# ---------------------------------------------------------------------------


def test_auroc_perfect_separation_is_one():
    assert binary_auroc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0


def test_auroc_inverted_scores_is_zero():
    assert binary_auroc([0, 0, 1, 1], [0.9, 0.8, 0.2, 0.1]) == 0.0


def test_auroc_all_tied_scores_is_half():
    assert binary_auroc([0, 1, 0, 1], [0.5, 0.5, 0.5, 0.5]) == 0.5


def test_auroc_single_class_is_undefined():
    assert binary_auroc([1, 1, 1], [0.2, 0.5, 0.9]) is None
    assert binary_auroc([0, 0], [0.2, 0.5]) is None


def test_auroc_partial_overlap_matches_manual_computation():
    # Pares (pos, neg): (0.8>0.1), (0.8>0.4), (0.3>0.1), (0.3<0.4) -> 3/4.
    assert binary_auroc([0, 1, 0, 1], [0.1, 0.8, 0.4, 0.3]) == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# brier_score
# ---------------------------------------------------------------------------


def test_brier_score_zero_for_perfect_confidence():
    assert brier_score([1, 0], [1.0, 0.0]) == 0.0


def test_brier_score_penalizes_confident_errors():
    assert brier_score([0], [1.0]) == 1.0
    assert brier_score([1, 0], [0.7, 0.2]) == pytest.approx((0.09 + 0.04) / 2)


def test_brier_score_empty_is_none():
    assert brier_score([], []) is None


# ---------------------------------------------------------------------------
# normalize_label
# ---------------------------------------------------------------------------


def test_normalize_label_accepts_case_spaces_and_accents():
    assert normalize_label(" seria ") == "SERIA"
    assert normalize_label("Dudosa") == "DUDOSA"
    assert normalize_label("improcedente") == "IMPROCEDENTE"


def test_normalize_label_rejects_unknown_or_empty():
    assert normalize_label("") is None
    assert normalize_label(None) is None
    assert normalize_label("broma") is None


# ---------------------------------------------------------------------------
# stratified_labeling_sample
# ---------------------------------------------------------------------------


def _record(name: str, categoria: str) -> dict:
    return {"archivo": name, "categoria": categoria}


def test_sample_includes_all_minority_classes_and_n_serias():
    records = (
        [_record(f"dudosa_{i}.mp3", "DUDOSA") for i in range(5)]
        + [_record("improc_0.mp3", "IMPROCEDENTE")]
        + [_record(f"seria_{i}.mp3", "SERIA") for i in range(50)]
    )

    sample = stratified_labeling_sample(records, serias=10, seed=1)

    categorias = [r["categoria"] for r in sample]
    assert categorias.count("DUDOSA") == 5
    assert categorias.count("IMPROCEDENTE") == 1
    assert categorias.count("SERIA") == 10


def test_sample_is_reproducible_and_sorted_by_file():
    records = [_record(f"seria_{i:02d}.mp3", "SERIA") for i in range(30)]

    first = stratified_labeling_sample(records, serias=5, seed=42)
    second = stratified_labeling_sample(records, serias=5, seed=42)

    assert first == second
    files = [r["archivo"] for r in first]
    assert files == sorted(files)


def test_sample_excludes_records_without_valid_category():
    records = [
        _record("fallo.mp3", ""),
        _record("dudosa.mp3", "DUDOSA"),
    ]

    sample = stratified_labeling_sample(records, serias=5, seed=1)

    assert [r["archivo"] for r in sample] == ["dudosa.mp3"]


def test_sample_takes_all_serias_when_pool_is_small():
    records = [_record(f"seria_{i}.mp3", "SERIA") for i in range(3)]

    sample = stratified_labeling_sample(records, serias=15, seed=1)

    assert len(sample) == 3
