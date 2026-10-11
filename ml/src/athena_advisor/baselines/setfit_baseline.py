"""SetFit baseline: a few-shot sentence-transformer classifier.

SetFit fine-tunes a sentence encoder on pairs of training texts (same label: pull together, different: push
apart), then fits a logistic-regression head on the embeddings. It is designed for few labelled examples, so
it is trained on a small sample of train (baselines.setfit_train_max, default 2000), and reported as a
few-shot baseline rather than a full-data one.

- Multi-label data (StackSample teams, MixATIS, MixSNIPS): one-vs-rest head, one binary classifier per label.
- Single-label data (CLINC150, NLBSE): one multiclass head.
The lead is the label with the highest probability.

The training sample is stratified by the lead label (the label itself on single-label data; rows without a
lead form their own group), so rare labels are still represented.
"""

import tempfile
from typing import Self

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier

from athena_advisor.baselines.base import Baseline, is_single_label, normalise
from athena_advisor.eval.data import LabelledSplit


def stratified_sample(groups: np.ndarray, size: int, seed: int) -> np.ndarray:
    """Row indices of a seeded sample of at most `size` rows, keeping each group's share of the data.

    Every group gets at least one row when there is room, then the rest is shared out in proportion
    (largest remainders first). The result is sorted, so it does not depend on drawing order.
    """
    groups = np.asarray(groups)
    n = len(groups)
    if n <= size:
        return np.arange(n)
    rng = np.random.default_rng(seed)
    names, counts = np.unique(groups, return_counts=True)
    quota = np.minimum(counts, 1) if size >= len(names) else np.zeros_like(counts)
    share = counts / n * (size - quota.sum())
    quota = np.minimum(counts, quota + np.floor(share).astype(int))
    for i in np.argsort(-(share - np.floor(share)), kind="stable"):
        if quota.sum() >= size:
            break
        if quota[i] < counts[i]:
            quota[i] += 1
    chosen = [
        rng.choice(np.flatnonzero(groups == name), size=q, replace=False)
        for name, q in zip(names, quota, strict=True)
    ]
    return np.sort(np.concatenate(chosen))


def has_contrastive_pairs(label_sets: np.ndarray) -> bool:
    """True when the sample has at least one pair of rows sharing a label and one pair sharing none."""
    shared = (label_sets.astype(int) @ label_sets.T.astype(int)) > 0
    upper = np.triu_indices(len(label_sets), k=1)
    return bool(shared[upper].any() and (~shared[upper]).any())


class SetFitBaseline(Baseline):
    name = "setfit"

    def __init__(
        self,
        model: str | object = "sentence-transformers/all-MiniLM-L6-v2",
        train_max: int = 2000,
        num_iterations: int = 20,
        epochs: int = 1,
        batch_size: int = 16,
    ) -> None:
        # `model` is a Hugging Face model name or an already built SentenceTransformer (used by the tests).
        self.model_source = model
        self.train_max = train_max
        self.num_iterations = num_iterations
        self.epochs = epochs
        self.batch_size = batch_size

    def _body(self):  # type: ignore[no-untyped-def]
        from sentence_transformers import SentenceTransformer

        if isinstance(self.model_source, str):
            return SentenceTransformer(self.model_source)
        return self.model_source

    def fit(self, train: LabelledSplit, seed: int = 0) -> Self:
        # Imported here: SetFit pulls in PyTorch, which the other baselines never need.
        from datasets import Dataset
        from setfit import SetFitModel, Trainer, TrainingArguments

        self.k = len(train.labels)
        self.single_label = is_single_label(train)
        groups = np.where(train.has_lead, train.lead, -1)
        rows = stratified_sample(groups, self.train_max, seed)
        if self.single_label:
            # Out-of-scope rows (no label) are not a class.
            rows = rows[train.has_lead[rows]]
            labels = train.lead[rows].tolist()
            self.model = SetFitModel(model_body=self._body(), model_head=LogisticRegression(max_iter=1000))
        else:
            labels = train.team[rows].tolist()
            self.model = SetFitModel(
                model_body=self._body(),
                model_head=OneVsRestClassifier(LogisticRegression(max_iter=1000)),
                multi_target_strategy="one-vs-rest",
            )
        self.train_rows = len(rows)
        texts = [train.texts[i] for i in rows]
        sets = np.eye(self.k, dtype=bool)[labels] if self.single_label else np.asarray(labels, dtype=bool)
        self.contrastive = has_contrastive_pairs(sets)
        if not self.contrastive:
            # Tiny samples can have no "same label" or no "different label" pair, and SetFit's pair sampler
            # then fails. Train only the head, on embeddings from the unchanged encoder.
            self.model.model_head.fit(self.model.model_body.encode(texts), labels)
            return self
        dataset = Dataset.from_dict({"text": texts, "label": labels})
        with tempfile.TemporaryDirectory() as output_dir:
            args = TrainingArguments(
                output_dir=output_dir,
                batch_size=self.batch_size,
                num_epochs=self.epochs,
                num_iterations=self.num_iterations,
                seed=seed,
                save_strategy="no",
                report_to="none",
                show_progress_bar=False,
            )
            Trainer(model=self.model, args=args, train_dataset=dataset).train()
        return self

    def predict_probs(self, texts: list[str]) -> tuple[np.ndarray, np.ndarray]:
        raw = self.model.predict_proba(texts)
        probs = raw.detach().cpu().numpy() if hasattr(raw, "detach") else np.asarray(raw)
        if self.single_label:
            # The head only knows the classes it saw in the sample; put each in its label column.
            lead = np.zeros((len(texts), self.k))
            lead[:, self.model.model_head.classes_] = probs
            return lead, lead
        team = probs.reshape(len(texts), self.k)
        # Lead = the label with the highest probability.
        return team, normalise(team)
