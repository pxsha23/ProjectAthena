"""The metrics recorded for one predictions file, chosen by dataset."""

from typing import Any

import numpy as np

from athena_advisor.decide.simple import RULES
from athena_advisor.eval import metrics as m
from athena_advisor.eval.data import LabelledSplit
from athena_advisor.eval.predictions import Predictions

MULTI_INTENT = ("mixatis", "mixsnips")


def dataset_metrics(
    dataset: str, gold: LabelledSplit, predictions: Predictions, threshold: float
) -> dict[str, Any]:
    """Team and lead metrics at a fixed threshold, the dataset's own metrics, the two simple decision
    rules, and latency. The cost-aware decision layer is evaluated separately from the same files."""
    predictions = predictions.aligned_to(gold.ids)
    if predictions.labels != gold.labels:
        raise ValueError("Predictions and gold use different label lists")
    team, lead = predictions.team_probs, predictions.lead_probs
    y_pred = m.threshold(team, threshold)
    result: dict[str, Any] = {
        "threshold": threshold,
        **m.multilabel_report(gold.team, team, gold.lead, lead, gold.labels, y_pred),
    }
    if dataset in MULTI_INTENT:
        result["intent_accuracy"] = m.intent_accuracy(gold.team, y_pred)
    if dataset == "clinc150":
        # No out-of-scope threshold is chosen here, so nothing is predicted out of scope (recall 0).
        result["clinc"] = m.clinc_metrics(gold.lead, gold.out_of_scope, m.single_label_predictions(lead))
    if dataset == "nlbse":
        result["nlbse"] = m.single_label_f1(gold.lead, m.single_label_predictions(lead), gold.labels)
    result["decision_rules"] = {
        name: {
            "micro_f1": m.micro_f1(gold.team, decision.active),
            "lead_accuracy": float((decision.lead[gold.has_lead] == gold.lead[gold.has_lead]).mean())
            if gold.has_lead.any()
            else None,
            "mean_team_size": float(decision.active.sum(axis=1).mean()),
        }
        for name, decision in ((name, rule(predictions)) for name, rule in RULES.items())
    }
    latency = predictions.latency_ms
    result["latency_ms"] = {
        "mean": float(latency.mean()) if len(latency) else None,
        "p50": float(np.percentile(latency, 50)) if len(latency) else None,
        "p95": float(np.percentile(latency, 95)) if len(latency) else None,
    }
    return result
