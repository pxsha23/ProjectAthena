"""Prior baseline: ignores the text and predicts the label frequencies seen in train, for every row.

Any model worth reporting must beat this.
"""

from typing import Self

import numpy as np

from athena_advisor.baselines.base import Baseline, is_single_label, normalise
from athena_advisor.eval.data import LabelledSplit


class PriorBaseline(Baseline):
    name = "prior"

    def fit(self, train: LabelledSplit, seed: int = 0) -> Self:
        # Team: how often each label is in a row's team.
        team = train.team.mean(axis=0)
        # Lead: how often each label leads, among rows that have a lead. Without any, the team shares.
        leads = np.bincount(train.lead[train.has_lead], minlength=len(train.labels)).astype(float)
        lead = normalise(leads[None, :] if leads.sum() else team[None, :])[0]
        # Single-label data: the team is just the one label, so both heads share one distribution.
        self.team = lead if is_single_label(train) else team
        self.lead = lead
        return self

    def predict_probs(self, texts: list[str]) -> tuple[np.ndarray, np.ndarray]:
        n = len(texts)
        return np.tile(self.team, (n, 1)), np.tile(self.lead, (n, 1))
