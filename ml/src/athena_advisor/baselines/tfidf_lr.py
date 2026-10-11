"""TF-IDF + logistic regression: the standard strong linear baseline.

Text becomes TF-IDF weights over words and word pairs (1-2 grams).
- Multi-label data (StackSample teams, MixATIS, MixSNIPS): one-vs-rest, one binary logistic regression per
  label. A label that is always or never present in train gets that constant probability instead.
- Lead (and the whole prediction on single-label data, CLINC150 and NLBSE): one multinomial logistic
  regression over the labels, trained on the rows that have a lead.
"""

from typing import Self

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from athena_advisor.baselines.base import Baseline, is_single_label
from athena_advisor.eval.data import LabelledSplit


class TfidfLogisticBaseline(Baseline):
    name = "tfidf_lr"

    def __init__(
        self, min_df: int = 2, max_features: int = 200_000, c: float = 4.0, max_iter: int = 1000
    ) -> None:
        self.min_df = min_df
        self.max_features = max_features
        self.c = c
        self.max_iter = max_iter

    def _classifier(self, seed: int) -> LogisticRegression:
        return LogisticRegression(C=self.c, max_iter=self.max_iter, random_state=seed)

    def fit(self, train: LabelledSplit, seed: int = 0) -> Self:
        self.k = len(train.labels)
        self.single_label = is_single_label(train)
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2), min_df=self.min_df, max_features=self.max_features, sublinear_tf=True
        )
        features = self.vectorizer.fit_transform(train.texts)

        # One binary classifier per label (skipped on single-label data, where the lead model covers it).
        self.team_models: list[LogisticRegression | float] = []
        if not self.single_label:
            for column in train.team.T:
                if column.min() == column.max():
                    self.team_models.append(float(column[0]))
                else:
                    self.team_models.append(self._classifier(seed).fit(features, column))

        # Multinomial classifier for the lead.
        rows = train.has_lead
        classes = np.unique(train.lead[rows])
        if len(classes) >= 2:
            self.lead_model: LogisticRegression | int | None = self._classifier(seed).fit(
                features[rows], train.lead[rows]
            )
        else:
            self.lead_model = int(classes[0]) if len(classes) == 1 else None
        return self

    def _lead_probs(self, features) -> np.ndarray:  # type: ignore[no-untyped-def]
        n = features.shape[0]
        probs = np.zeros((n, self.k))
        if isinstance(self.lead_model, LogisticRegression):
            # The model only knows the classes it saw; put each in its label column.
            probs[:, self.lead_model.classes_] = self.lead_model.predict_proba(features)
        elif isinstance(self.lead_model, int):
            probs[:, self.lead_model] = 1.0
        return probs

    def predict_probs(self, texts: list[str]) -> tuple[np.ndarray, np.ndarray]:
        features = self.vectorizer.transform(texts)
        lead = self._lead_probs(features)
        if self.single_label:
            return lead, lead
        team = np.column_stack(
            [
                np.full(features.shape[0], model)
                if isinstance(model, float)
                else model.predict_proba(features)[:, 1]
                for model in self.team_models
            ]
        )
        if self.lead_model is None:
            # No row in train has a lead (for example only multi-intent rows): rank by team probability.
            lead = team
        return team, lead
