"""F. Output heads: team logits and lead logits.

With label attention: the team logits come from the label-attention scores, and the lead score of each
label is a shared linear score of that label's attention vector (which label should lead this question).
Without label attention: the tokens are mean-pooled into one sentence vector and two plain linear heads
give the team and lead logits (the standard fine-tuned classifier).
"""

import torch
from torch import nn


class AttentionLeadHead(nn.Module):
    """lead_k = u . v_k + c, the same scoring vector for every label's attention vector v_k."""

    def __init__(self, hidden_size: int) -> None:
        super().__init__()
        self.score = nn.Linear(hidden_size, 1)

    def forward(self, label_vectors: torch.Tensor) -> torch.Tensor:
        return self.score(label_vectors).squeeze(-1)


class PooledHeads(nn.Module):
    def __init__(self, hidden_size: int, num_labels: int) -> None:
        super().__init__()
        self.team = nn.Linear(hidden_size, num_labels)
        self.lead = nn.Linear(hidden_size, num_labels)

    def forward(self, sentence: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        return self.team(sentence), self.lead(sentence)
