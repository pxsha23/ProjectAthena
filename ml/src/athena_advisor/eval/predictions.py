"""The one saved predictions format: one .npz file per run, dataset, split and seed.

Every later step (calibration, conformal prediction, decisions, metrics) reads only these files, so a model
is run once and never needs to be retrained to try a new decision rule or metric.

    ids          (n,)   string ids, matching the dataset rows
    labels       (K,)   label names, the column order of both probability matrices
    team_probs   (n, K) probability that each label belongs to the row's team / label set
    lead_probs   (n, K) probability distribution over the lead label (rows sum to 1)
    latency_ms   (n,)   time to predict each item, in milliseconds
    meta         JSON   model, dataset, split, seed, and how latency was measured
Stored with allow_pickle=False, so loading a file can never run code.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from athena_advisor.paths import resolve


@dataclass
class Predictions:
    ids: np.ndarray
    labels: tuple[str, ...]
    team_probs: np.ndarray
    lead_probs: np.ndarray
    latency_ms: np.ndarray
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        n, k = len(self.ids), len(self.labels)
        self.ids = np.asarray(self.ids).astype(str)
        self.team_probs = np.asarray(self.team_probs, dtype=np.float32)
        self.lead_probs = np.asarray(self.lead_probs, dtype=np.float32)
        self.latency_ms = np.asarray(self.latency_ms, dtype=np.float32)
        for name, array, shape in (
            ("team_probs", self.team_probs, (n, k)),
            ("lead_probs", self.lead_probs, (n, k)),
            ("latency_ms", self.latency_ms, (n,)),
        ):
            if array.shape != shape:
                raise ValueError(f"{name} has shape {array.shape}, expected {shape}")
        if n and not np.allclose(self.lead_probs.sum(axis=1), 1.0, atol=1e-4):
            raise ValueError("Each row of lead_probs must sum to 1")
        if ((self.team_probs < 0) | (self.team_probs > 1)).any():
            raise ValueError("team_probs must be between 0 and 1")

    def save(self, path: str | Path) -> Path:
        path = resolve(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            path,
            ids=self.ids,
            labels=np.asarray(self.labels, dtype=str),
            team_probs=self.team_probs,
            lead_probs=self.lead_probs,
            latency_ms=self.latency_ms,
            meta=np.asarray(json.dumps(self.meta, sort_keys=True)),
        )
        return path

    @classmethod
    def load(cls, path: str | Path) -> "Predictions":
        with np.load(resolve(path), allow_pickle=False) as data:
            return cls(
                ids=data["ids"],
                labels=tuple(data["labels"].tolist()),
                team_probs=data["team_probs"],
                lead_probs=data["lead_probs"],
                latency_ms=data["latency_ms"],
                meta=json.loads(str(data["meta"])),
            )

    def aligned_to(self, ids: np.ndarray) -> "Predictions":
        """The same predictions reordered to match `ids` (for example the gold split's row order)."""
        position = {item: i for i, item in enumerate(self.ids.tolist())}
        missing = [item for item in np.asarray(ids).astype(str).tolist() if item not in position]
        if missing:
            raise ValueError(f"{len(missing)} ids have no prediction, for example {missing[0]!r}")
        order = np.array([position[item] for item in np.asarray(ids).astype(str).tolist()], dtype=np.int64)
        return Predictions(
            ids=self.ids[order],
            labels=self.labels,
            team_probs=self.team_probs[order],
            lead_probs=self.lead_probs[order],
            latency_ms=self.latency_ms[order],
            meta=self.meta,
        )


def predictions_path(results_dir: str | Path, model: str, dataset: str, split: str, seed: int) -> Path:
    """results/predictions/<model>/<dataset>/<split>/<seed>.npz"""
    return resolve(results_dir) / "predictions" / model / dataset / split / f"{seed}.npz"
