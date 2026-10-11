"""C. FiLM gating: the situation (context) scales and shifts every token vector.

    h' = (1 + gamma) * h + beta        (gamma and beta are one vector per row, applied to every token)

Position 0 of the context vector is the `present` flag. Rows without context (present = 0) get
gamma = beta = 0, so their tokens pass through unchanged, whatever the state encoder has learned.
"""

import torch
from torch import nn

from athena_advisor.model.state_encoder import StateEncoder


class FiLM(nn.Module):
    def __init__(self, context_dim: int, hidden_size: int, inner: int = 64) -> None:
        super().__init__()
        self.state_encoder = StateEncoder(context_dim, hidden_size, inner)

    def forward(self, states: torch.Tensor, context: torch.Tensor) -> torch.Tensor:
        gamma, beta = self.state_encoder(context)
        present = context[:, :1].to(states.dtype)  # (batch, 1): 1 = real context, 0 = none
        gamma, beta = gamma * present, beta * present
        return (1 + gamma.unsqueeze(1)) * states + beta.unsqueeze(1)
