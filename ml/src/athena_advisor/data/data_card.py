"""Writes DATA_CARD.md for a built dataset: where the data comes from, its licence, how it was filtered and
labelled, and what the splits contain. It reads only the build output, never the raw files."""

import json
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from athena_advisor.config import SPECIALISTS, SPLITS
from athena_advisor.data.build import load_split
from athena_advisor.paths import resolve

# Recorded word for word from the Kaggle dataset page (via its public metadata) on 2026-10-11.
SOURCE = {
    "name": "StackSample: 10% of Stack Overflow Q&A",
    "url": "https://www.kaggle.com/datasets/stackoverflow/stacksample",
    "kaggle_licence_field": "Other (specified in description)",
    "licence_text": (
        "All Stack Overflow user contributions are licensed under "
        "[CC-BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) with "
        "[attribution required](http://blog.stackoverflow.com/2009/06/attribution-required/)."
    ),
    "retrieved": "2026-10-11",
}


def write_data_card(out_dir: str | Path) -> Path:
    out_dir = resolve(out_dir)
    info = json.loads((out_dir / "build_info.json").read_text(encoding="utf-8"))
    frames = {split: load_split(out_dir, split) for split in SPLITS}
    everything = pd.concat(frames.values(), ignore_index=True)
    tag_map = yaml.safe_load(resolve(info["tag_map"]["path"]).read_text(encoding="utf-8"))

    lines = [
        "# Data card: Athena Advisor training data (StackSample)",
        "",
        "## Source and licence",
        "",
        f"- Dataset: [{SOURCE['name']}]({SOURCE['url']})",
        f'- Licence field on Kaggle: "{SOURCE["kaggle_licence_field"]}"',
        f"- Licence text in the dataset description (retrieved {SOURCE['retrieved']}): "
        f"{SOURCE['licence_text']}",
        "- Use in Athena: question titles and bodies are model input; human-written tags become labels.",
        "",
        "## Filters and labels",
        "",
        "- Labels come only from the question's tags, through the fixed tag map below. Tags are never input.",
        "- Team: every specialist that at least one of the question's tags maps to.",
        "- Lead: the specialist with the most specific (non-generic) mapped tags; generic tags count only "
        "when there is no specific one; ties go to the first in the priority order "
        f"{', '.join(tag_map['priority'])}.",
        "- Questions with no mapped tag are dropped.",
        f"- Input text: title plus the first {info['data_config']['body_prose_words']} words of the "
        "body prose, with HTML, code blocks and inline code removed.",
        "- Splits are chronological by CreationDate (older questions train, newer ones evaluate).",
        f"- The train split is sampled down to at most {info['data_config']['train_max']} questions "
        f"(seed {info['data_config']['sample_seed']}); val_tune, val_cal and test are complete.",
        "",
        "## Counts",
        "",
        f"- Questions read: {info['questions_read']}",
        f"- Kept (at least one mapped tag): {info['questions_kept']} ({info['kept_share']:.1%})",
        f"- Dropped (no mapped tag): {info['dropped_no_mapped_tag']}",
        "",
        _table(
            ["Split", "Starts on", "Kept", "In file", "SHA-256"],
            [
                [
                    split,
                    (info["split_starts"].get(split) or "-")[:10] if split != "train" else "(oldest)",
                    info["split_counts_before_sampling"][split],
                    info["split_counts"][split],
                    f"`{info['files'][split]['sha256'][:16]}...`",
                ]
                for split in SPLITS
            ],
        ),
        "",
        "### Questions per specialist (in the team)",
        "",
        _table(
            ["Specialist", *SPLITS],
            [[s, *(_in_team(frames[split], s) for split in SPLITS)] for s in SPECIALISTS],
        ),
        "",
        "### Questions per lead",
        "",
        _table(
            ["Lead", *SPLITS],
            [[s, *(int((frames[split]["lead"] == s).sum()) for split in SPLITS)] for s in SPECIALISTS],
        ),
        "",
        "### Label co-occurrence (all splits)",
        "",
        "Questions whose team contains both specialists. The diagonal is the total for that specialist.",
        "",
        _table(["", *SPECIALISTS], _cooccurrence(everything)),
        "",
        "### Team size (all splits)",
        "",
        _table(
            ["Specialists in team", "Questions"],
            sorted(everything["team"].map(len).value_counts().items()),
        ),
        "",
        "## Context features",
        "",
        f"Schema version {info['context_schema_version']}, {info['context_dim']} values per question. "
        "Share of questions (all splits) where each value is 1; code_ratio shows the mean.",
        "",
        _table(["Feature", "Rate"], _feature_rates(everything, info["context_features"])),
        "",
        "## Reproducibility",
        "",
        f"- Tag map SHA-256: `{info['tag_map']['sha256']}` ({info['tag_map']['tags']} tags)",
        *(
            f"- {name}: SHA-256 `{meta['sha256']}`, {meta['bytes']} bytes"
            for name, meta in info["source_files"].items()
        ),
        "",
        "## Tag map",
        "",
        _table(
            ["Tag", "Specialist", "Generic"],
            [[f"`{e['tag']}`", e["specialist"], "yes" if e["generic"] else ""] for e in tag_map["tags"]],
        ),
        "",
    ]
    path = out_dir / "DATA_CARD.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _table(header: list[str], rows: list[list[Any]] | list[tuple[Any, ...]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(out)


def _in_team(frame: pd.DataFrame, specialist: str) -> int:
    return int(frame["team"].map(lambda team: specialist in team).sum())


def _cooccurrence(frame: pd.DataFrame) -> list[list[Any]]:
    counts = {(a, b): 0 for a in SPECIALISTS for b in SPECIALISTS}
    for team in frame["team"]:
        members = list(team)
        for s in members:
            counts[(s, s)] += 1
        for a, b in combinations(members, 2):
            counts[(a, b)] += 1
            counts[(b, a)] += 1
    return [[a, *(counts[(a, b)] for b in SPECIALISTS)] for a in SPECIALISTS]


def _feature_rates(frame: pd.DataFrame, names: list[str]) -> list[list[Any]]:
    if frame.empty:
        return [[name, "-"] for name in names[1:]]
    matrix = np.stack(frame["context"].to_numpy())
    means = matrix.mean(axis=0)
    # Skip position 0 (the present flag), which is 1 for every real question.
    return [[name, f"{means[i]:.3f}"] for i, name in enumerate(names) if i > 0]
