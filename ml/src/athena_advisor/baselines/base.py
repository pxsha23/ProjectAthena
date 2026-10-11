"""The interface every baseline (and later the Advisor model) follows: fit on train, predict any split.

predict() returns the saved Predictions format, so baselines and the real model are scored by exactly the
same code. Latency is measured around the batch call and spread evenly over its rows.
"""

import time
from abc import ABC, abstractmethod
from typing import Self

import numpy as np

from athena_advisor.eval.data import LabelledSplit
from athena_advisor.eval.predictions import Predictions


class NotApplicable(Exception):
    """The baseline makes no sense for this dataset (the reason is the message)."""


def is_single_label(split: LabelledSplit) -> bool:
    """CLINC150 and NLBSE: every row has at most one label, so team and lead are the same prediction."""
    return bool((split.team.sum(axis=1) <= 1).all())


def normalise(rows: np.ndarray) -> np.ndarray:
    """Rows scaled to sum to 1; an all-zero row becomes uniform."""
    rows = np.asarray(rows, dtype=float)
    totals = rows.sum(axis=1, keepdims=True)
    uniform = np.full_like(rows, 1.0 / rows.shape[1])
    return np.divide(rows, totals, out=uniform, where=totals > 0)


class Baseline(ABC):
    name: str

    def applies_to(self, dataset: str) -> None:  # noqa: B027 (optional hook, applies everywhere by default)
        """Raises NotApplicable when the baseline cannot be used on this dataset."""
        return None

    @abstractmethod
    def fit(self, train: LabelledSplit, seed: int = 0) -> Self: ...

    @abstractmethod
    def predict_probs(self, texts: list[str]) -> tuple[np.ndarray, np.ndarray]:
        """(team_probs, lead_probs) for a batch of texts."""

    def predict(self, split: LabelledSplit, dataset: str, split_name: str, seed: int = 0) -> Predictions:
        self.applies_to(dataset)
        start = time.perf_counter()
        team, lead = self.predict_probs(split.texts)
        elapsed_ms = (time.perf_counter() - start) * 1000
        per_item = elapsed_ms / max(len(split), 1)
        return Predictions(
            ids=split.ids,
            labels=split.labels,
            team_probs=np.clip(team, 0.0, 1.0),
            lead_probs=normalise(lead),
            latency_ms=np.full(len(split), per_item),
            meta={
                "model": self.name,
                "dataset": dataset,
                "split": split_name,
                "seed": seed,
                "latency": "batch time divided evenly over the rows",
            },
        )
