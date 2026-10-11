"""D. Label-wise attention: each label reads the tokens that matter to it.

Every label has its own query vector, initialised from the embedding of the label's description. For each
label, the query scores every token, padding is masked out, and a softmax turns the scores into attention
weights over tokens. The weighted sum of token vectors is that label's own view of the text, and a per-label
linear score of that vector is the label's logit. The weights also explain the prediction: they show which
words each label looked at.
"""

import math

import torch
from torch import nn


class LabelAttention(nn.Module):
    def __init__(self, hidden_size: int, num_labels: int, init_queries: torch.Tensor | None = None) -> None:
        super().__init__()
        queries = (
            torch.randn(num_labels, hidden_size) * 0.02 if init_queries is None else init_queries.clone()
        )
        if queries.shape != (num_labels, hidden_size):
            raise ValueError(
                f"init_queries must have shape {(num_labels, hidden_size)}, got {tuple(queries.shape)}"
            )
        self.queries = nn.Parameter(queries.float())
        # One scoring vector and bias per label: logit_k = w_k . v_k + b_k
        self.score_weight = nn.Parameter(torch.randn(num_labels, hidden_size) * 0.02)
        self.score_bias = nn.Parameter(torch.zeros(num_labels))
        self.scale = 1.0 / math.sqrt(hidden_size)

    def forward(
        self, states: torch.Tensor, mask: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """states (B, T, H), mask (B, T) -> vectors (B, K, H), logits (B, K), weights (B, K, T)."""
        scores = torch.einsum("bth,kh->bkt", states, self.queries) * self.scale
        scores = scores.masked_fill(mask.unsqueeze(1) == 0, torch.finfo(scores.dtype).min)
        weights = scores.softmax(dim=-1)
        vectors = torch.einsum("bkt,bth->bkh", weights, states)
        logits = (vectors * self.score_weight).sum(dim=-1) + self.score_bias
        return vectors, logits, weights
