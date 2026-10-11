"""B. State encoder: turns the 43-value context vector into FiLM parameters gamma and beta.

context (43) -> Linear -> 64 -> GELU -> Linear -> 2 x hidden, split into gamma and beta.
The last layer starts at zero, so at the start of training gamma = beta = 0 and FiLM changes nothing:
the model starts exactly as the plain text encoder and only learns to use context if it helps.
"""

import torch
from torch import nn


class StateEncoder(nn.Module):
    def __init__(self, context_dim: int, hidden_size: int, inner: int = 64) -> None:
        super().__init__()
        self.hidden_size = hidden_size
        self.net = nn.Sequential(nn.Linear(context_dim, inner), nn.GELU(), nn.Linear(inner, 2 * hidden_size))
        last = self.net[-1]
        nn.init.zeros_(last.weight)
        nn.init.zeros_(last.bias)

    def forward(self, context: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        gamma, beta = self.net(context).split(self.hidden_size, dim=-1)
        return gamma, beta
