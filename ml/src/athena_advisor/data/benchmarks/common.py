"""The common benchmark format and its writer.

Every benchmark is converted to the same columns, so evaluation code never needs to know where a row came
from:
    id            "<dataset>-<split>-<6-digit index in the source file>"
    text          the utterance or issue text
    labels        list of gold labels (intents or issue types); empty for out-of-scope rows
    lead          the single gold label, or null when there is none (multi-intent or out-of-scope)
    out_of_scope  true only for CLINC150 out-of-scope rows
    split         train, dev or test
"""

import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from athena_advisor.data.benchmarks.sources import SOURCES
from athena_advisor.run_metadata import file_sha256

BENCHMARK_SPLITS = ("train", "dev", "test")

SCHEMA = pa.schema(
    [
        ("id", pa.string()),
        ("text", pa.string()),
        ("labels", pa.list_(pa.string())),
        ("lead", pa.string()),
        ("out_of_scope", pa.bool_()),
        ("split", pa.string()),
    ]
)


@dataclass(frozen=True)
class Example:
    id: str
    text: str
    labels: tuple[str, ...]
    lead: str | None
    out_of_scope: bool
    split: str

    def __post_init__(self) -> None:
        if self.split not in BENCHMARK_SPLITS:
            raise ValueError(f"Unknown split {self.split!r}")
        if self.out_of_scope and (self.labels or self.lead):
            raise ValueError(f"{self.id}: an out-of-scope example has no labels and no lead")
        if self.lead is not None and self.lead not in self.labels:
            raise ValueError(f"{self.id}: the lead must be one of the labels")


@dataclass
class Conversion:
    """What a converter produced, plus facts for the data card."""

    dataset: str
    examples: list[Example]
    source_files: dict[str, Path]
    facts: dict[str, Any] = field(default_factory=dict)


def make_id(dataset: str, split: str, index: int) -> str:
    return f"{dataset}-{split}-{index:06d}"


def write_benchmark(conversion: Conversion, out_dir: Path) -> dict[str, Any]:
    """Writes <out_dir>/<dataset>/<split>.parquet, a .sha256 file for each, info.json and DATA_CARD.md."""
    folder = out_dir / conversion.dataset
    folder.mkdir(parents=True, exist_ok=True)
    by_split = {s: [e for e in conversion.examples if e.split == s] for s in BENCHMARK_SPLITS}
    _check_integrity(by_split)

    files = {}
    for split, examples in by_split.items():
        examples = sorted(examples, key=lambda e: e.id)
        table = pa.table(
            {
                "id": [e.id for e in examples],
                "text": [e.text for e in examples],
                "labels": [list(e.labels) for e in examples],
                "lead": [e.lead for e in examples],
                "out_of_scope": [e.out_of_scope for e in examples],
                "split": [e.split for e in examples],
            },
            schema=SCHEMA,
        )
        path = folder / f"{split}.parquet"
        pq.write_table(table, path, compression="zstd")
        digest = file_sha256(path)
        path.with_name(path.name + ".sha256").write_text(f"{digest}  {path.name}\n", encoding="utf-8")
        files[split] = {"file": path.name, "sha256": digest, "rows": table.num_rows}

    info = {
        "dataset": conversion.dataset,
        "source_files": {
            name: {"sha256": file_sha256(path), "bytes": path.stat().st_size}
            for name, path in sorted(conversion.source_files.items())
        },
        "files": files,
        "counts": _counts(by_split),
        "facts": conversion.facts,
    }
    (folder / "info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    (folder / "DATA_CARD.md").write_text(_data_card(info), encoding="utf-8")
    return info


def _check_integrity(by_split: dict[str, list[Example]]) -> None:
    """Every id is unique and belongs to exactly one split."""
    seen: dict[str, str] = {}
    for split, examples in by_split.items():
        for e in examples:
            if e.id in seen:
                raise ValueError(f"{e.id} appears in both {seen[e.id]} and {split}")
            seen[e.id] = split


def _counts(by_split: dict[str, list[Example]]) -> dict[str, Any]:
    return {
        split: {
            "rows": len(examples),
            "out_of_scope": sum(e.out_of_scope for e in examples),
            "multi_label": sum(len(e.labels) > 1 for e in examples),
            "labels": dict(sorted(Counter(label for e in examples for label in e.labels).items())),
        }
        for split, examples in by_split.items()
    }


def _data_card(info: dict[str, Any]) -> str:
    source = SOURCES[info["dataset"]]
    counts = info["counts"]
    all_labels = sorted({label for split in counts.values() for label in split["labels"]})
    lines = [
        f"# Data card: {source.name}",
        "",
        "## Source",
        "",
        f"- Homepage: {source.homepage}",
        f"- Version: {source.version}",
        "- Files:",
        *(f"  - `{name}`: {url}" for name, url in source.files.items()),
        "",
        "## Licence",
        "",
        source.licence,
        "",
        "## Citation",
        "",
        "```bibtex",
        source.citation,
        "```",
        "",
        "## Notes",
        "",
        *(f"- {note}" for note in source.notes),
        "",
        "## Counts",
        "",
        "| Split | Rows | Out of scope | More than one label | Distinct labels | SHA-256 |",
        "|---|---|---|---|---|---|",
        *(
            f"| {split} | {c['rows']} | {c['out_of_scope']} | {c['multi_label']} | {len(c['labels'])} | "
            f"`{info['files'][split]['sha256'][:16]}...` |"
            for split, c in counts.items()
        ),
        "",
        f"{len(all_labels)} distinct labels in total.",
    ]
    if info["facts"]:
        lines += ["", "## Conversion", "", *(f"- {key}: {value}" for key, value in info["facts"].items())]
    lines += [
        "",
        "## Source file hashes",
        "",
        *(
            f"- `{name}`: SHA-256 `{meta['sha256']}`, {meta['bytes']} bytes"
            for name, meta in info["source_files"].items()
        ),
        "",
    ]
    return "\n".join(lines)


def label_list(examples: Iterable[Example]) -> list[str]:
    return sorted({label for e in examples for label in e.labels})
