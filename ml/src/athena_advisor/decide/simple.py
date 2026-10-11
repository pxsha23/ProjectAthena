"""Two simple decision rules, used as reference points for the cost-aware decision layer.

Both work on any saved predictions file.
- call_all: every label is active (always calls the whole team: maximum recall, maximum cost).
- top1:     only the single most likely team label is active, and it is also the lead (minimum cost).
"""

from dataclasses import dataclass

import numpy as np

from athena_advisor.eval.predictions import Predictions


@dataclass(frozen=True)
class Decision:
    active: np.ndarray  # (n, K) 0/1: which labels are switched on for each row
    lead: np.ndarray  # (n,) index of the lead label


def call_all(predictions: Predictions) -> Decision:
    n, k = predictions.team_probs.shape
    return Decision(active=np.ones((n, k), dtype=np.int8), lead=predictions.lead_probs.argmax(axis=1))


def top1(predictions: Predictions) -> Decision:
    best = predictions.team_probs.argmax(axis=1)
    active = np.zeros(predictions.team_probs.shape, dtype=np.int8)
    active[np.arange(len(best)), best] = 1
    return Decision(active=active, lead=best)


RULES = {"call_all": call_all, "top1": top1}
