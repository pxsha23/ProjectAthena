"""Labelled splits as arrays, for StackSample and every benchmark alike.

ids           (n,)   string ids
texts         (n,)   model input
team          (n, K) 0/1, one column per label in `labels`
lead          (n,)   index of the lead label, or -1 when the row has none
out_of_scope  (n,)   True only for CLINC150 out-of-scope rows
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from athena_advisor.config import SPECIALISTS


@dataclass(frozen=True)
class LabelledSplit:
    ids: np.ndarray
    texts: list[str]
    labels: tuple[str, ...]
    team: np.ndarray
    lead: np.ndarray
    out_of_scope: np.ndarray
    context: np.ndarray | None = None

    def __len__(self) -> int:
        return len(self.ids)

    @property
    def has_lead(self) -> np.ndarray:
        return self.lead >= 0


def from_frame(frame: pd.DataFrame, labels: tuple[str, ...] | list[str]) -> LabelledSplit:
    """Builds a split from a StackSample frame (team, lead) or a benchmark frame (labels, lead,
    out_of_scope)."""
    labels = tuple(labels)
    index = {label: i for i, label in enumerate(labels)}
    label_column = "team" if "team" in frame.columns else "labels"
    team = np.zeros((len(frame), len(labels)), dtype=np.int8)
    for row, row_labels in enumerate(frame[label_column]):
        for label in row_labels:
            if label not in index:
                raise ValueError(f"Label {label!r} is not in the label list")
            team[row, index[label]] = 1
    lead = np.array([index[x] if isinstance(x, str) else -1 for x in frame["lead"]], dtype=np.int64)
    out_of_scope = (
        frame["out_of_scope"].to_numpy(dtype=bool)
        if "out_of_scope" in frame.columns
        else np.zeros(len(frame), bool)
    )
    context = (
        np.stack(frame["context"].to_numpy()).astype(np.float32)
        if "context" in frame.columns and len(frame)
        else None
    )
    return LabelledSplit(
        ids=frame["id"].astype(str).to_numpy(),
        texts=frame["text"].tolist(),
        labels=labels,
        team=team,
        lead=lead,
        out_of_scope=out_of_scope,
        context=context,
    )


def subset(split: LabelledSplit, rows: np.ndarray) -> LabelledSplit:
    """The same split restricted to the given row indices (in that order)."""
    return LabelledSplit(
        ids=split.ids[rows],
        texts=[split.texts[i] for i in rows],
        labels=split.labels,
        team=split.team[rows],
        lead=split.lead[rows],
        out_of_scope=split.out_of_scope[rows],
        context=split.context[rows] if split.context is not None else None,
    )


def label_names(frames: list[pd.DataFrame]) -> tuple[str, ...]:
    """The label columns for a dataset.

    StackSample uses the fixed specialist order. A benchmark uses every label in any of its splits, sorted:
    the label set is part of the task definition, and a label that only occurs in test must still have a
    column (models then predict it with a constant 0 probability).
    """
    if "team" in frames[0].columns:
        return tuple(SPECIALISTS)
    return tuple(sorted({label for frame in frames for row in frame["labels"] for label in row}))


def load_split(folder: str | Path, split: str, labels: tuple[str, ...] | None = None) -> LabelledSplit:
    """Reads <folder>/<split>.parquet with the dataset's label columns (computed when not given)."""
    folder = Path(folder)
    if labels is None:
        labels = label_names([pd.read_parquet(path) for path in sorted(folder.glob("*.parquet"))])
    return from_frame(pd.read_parquet(folder / f"{split}.parquet"), labels)
