"""Builds the StackSample splits: one parquet file per split, each with a SHA-256 file, plus build_info.json.

Two passes over the CSV files, read in chunks so the full dataset never has to fit in memory at once:
1. Read Id and CreationDate only, label every question from its tags, drop the ones with no mapped tag,
   and cut the kept questions into chronological splits (older questions train, newer ones evaluate,
   so the model is never tested on questions from before the ones it learned from).
2. Read Title and Body only for the selected questions and write text, context vector, team and lead.
The output is sorted by (CreationDate, Id), so the same input and config always give the same files.
"""

import json
from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from athena_advisor.config import SPLITS, AdvisorConfig
from athena_advisor.data.context import CONTEXT_DIM, CONTEXT_SCHEMA_VERSION, FEATURE_NAMES, ContextSchema
from athena_advisor.data.labels import Label, TagMap, load_tag_map
from athena_advisor.data.text import build_text
from athena_advisor.paths import resolve
from athena_advisor.run_metadata import file_sha256

QUESTIONS_FILE = "Questions.csv"
TAGS_FILE = "Tags.csv"

SCHEMA = pa.schema(
    [
        ("id", pa.int64()),
        ("creation_date", pa.timestamp("s", tz="UTC")),
        ("text", pa.string()),
        ("context", pa.list_(pa.float32(), CONTEXT_DIM)),
        ("team", pa.list_(pa.string())),
        ("lead", pa.string()),
    ]
)


