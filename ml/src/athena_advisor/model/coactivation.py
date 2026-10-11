"""E. Co-activation: labels that usually come together nudge each other's scores.

    z' = z + A . sigmoid(z)        A is K x K with a zero diagonal

If label j looks likely (sigmoid(z_j) near 1), label k's score moves by A[k, j]. A starts from how often the
labels co-occur in train (pointwise mutual information, PMI, scaled down), so "code" and "checker" start
by supporting each other if they often appear together. A is kept small by an L2 penalty added to the loss.
The diagonal is forced to zero on every pass, so a label never boosts itself.
"""

import numpy as np
import torch
from torch import nn


def scaled_pmi(team: np.ndarray, scale: float, smoothing: float = 1.0) -> np.ndarray:
    """PMI(i, j) = log(P(i and j) / (P(i) P(j))) from a 0/1 label matrix, times `scale`, zero diagonal.

    Positive: the pair appears together more often than chance; negative: less often. Counts are smoothed
    so pairs never seen together get a finite negative value instead of minus infinity.
    """
    team = np.asarray(team, dtype=float)
    n = team.shape[0]
    both = team.T @ team
    single = team.sum(axis=0)
    p_both = (both + smoothing) / (n + smoothing)
    p_single = (single + smoothing) / (n + smoothing)
    pmi = np.log(p_both / np.outer(p_single, p_single))
    np.fill_diagonal(pmi, 0.0)
    return pmi * scale


class CoActivation(nn.Module):
    def __init__(self, num_labels: int, init: np.ndarray | None = None, l2: float = 0.001) -> None:
        super().__init__()
        start = (
            torch.zeros(num_labels, num_labels)
            if init is None
            else torch.as_tensor(init, dtype=torch.float32)
        )
        self.A = nn.Parameter(start.clone())
        self.register_buffer("off_diagonal", 1.0 - torch.eye(num_labels))
        self.l2 = l2

    def matrix(self) -> torch.Tensor:
        return self.A * self.off_diagonal

    def forward(self, logits: torch.Tensor) -> torch.Tensor:
        return logits + torch.sigmoid(logits) @ self.matrix().T

    def penalty(self) -> torch.Tensor:
        return self.l2 * self.matrix().pow(2).sum()
