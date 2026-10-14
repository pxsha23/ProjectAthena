"""Training data: batches of tokenised text, context vectors, team labels and lead labels.

Texts are tokenised per batch (padding only to the longest text in the batch) with the encoder's tokenizer,
truncated to data.max_length tokens. StackSample rows carry their 43-value context vector; benchmark rows get
the null context (all zeros, present flag 0), so FiLM leaves them unchanged.
"""

from dataclasses import dataclass

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

from athena_advisor.data.context import CONTEXT_DIM
from athena_advisor.eval.data import LabelledSplit


@dataclass
class Batch:
    rows: torch.Tensor  # (B,) row positions in the split, to match predictions back to ids
    input_ids: torch.Tensor
    attention_mask: torch.Tensor
    context: torch.Tensor  # (B, 43)
    team: torch.Tensor  # (B, K) 0/1
    lead: torch.Tensor  # (B,) label index, -1 when the row has no lead

    def to(self, device: torch.device) -> "Batch":
        return Batch(
            *(
                t.to(device)
                for t in (self.rows, self.input_ids, self.attention_mask, self.context, self.team, self.lead)
            )
        )


class SplitDataset(Dataset):
    """Row i of a labelled split. Tokenisation happens in the collate function, per batch."""

    def __init__(self, split: LabelledSplit) -> None:
        self.split = split
        if split.context is not None:
            self.context = np.asarray(split.context, dtype=np.float32)
        else:
            self.context = np.zeros((len(split), CONTEXT_DIM), dtype=np.float32)

    def __len__(self) -> int:
        return len(self.split)

    def __getitem__(self, i: int) -> int:
        return i


class Collator:
    def __init__(self, dataset: SplitDataset, tokenizer, max_length: int) -> None:  # type: ignore[no-untyped-def]
        self.dataset = dataset
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __call__(self, rows: list[int]) -> Batch:
        split = self.dataset.split
        encoded = self.tokenizer(
            [split.texts[i] for i in rows],
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )
        index = np.asarray(rows)
        return Batch(
            rows=torch.as_tensor(index),
            input_ids=encoded["input_ids"],
            attention_mask=encoded["attention_mask"],
            context=torch.as_tensor(self.dataset.context[index]),
            team=torch.as_tensor(split.team[index], dtype=torch.float32),
            lead=torch.as_tensor(split.lead[index], dtype=torch.long),
        )


def make_loader(
    split: LabelledSplit,
    tokenizer,  # type: ignore[no-untyped-def]
    max_length: int,
    batch_size: int,
    *,
    shuffle: bool,
    seed: int = 0,
) -> DataLoader:
    """A loader over one split. With shuffle, the order comes from its own seeded generator, so an epoch's
    order depends only on the seed passed in (which lets a resumed run see the same order)."""
    dataset = SplitDataset(split)
    generator = torch.Generator().manual_seed(seed) if shuffle else None
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        generator=generator,
        collate_fn=Collator(dataset, tokenizer, max_length),
    )
