"""MixATIS and MixSNIPS (cleaned, AGIF release): multi-intent utterances.

Source format, one utterance per block:
    token SLOT-TAG        (one line per word)
    ...
    intent_a#intent_b     (all intents of the utterance, joined with "#")
    <blank line>
The text is the tokens joined by spaces. Slot tags are dropped: only the intents are used.
"""

from dataclasses import dataclass
from pathlib import Path

from athena_advisor.data.benchmarks.common import BENCHMARK_SPLITS, Conversion, Example, make_id


@dataclass(frozen=True)
class Utterance:
    tokens: tuple[str, ...]
    intents: tuple[str, ...]


def parse_agif(text: str, source: str = "<text>") -> list[Utterance]:
    utterances: list[Utterance] = []
    tokens: list[str] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            if tokens:
                raise ValueError(f"{source}:{number}: utterance ends without an intent line")
            continue
        parts = line.split()
        if len(parts) == 2:
            tokens.append(parts[0])
        elif len(parts) == 1:
            # The intent line closes the utterance. Multiple intents are joined with "#".
            if not tokens:
                raise ValueError(f"{source}:{number}: intent line without any tokens")
            intents = tuple(i for i in parts[0].split("#") if i)
            if not intents:
                raise ValueError(f"{source}:{number}: empty intent line")
            utterances.append(Utterance(tokens=tuple(tokens), intents=intents))
            tokens = []
        else:
            raise ValueError(f"{source}:{number}: expected 'token TAG' or an intent line, got {line!r}")
    if tokens:
        raise ValueError(f"{source}: file ends in the middle of an utterance")
    return utterances


def convert(dataset: str, raw_dir: Path) -> Conversion:
    """Reads train.txt, dev.txt and test.txt (the official splits) from raw_dir."""
    examples: list[Example] = []
    files: dict[str, Path] = {}
    for split in BENCHMARK_SPLITS:
        path = raw_dir / f"{split}.txt"
        files[path.name] = path
        for index, utterance in enumerate(parse_agif(path.read_text(encoding="utf-8"), str(path))):
            examples.append(
                Example(
                    id=make_id(dataset, split, index),
                    text=" ".join(utterance.tokens),
                    labels=utterance.intents,
                    # Several intents have no ranking between them, so there is no gold lead.
                    lead=utterance.intents[0] if len(utterance.intents) == 1 else None,
                    out_of_scope=False,
                    split=split,
                )
            )
    return Conversion(dataset=dataset, examples=examples, source_files=files)
