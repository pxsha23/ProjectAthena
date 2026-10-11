"""Labels from human-written Stack Overflow tags, through the fixed table in configs/tag_map.yaml.

Step 1 (team): every tag that appears in the table adds its specialist to the team.
Step 2 (lead): the specialist with the most specific (non-generic) mapped tags leads. When a question has
only generic tags (for example just "python"), those are counted instead. Ties go to the specialist that
comes first in the table's priority order.
Questions with no mapped tag get no label and are dropped. Tags are only ever used here, never as input.
"""

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import yaml

from athena_advisor.config import SPECIALISTS
from athena_advisor.paths import resolve
from athena_advisor.run_metadata import file_sha256


@dataclass(frozen=True)
class TagEntry:
    specialist: str
    generic: bool


@dataclass(frozen=True)
class Label:
    team: tuple[str, ...]  # in the fixed SPECIALISTS order
    lead: str


@dataclass(frozen=True)
class TagMap:
    entries: dict[str, TagEntry]
    priority: tuple[str, ...]
    sha256: str

    def label(self, tags: list[str]) -> Label | None:
        """The team and lead for one question's tags, or None when no tag is mapped."""
        mapped = [self.entries[t] for t in dict.fromkeys(tags) if t in self.entries]
        if not mapped:
            return None
        team = tuple(s for s in SPECIALISTS if any(e.specialist == s for e in mapped))
        specific = Counter(e.specialist for e in mapped if not e.generic)
        counts = specific or Counter(e.specialist for e in mapped)
        best = max(counts.values())
        lead = next(s for s in self.priority if counts.get(s, 0) == best)
        return Label(team=team, lead=lead)


def load_tag_map(path: str | Path) -> TagMap:
    path = resolve(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    priority = tuple(data["priority"])
    if sorted(priority) != sorted(SPECIALISTS):
        raise ValueError(f"priority must list each of {SPECIALISTS} exactly once")
    entries: dict[str, TagEntry] = {}
    for row in data["tags"]:
        tag, specialist, generic = row["tag"], row["specialist"], row["generic"]
        if specialist not in SPECIALISTS:
            raise ValueError(f"Tag {tag!r} maps to unknown specialist {specialist!r}")
        if not isinstance(generic, bool):
            raise ValueError(f"Tag {tag!r}: generic must be true or false")
        if tag in entries:
            raise ValueError(f"Tag {tag!r} appears twice")
        entries[str(tag)] = TagEntry(specialist=specialist, generic=generic)
    return TagMap(entries=entries, priority=priority, sha256=file_sha256(path))
