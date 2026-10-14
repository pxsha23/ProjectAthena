"""Where each dataset lives and how its splits are loaded, shared by the baselines and the trainer.

Evaluation splits are val_tune, val_cal and test for every dataset:
- StackSample has them already.
- A benchmark has one official dev split. It is cut into val_tune and val_cal halves with the fixed
  benchmarks seed, so every model and seed sees the same halves.
"""

from pathlib import Path

import numpy as np

from athena_advisor.config import AdvisorConfig
from athena_advisor.eval.data import LabelledSplit, load_split, subset
from athena_advisor.paths import resolve

DATASETS = ("stacksample", "mixatis", "mixsnips", "clinc150", "nlbse")
EVAL_SPLITS = ("val_tune", "val_cal", "test")
# Multi-label datasets predict a team (any number of labels); single-label ones exactly one label.
MODES = {
    "stacksample": "multilabel",
    "mixatis": "multilabel",
    "mixsnips": "multilabel",
    "clinc150": "singlelabel",
    "nlbse": "singlelabel",
}


def dataset_folder(config: AdvisorConfig, dataset: str) -> Path:
    if dataset == "stacksample":
        return resolve(config.data.processed_dir) / "stacksample"
    if dataset in DATASETS:
        return resolve(config.benchmarks.processed_dir) / dataset
    raise ValueError(f"Unknown dataset {dataset!r}; choose from {DATASETS}")


def load_dataset(config: AdvisorConfig, dataset: str) -> dict[str, LabelledSplit]:
    folder = dataset_folder(config, dataset)
    if not (folder / "train.parquet").is_file():
        raise FileNotFoundError(f"{folder} has no train.parquet: build the data first")
    train = load_split(folder, "train")
    splits = {"train": train}
    if dataset == "stacksample":
        for split in EVAL_SPLITS:
            splits[split] = load_split(folder, split, train.labels)
        return splits
    dev = load_split(folder, "dev", train.labels)
    order = np.random.default_rng(config.benchmarks.seed).permutation(len(dev))
    half = len(dev) // 2
    splits["val_tune"] = subset(dev, np.sort(order[:half]))
    splits["val_cal"] = subset(dev, np.sort(order[half:]))
    splits["test"] = load_split(folder, "test", train.labels)
    return splits