def build(config: AdvisorConfig, raw_dir: str | Path, out_dir: str | Path) -> dict[str, Any]:
    """Runs both passes and returns build_info (also written to out_dir/build_info.json)."""
    data = config.data
    _check_fractions(data.split_fractions)
    raw_dir, out_dir = resolve(raw_dir), resolve(out_dir)
    questions_path, tags_path = raw_dir / QUESTIONS_FILE, raw_dir / TAGS_FILE
    tag_map = load_tag_map(data.tag_map)

    # ---- pass 1: ids, dates and labels only
    tags = _read_tags(tags_path, data.csv_encoding, data.chunk_size)
    kept_ids: list[int] = []
    kept_dates: list[pd.Timestamp] = []
    labels: dict[int, Label] = {}
    read = 0
    for chunk in _read_questions(questions_path, ["Id", "CreationDate"], data):
        for qid, created in zip(chunk["Id"].tolist(), chunk["CreationDate"].tolist(), strict=True):
            read += 1
            label = tag_map.label(tags.get(qid, []))
            if label is None:
                continue
            kept_ids.append(qid)
            kept_dates.append(created)
            labels[qid] = label
    del tags

    dates = pd.to_datetime(pd.Series(kept_dates, dtype="object"), utc=True)
    boundaries = _boundaries(dates, data.split_fractions)
    split_of = _assign_splits(dates, boundaries)
    by_split: dict[str, list[int]] = {s: [] for s in SPLITS}
    for qid, split in zip(kept_ids, split_of, strict=True):
        by_split[split].append(qid)
    counts_before_sampling = {s: len(ids) for s, ids in by_split.items()}

    # Train is sampled down with a fixed seed; validation and test stay complete.
    if data.train_max is not None and len(by_split["train"]) > data.train_max:
        rng = np.random.default_rng(data.sample_seed)
        train = np.sort(np.asarray(by_split["train"], dtype=np.int64))
        by_split["train"] = sorted(rng.choice(train, size=data.train_max, replace=False).tolist())
    selected = {qid: split for split, ids in by_split.items() for qid in ids}

    # ---- pass 2: text and context for the selected questions only
    rows: dict[str, dict[str, list[Any]]] = {s: {name: [] for name in SCHEMA.names} for s in SPLITS}
    for chunk in _read_questions(questions_path, ["Id", "CreationDate", "Title", "Body"], data):
        for qid, created, title, body in chunk.itertuples(index=False, name=None):
            split = selected.get(qid)
            if split is None:
                continue
            label = labels[qid]
            out = rows[split]
            out["id"].append(qid)
            out["creation_date"].append(created)
            # Only the title and body are passed on: tags can never leak into the model input.
            out["text"].append(build_text(_str(title), _str(body), data.body_prose_words))
            out["context"].append(ContextSchema.from_stackoverflow_body(_str(body)).encode())
            out["team"].append(list(label.team))
            out["lead"].append(label.lead)

    out_dir.mkdir(parents=True, exist_ok=True)
    files = {split: _write_split(rows[split], out_dir / f"{split}.parquet") for split in SPLITS}

    info: dict[str, Any] = {
        "context_schema_version": CONTEXT_SCHEMA_VERSION,
        "context_dim": CONTEXT_DIM,
        "context_features": list(FEATURE_NAMES),
        "tag_map": {"path": data.tag_map, "sha256": tag_map.sha256, "tags": len(tag_map.entries)},
        "source_files": {
            name: {"sha256": file_sha256(path), "bytes": path.stat().st_size}
            for name, path in ((QUESTIONS_FILE, questions_path), (TAGS_FILE, tags_path))
        },
        "data_config": asdict(data),
        "questions_read": read,
        "questions_kept": len(kept_ids),
        "dropped_no_mapped_tag": read - len(kept_ids),
        "kept_share": round(len(kept_ids) / read, 4) if read else 0.0,
        "split_starts": {
            split: (b.isoformat() if b is not None else None)
            for split, b in zip(SPLITS[1:], boundaries, strict=True)
        },
        "split_counts_before_sampling": counts_before_sampling,
        "split_counts": {split: files[split]["rows"] for split in SPLITS},
        "files": files,
    }
    (out_dir / "build_info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    return info


def load_split(out_dir: str | Path, split: str) -> pd.DataFrame:
    return pd.read_parquet(resolve(out_dir) / f"{split}.parquet")


# ---------------------------------------------------------------- helpers


def _str(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _check_fractions(fractions: list[float]) -> None:
    if len(fractions) != len(SPLITS) or any(f < 0 for f in fractions) or abs(sum(fractions) - 1) > 1e-6:
        raise ValueError(f"split_fractions must be {len(SPLITS)} non-negative numbers that sum to 1")


def _read_tags(path: Path, encoding: str, chunk_size: int) -> dict[int, list[str]]:
    tags: dict[int, list[str]] = {}
    for chunk in pd.read_csv(
        path, encoding=encoding, chunksize=chunk_size, dtype={"Id": "int64", "Tag": "str"}
    ):
        for qid, tag in zip(chunk["Id"].tolist(), chunk["Tag"].tolist(), strict=True):
            if isinstance(tag, str):
                tags.setdefault(qid, []).append(tag)
    return tags


def _read_questions(path: Path, columns: list[str], data: Any) -> Iterator[pd.DataFrame]:
    """Yields chunks of the requested columns, stopping after data.sample_size questions if it is set."""
    remaining = data.sample_size
    reader = pd.read_csv(
        path, encoding=data.csv_encoding, chunksize=data.chunk_size, usecols=columns, dtype={"Id": "int64"}
    )
    for chunk in reader:
        chunk = chunk[columns]
        if remaining is not None:
            if remaining <= 0:
                break
            chunk = chunk.iloc[:remaining]
            remaining -= len(chunk)
        yield chunk


def _boundaries(dates: pd.Series, fractions: list[float]) -> list[pd.Timestamp | None]:
    """Start date of each split after train: the date at the cumulative fraction of the sorted questions.

    A question belongs to the latest split whose start date is on or before its own date. Questions that
    share a timestamp therefore always land in the same split.
    """
    ordered = dates.sort_values().reset_index(drop=True)
    n = len(ordered)
    starts: list[pd.Timestamp | None] = []
    cumulative = 0.0
    for fraction in fractions[:-1]:
        cumulative += fraction
        index = int(round(cumulative * n))
        starts.append(ordered.iloc[index] if index < n else None)
    return starts


def _assign_splits(dates: pd.Series, starts: list[pd.Timestamp | None]) -> list[str]:
    result = []
    for date in dates:
        position = 0
        for i, start in enumerate(starts):
            if start is not None and date >= start:
                position = i + 1
        result.append(SPLITS[position])
    return result


def _write_split(columns: dict[str, list[Any]], path: Path) -> dict[str, Any]:
    frame = pd.DataFrame(
        {
            "id": pd.Series(columns["id"], dtype="int64"),
            "creation_date": pd.to_datetime(pd.Series(columns["creation_date"], dtype="object"), utc=True),
        }
    )
    # Sorting by date and then id makes the file byte-for-byte reproducible.
    order = frame.sort_values(["creation_date", "id"], kind="mergesort").index.to_numpy()
    table = pa.table(
        {
            "id": pa.array(frame["id"].to_numpy()[order], pa.int64()),
            "creation_date": pa.array(
                frame["creation_date"].iloc[order].dt.floor("s"), pa.timestamp("s", tz="UTC")
            ),
            "text": pa.array([columns["text"][i] for i in order], pa.string()),
            "context": pa.array(
                [columns["context"][i].tolist() for i in order], pa.list_(pa.float32(), CONTEXT_DIM)
            ),
            "team": pa.array([columns["team"][i] for i in order], pa.list_(pa.string())),
            "lead": pa.array([columns["lead"][i] for i in order], pa.string()),
        },
        schema=SCHEMA,
    )
    pq.write_table(table, path, compression="zstd")
    digest = file_sha256(path)
    path.with_name(path.name + ".sha256").write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    return {"file": path.name, "sha256": digest, "rows": table.num_rows}


def tag_map_of(config: AdvisorConfig) -> TagMap:
    return load_tag_map(config.data.tag_map)
