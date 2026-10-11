"""Metrics, generic over any label list.

Inputs are plain arrays:
    y_true, y_pred   (n, K) 0/1 matrices (gold labels and predicted labels)
    lead_true        (n,)   gold lead index, -1 when the row has no lead
    lead_probs       (n, K) predicted lead distribution
    team_probs       (n, K) predicted probability per label
Turning probabilities into 0/1 predictions is the decision layer's job; `threshold()` is the plain
fixed-threshold version used by the baselines and the ablations.
"""

from typing import Any

import numpy as np

ECE_BINS = 15


def threshold(team_probs: np.ndarray, value: float = 0.5) -> np.ndarray:
    return (np.asarray(team_probs) >= value).astype(np.int8)


def _f1(tp: np.ndarray, fp: np.ndarray, fn: np.ndarray) -> np.ndarray:
    """F1 = 2TP / (2TP + FP + FN), defined as 0 when there is nothing to count."""
    denominator = 2 * tp + fp + fn
    return np.divide(2 * tp, denominator, out=np.zeros_like(denominator, dtype=float), where=denominator > 0)


def _counts(y_true: np.ndarray, y_pred: np.ndarray, axis: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    y_true, y_pred = np.asarray(y_true, bool), np.asarray(y_pred, bool)
    return (
        (y_true & y_pred).sum(axis=axis).astype(float),
        (~y_true & y_pred).sum(axis=axis).astype(float),
        (y_true & ~y_pred).sum(axis=axis).astype(float),
    )


def micro_f1(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Pools every (row, label) decision: frequent labels dominate."""
    tp, fp, fn = (c.sum() for c in _counts(y_true, y_pred, axis=0))
    return float(_f1(np.array(tp), np.array(fp), np.array(fn)))


def macro_f1(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """The mean of per-label F1: every label counts the same, however rare."""
    return float(_f1(*_counts(y_true, y_pred, axis=0)).mean())


def samples_f1(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """The mean of per-row F1. A row with no gold and no predicted label scores 1 (a correct abstention)."""
    tp, fp, fn = _counts(y_true, y_pred, axis=1)
    per_row = _f1(tp, fp, fn)
    per_row[(tp + fp + fn) == 0] = 1.0
    return float(per_row.mean())


def exact_match(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Share of rows whose predicted label set is exactly the gold set."""
    return float((np.asarray(y_true, bool) == np.asarray(y_pred, bool)).all(axis=1).mean())


def hamming_loss(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Share of individual (row, label) decisions that are wrong."""
    return float((np.asarray(y_true, bool) != np.asarray(y_pred, bool)).mean())


def per_label(y_true: np.ndarray, y_pred: np.ndarray, labels: tuple[str, ...]) -> dict[str, dict[str, float]]:
    tp, fp, fn = _counts(y_true, y_pred, axis=0)
    precision = np.divide(tp, tp + fp, out=np.zeros_like(tp), where=(tp + fp) > 0)
    recall = np.divide(tp, tp + fn, out=np.zeros_like(tp), where=(tp + fn) > 0)
    f1 = _f1(tp, fp, fn)
    support = np.asarray(y_true, bool).sum(axis=0)
    return {
        label: {
            "precision": float(precision[i]),
            "recall": float(recall[i]),
            "f1": float(f1[i]),
            "support": int(support[i]),
        }
        for i, label in enumerate(labels)
    }


def lead_accuracy(lead_true: np.ndarray, lead_probs: np.ndarray) -> dict[str, float | int]:
    """Accuracy of argmax(lead_probs), only on rows that have a gold lead."""
    lead_true = np.asarray(lead_true)
    mask = lead_true >= 0
    rows = int(mask.sum())
    if rows == 0:
        return {"lead_accuracy": float("nan"), "lead_rows": 0}
    correct = np.asarray(lead_probs)[mask].argmax(axis=1) == lead_true[mask]
    return {"lead_accuracy": float(correct.mean()), "lead_rows": rows}


def expected_calibration_error(confidence: np.ndarray, correct: np.ndarray, bins: int = ECE_BINS) -> float:
    """ECE: the gap between confidence and accuracy, averaged over equal-width bins weighted by size.

    A model that says 80% should be right 80% of the time; ECE is how far off that is on average.
    """
    confidence = np.asarray(confidence, dtype=float).ravel()
    correct = np.asarray(correct, dtype=float).ravel()
    if confidence.size == 0:
        return float("nan")
    # Bin i holds confidences in (edge_i, edge_i+1]; zero falls into the first bin.
    index = np.clip(np.ceil(confidence * bins).astype(int) - 1, 0, bins - 1)
    total = 0.0
    for b in range(bins):
        members = index == b
        if members.any():
            total += members.mean() * abs(correct[members].mean() - confidence[members].mean())
    return float(total)


def team_ece(y_true: np.ndarray, team_probs: np.ndarray, bins: int = ECE_BINS) -> float:
    """Calibration of every per-label probability as its own yes/no prediction."""
    return expected_calibration_error(team_probs, y_true, bins)


def lead_ece(lead_true: np.ndarray, lead_probs: np.ndarray, bins: int = ECE_BINS) -> float:
    """Calibration of the top lead probability, on rows that have a gold lead."""
    lead_true = np.asarray(lead_true)
    mask = lead_true >= 0
    probs = np.asarray(lead_probs)[mask]
    if probs.size == 0:
        return float("nan")
    return expected_calibration_error(probs.max(axis=1), probs.argmax(axis=1) == lead_true[mask], bins)


def multilabel_report(
    y_true: np.ndarray,
    team_probs: np.ndarray,
    lead_true: np.ndarray,
    lead_probs: np.ndarray,
    labels: tuple[str, ...],
    y_pred: np.ndarray | None = None,
) -> dict[str, Any]:
    """Every team and lead metric at once. y_pred defaults to a 0.5 threshold on team_probs."""
    y_pred = threshold(team_probs) if y_pred is None else y_pred
    return {
        "micro_f1": micro_f1(y_true, y_pred),
        "macro_f1": macro_f1(y_true, y_pred),
        "samples_f1": samples_f1(y_true, y_pred),
        "exact_match": exact_match(y_true, y_pred),
        "hamming_loss": hamming_loss(y_true, y_pred),
        **lead_accuracy(lead_true, lead_probs),
        "team_ece": team_ece(y_true, team_probs),
        "lead_ece": lead_ece(lead_true, lead_probs),
        "per_label": per_label(y_true, y_pred, labels),
        "rows": int(len(y_true)),
    }


# ---------------------------------------------------------------- benchmark-specific metrics


def intent_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """MixATIS / MixSNIPS: an utterance counts as correct only when its whole intent set is right."""
    return exact_match(y_true, y_pred)


def single_label_predictions(lead_probs: np.ndarray, oos_threshold: float | None = None) -> np.ndarray:
    """argmax label per row; -1 (out of scope) when the top probability is below oos_threshold."""
    lead_probs = np.asarray(lead_probs)
    predicted = lead_probs.argmax(axis=1)
    if oos_threshold is not None:
        predicted = np.where(lead_probs.max(axis=1) < oos_threshold, -1, predicted)
    return predicted


def clinc_metrics(lead_true: np.ndarray, out_of_scope: np.ndarray, predicted: np.ndarray) -> dict[str, Any]:
    """CLINC150: in-scope accuracy (predicting out-of-scope for an in-scope query is wrong) and
    out-of-scope recall (share of out-of-scope queries predicted as out of scope, i.e. -1)."""
    out_of_scope = np.asarray(out_of_scope, bool)
    lead_true, predicted = np.asarray(lead_true), np.asarray(predicted)
    in_scope = ~out_of_scope
    return {
        "in_scope_accuracy": float((predicted[in_scope] == lead_true[in_scope]).mean())
        if in_scope.any()
        else None,
        "out_of_scope_recall": float((predicted[out_of_scope] == -1).mean()) if out_of_scope.any() else None,
        "in_scope_rows": int(in_scope.sum()),
        "out_of_scope_rows": int(out_of_scope.sum()),
    }


def single_label_f1(lead_true: np.ndarray, predicted: np.ndarray, labels: tuple[str, ...]) -> dict[str, Any]:
    """NLBSE: micro F1 (equal to accuracy for single-label data) and macro F1 over the classes."""
    k = len(labels)
    y_true = np.eye(k, dtype=np.int8)[np.asarray(lead_true)]
    y_pred = np.zeros_like(y_true)
    valid = np.asarray(predicted) >= 0
    y_pred[valid] = np.eye(k, dtype=np.int8)[np.asarray(predicted)[valid]]
    return {
        "micro_f1": micro_f1(y_true, y_pred),
        "macro_f1": macro_f1(y_true, y_pred),
        "per_label": per_label(y_true, y_pred, labels),
    }
