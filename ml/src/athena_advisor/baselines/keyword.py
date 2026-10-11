"""Keyword baseline (StackSample only): a specialist is predicted when the text names one of its tags.

Every tag in configs/tag_map.yaml is searched for in the input text as a whole word, ignoring case. The
matched tags are then labelled with the same rules as the gold labels (team = all their specialists,
lead = most specific tags, ties by the priority order). This shows how far simple word matching gets.

Rows that name no tag get an empty team and the train lead frequencies as their lead distribution.
It does not apply to the benchmarks: their labels (intents, issue types) are not specialists.
"""

import re
from typing import Self

import numpy as np

from athena_advisor.baselines.base import Baseline, NotApplicable, normalise
from athena_advisor.data.labels import TagMap, load_tag_map
from athena_advisor.eval.data import LabelledSplit

STACKSAMPLE = "stacksample"
# A tag counts as a whole word when no letter, digit or underscore touches it on either side, so "c#",
# "node.js" and "python-3.x" match as written while "react" does not match inside "reactive".
_EDGE = "A-Za-z0-9_"


def tag_pattern(tags: list[str]) -> re.Pattern[str]:
    # Longest first, so "c++" and "c#" are tried before "c".
    alternatives = "|".join(re.escape(tag) for tag in sorted(tags, key=len, reverse=True))
    return re.compile(rf"(?<![{_EDGE}])(?:{alternatives})(?![{_EDGE}])", re.IGNORECASE)


class KeywordBaseline(Baseline):
    name = "keyword"

    def __init__(self, tag_map_path: str = "configs/tag_map.yaml") -> None:
        self.tag_map: TagMap = load_tag_map(tag_map_path)
        self.pattern = tag_pattern(list(self.tag_map.entries))

    def applies_to(self, dataset: str) -> None:
        if dataset != STACKSAMPLE:
            raise NotApplicable(
                f"keyword baseline skipped for {dataset}: its labels are not specialists, so the tag map "
                "does not apply"
            )

    def matched_tags(self, text: str) -> list[str]:
        return [m.group(0).lower() for m in self.pattern.finditer(text)]

    def fit(self, train: LabelledSplit, seed: int = 0) -> Self:
        self.labels = train.labels
        leads = np.bincount(train.lead[train.has_lead], minlength=len(train.labels)).astype(float)
        self.fallback_lead = normalise(leads[None, :])[0]
        return self

    def predict_probs(self, texts: list[str]) -> tuple[np.ndarray, np.ndarray]:
        index = {label: i for i, label in enumerate(self.labels)}
        team = np.zeros((len(texts), len(self.labels)))
        lead = np.tile(self.fallback_lead, (len(texts), 1))
        for row, text in enumerate(texts):
            label = self.tag_map.label(self.matched_tags(text))
            if label is None:
                continue
            for specialist in label.team:
                team[row, index[specialist]] = 1.0
            lead[row] = 0.0
            lead[row, index[label.lead]] = 1.0
        return team, lead
