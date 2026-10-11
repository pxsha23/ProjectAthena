"""CLINC150, full version: 150 in-scope intents plus out-of-scope queries.

Source: data_full.json, a JSON object with six lists of [text, intent] pairs:
    train, val, test              in-scope queries
    oos_train, oos_val, oos_test  out-of-scope queries (intent "oos")
The official val split is called dev here.
"""

import json
from pathlib import Path

from athena_advisor.data.benchmarks.common import Conversion, Example, make_id

FILE = "data_full.json"
OOS_LABEL = "oos"
# Source key -> (split, out_of_scope)
KEYS = {
    "train": ("train", False),
    "val": ("dev", False),
    "test": ("test", False),
    "oos_train": ("train", True),
    "oos_val": ("dev", True),
    "oos_test": ("test", True),
}


def convert(raw_dir: Path) -> Conversion:
    path = raw_dir / FILE
    data = json.loads(path.read_text(encoding="utf-8"))
    missing = set(KEYS) - set(data)
    if missing:
        raise ValueError(f"{path} is missing {sorted(missing)}")

    examples: list[Example] = []
    next_index = {"train": 0, "dev": 0, "test": 0}
    for key, (split, out_of_scope) in KEYS.items():
        for text, intent in data[key]:
            if out_of_scope != (intent == OOS_LABEL):
                raise ValueError(f"{path}: {key} has a row labelled {intent!r}")
            index = next_index[split]
            next_index[split] += 1
            examples.append(
                Example(
                    id=make_id("clinc150", split, index),
                    text=" ".join(str(text).split()),
                    # Out-of-scope rows have no label at all, not an "oos" class.
                    labels=() if out_of_scope else (intent,),
                    lead=None if out_of_scope else intent,
                    out_of_scope=out_of_scope,
                    split=split,
                )
            )
    return Conversion(dataset="clinc150", examples=examples, source_files={FILE: path})
