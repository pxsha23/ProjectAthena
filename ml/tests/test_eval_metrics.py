"""Metric values checked against hand-worked examples."""

import math

import numpy as np
import pytest

from athena_advisor.eval import metrics as m

LABELS = ("a", "b", "c")
# Gold and predicted label sets for 4 rows:
#   row 0: gold {a, c}  predicted {a}
#   row 1: gold {b}     predicted {b, c}
#   row 2: gold {}      predicted {}
#   row 3: gold {a, b}  predicted {a}
Y_TRUE = np.array([[1, 0, 1], [0, 1, 0], [0, 0, 0], [1, 1, 0]])
Y_PRED = np.array([[1, 0, 0], [0, 1, 1], [0, 0, 0], [1, 0, 0]])


def test_f1_variants() -> None:
    # Pooled: TP 3, FP 1, FN 2 -> 2*3 / (6 + 1 + 2) = 2/3.
    assert m.micro_f1(Y_TRUE, Y_PRED) == pytest.approx(2 / 3)
    # Per label: a = 1, b = 2/3, c = 0 -> mean 5/9.
    assert m.macro_f1(Y_TRUE, Y_PRED) == pytest.approx(5 / 9)
    # Per row: 2/3, 2/3, 1 (empty and empty is a correct abstention), 2/3 -> mean 3/4.
    assert m.samples_f1(Y_TRUE, Y_PRED) == pytest.approx(0.75)


def test_exact_match_and_hamming() -> None:
    assert m.exact_match(Y_TRUE, Y_PRED) == 0.25  # only row 2 is exactly right
    assert m.hamming_loss(Y_TRUE, Y_PRED) == 0.25  # 3 wrong decisions out of 12
    assert m.intent_accuracy(Y_TRUE, Y_PRED) == 0.25


def test_per_label() -> None:
    report = m.per_label(Y_TRUE, Y_PRED, LABELS)
    assert report["a"] == {"precision": 1.0, "recall": 1.0, "f1": 1.0, "support": 2}
    assert report["b"]["precision"] == 1.0 and report["b"]["recall"] == 0.5
    assert report["c"] == {"precision": 0.0, "recall": 0.0, "f1": 0.0, "support": 1}


def test_perfect_and_empty_predictions() -> None:
    assert m.micro_f1(Y_TRUE, Y_TRUE) == m.macro_f1(Y_TRUE, Y_TRUE) == 1.0
    nothing = np.zeros_like(Y_TRUE)
    assert m.micro_f1(Y_TRUE, nothing) == 0.0  # no division by zero warnings or NaN


def test_lead_accuracy_counts_only_rows_with_a_lead() -> None:
    lead_true = np.array([0, -1, 2, 1])
    lead_probs = np.array([[0.7, 0.2, 0.1], [0.1, 0.1, 0.8], [0.2, 0.5, 0.3], [0.1, 0.6, 0.3]])
    # Rows 0, 2 and 3 have a lead; rows 0 and 3 are right.
    assert m.lead_accuracy(lead_true, lead_probs) == {"lead_accuracy": pytest.approx(2 / 3), "lead_rows": 3}
    none = m.lead_accuracy(np.array([-1, -1]), lead_probs[:2])
    assert none["lead_rows"] == 0 and math.isnan(none["lead_accuracy"])


def test_expected_calibration_error() -> None:
    # Two rows say 0.9 and one of them is right (gap 0.4); two say 0.1 and neither is right (gap 0.1).
    ece = m.expected_calibration_error(np.array([0.9, 0.9, 0.1, 0.1]), np.array([1, 0, 0, 0]))
    assert ece == pytest.approx(0.5 * 0.4 + 0.5 * 0.1)
    # Calibrated: 0.75 confidence, right 3 times out of 4.
    assert m.expected_calibration_error(np.full(4, 0.75), np.array([1, 1, 1, 0])) == pytest.approx(0.0)
    # The edges 0 and 1 land in the first and last bins.
    assert m.expected_calibration_error(np.array([0.0, 1.0]), np.array([0, 1])) == pytest.approx(0.0)


def test_team_and_lead_ece() -> None:
    team_probs = np.array([[0.9, 0.1], [0.9, 0.1]])
    y_true = np.array([[1, 0], [0, 0]])
    assert m.team_ece(y_true, team_probs) == pytest.approx(0.5 * 0.4 + 0.5 * 0.1)
    lead_probs = np.array([[0.8, 0.2], [0.6, 0.4], [0.5, 0.5]])
    # Rows with a lead: confidence 0.8 (right) and 0.6 (wrong). Bins: |1 - 0.8| and |0 - 0.6|, half each.
    assert m.lead_ece(np.array([0, 1, -1]), lead_probs) == pytest.approx(0.5 * 0.2 + 0.5 * 0.6)


def test_multilabel_report_has_every_metric() -> None:
    probs = Y_PRED * 0.8 + 0.1
    report = m.multilabel_report(
        Y_TRUE, probs, np.array([0, 1, -1, 0]), probs / probs.sum(1, keepdims=True), LABELS
    )
    assert report["micro_f1"] == pytest.approx(2 / 3) and report["lead_rows"] == 3
    assert {
        "macro_f1",
        "samples_f1",
        "exact_match",
        "hamming_loss",
        "team_ece",
        "lead_ece",
        "per_label",
    } <= set(report)


def test_clinc_metrics() -> None:
    lead_true = np.array([0, 1, -1, -1])
    out_of_scope = np.array([False, False, True, True])
    predicted = np.array([0, -1, -1, 2])  # in-scope: right, wrongly rejected; oos: caught, missed
    result = m.clinc_metrics(lead_true, out_of_scope, predicted)
    assert (result["in_scope_accuracy"], result["out_of_scope_recall"]) == (0.5, 0.5)
    assert (result["in_scope_rows"], result["out_of_scope_rows"]) == (2, 2)


def test_single_label_predictions_with_out_of_scope_threshold() -> None:
    probs = np.array([[0.6, 0.4], [0.45, 0.55], [0.5, 0.5]])
    assert m.single_label_predictions(probs).tolist() == [0, 1, 0]
    assert m.single_label_predictions(probs, oos_threshold=0.56).tolist() == [0, -1, -1]


def test_single_label_f1_for_nlbse() -> None:
    result = m.single_label_f1(
        np.array([0, 0, 1, 2]), np.array([0, 1, 1, 2]), ("bug", "enhancement", "question")
    )
    assert result["micro_f1"] == pytest.approx(0.75)  # equal to accuracy for single-label data
    # bug 2/3, enhancement 2/3, question 1 -> mean 7/9.
    assert result["macro_f1"] == pytest.approx(7 / 9)
    assert result["per_label"]["question"]["f1"] == 1.0
