"""NLBSE'22 issue report classification: GitHub issues labelled bug, enhancement or question.

Source: two .tar.gz archives, each holding one CSV with the columns
    (unnamed index), issue_url, issue_label, issue_created_at, issue_author_association,
    repository_url, issue_title, issue_body
The text is the title and body with whitespace collapsed. Official train and test splits; the dev split is
cut from train because there is no official one.

The train file is large (about 720k issues), so it is read in chunks and sampled down in one pass:
every row gets a random number from a seeded generator and the rows with the smallest numbers are kept.
That is a uniform sample, it never holds more than the cap in memory, and the same seed always gives
the same sample.
"""

import heapq
import tarfile
from collections.abc import Iterator
from pathlib import Path
from typing import IO

import numpy as np
import pandas as pd

from athena_advisor.config import BenchmarksConfig
from athena_advisor.data.benchmarks.common import Conversion, Example, make_id

TRAIN_FILE = "github-labels-top3-803k-train.tar.gz"
TEST_FILE = "github-labels-top3-803k-test.tar.gz"
LABELS = ("bug", "enhancement", "question")
COLUMNS = ["issue_label", "issue_title", "issue_body"]
CHUNK_ROWS = 50000


def issue_text(title: object, body: object) -> str:
    parts = [p for p in (title, body) if isinstance(p, str)]
    return " ".join(" ".join(parts).split())


def read_rows(path: Path) -> Iterator[tuple[int, str, str]]:
    """Yields (row number in the file, label, text). Reads a .tar.gz archive or a plain .csv."""
    if path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as archive:
            member = next((m for m in archive.getmembers() if m.name.endswith(".csv")), None)
            if member is None:
                raise ValueError(f"{path} contains no CSV file")
            handle = archive.extractfile(member)
            assert handle is not None
            yield from _rows(handle, path)
    else:
        with path.open("rb") as handle:
            yield from _rows(handle, path)


def _rows(handle: IO[bytes], path: Path) -> Iterator[tuple[int, str, str]]:
    number = 0
    for chunk in pd.read_csv(handle, usecols=COLUMNS, chunksize=CHUNK_ROWS, dtype=str, keep_default_na=False):
        for label, title, body in chunk[COLUMNS].itertuples(index=False, name=None):
            if label not in LABELS:
                raise ValueError(f"{path}: row {number} has unknown label {label!r}")
            yield number, label, issue_text(title, body)
            number += 1


def source_path(raw_dir: Path, name: str) -> Path:
    """The official .tar.gz, or the same file already unpacked as .csv (the test fixtures use this)."""
    archive = raw_dir / name
    unpacked = raw_dir / name.replace(".tar.gz", ".csv")
    return archive if archive.exists() or not unpacked.exists() else unpacked


def convert(raw_dir: Path, config: BenchmarksConfig) -> Conversion:
    train_path, test_path = source_path(raw_dir, TRAIN_FILE), source_path(raw_dir, TEST_FILE)
    rng = np.random.default_rng(config.seed)

    # Train: seeded one-pass sample of at most nlbse_train_max rows (all rows when there is no cap).
    kept: list[tuple[float, int, str, str]] = []
    train_rows = 0
    for number, label, text in read_rows(train_path):
        train_rows += 1
        key = float(rng.random())
        if config.nlbse_train_max is None:
            kept.append((key, number, label, text))
        elif len(kept) < config.nlbse_train_max:
            # A max-heap on the key (stored negated) keeps the smallest keys seen so far.
            heapq.heappush(kept, (-key, number, label, text))
        elif -kept[0][0] > key:
            heapq.heapreplace(kept, (-key, number, label, text))
    pool = sorted((number, label, text) for _, number, label, text in kept)

    # Dev: a seeded random share of the (sampled) official train split.
    order = np.random.default_rng(config.seed + 1).permutation(len(pool))
    dev_count = int(round(len(pool) * config.nlbse_dev_fraction))
    dev_rows = {int(i) for i in order[:dev_count]}

    examples: list[Example] = []
    for position, (number, label, text) in enumerate(pool):
        split = "dev" if position in dev_rows else "train"
        # The id keeps the row number in the official file, so every row can be traced back.
        examples.append(_example(split, number, label, text))
    test_rows = 0
    for number, label, text in read_rows(test_path):
        test_rows += 1
        examples.append(_example("test", number, label, text))

    return Conversion(
        dataset="nlbse",
        examples=examples,
        source_files={train_path.name: train_path, test_path.name: test_path},
        facts={
            "Official train rows": train_rows,
            "Train rows kept after sampling": len(pool),
            "Train cap (nlbse_train_max)": config.nlbse_train_max,
            "Dev fraction of the kept train rows": config.nlbse_dev_fraction,
            "Seed": config.seed,
            "Official test rows (all kept)": test_rows,
        },
    )


def _example(split: str, number: int, label: str, text: str) -> Example:
    return Example(
        id=make_id("nlbse", split, number),
        text=text,
        labels=(label,),
        lead=label,
        out_of_scope=False,
        split=split,
    )
