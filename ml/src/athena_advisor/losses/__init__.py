"""Training losses for the Advisor model.

multilabel:  focal BCE (team) + lead_weight * CE (lead, rows with a lead)
             + contrastive_weight * supervised contrastive + co-activation L2 penalty
singlelabel: CE (the one label, rows that have one) + contrastive_weight * supervised contrastive
"""

from dataclasses import dataclass

import torch
import torch.nn.functional as F
from torch import nn

from athena_advisor.config import LossConfig


def focal_bce(logits: torch.Tensor, targets: torch.Tensor, gamma: float) -> torch.Tensor:
    """Binary cross-entropy that down-weights easy decisions.

    Each term is scaled by (1 - p_t)^gamma, where p_t is the probability given to the correct answer. Easy
    cases (p_t near 1) count little, so the many obvious "this label is absent" decisions do not drown out
    the hard ones. gamma = 0 is plain binary cross-entropy.
    """
    targets = targets.to(logits.dtype)
    bce = F.binary_cross_entropy_with_logits(logits, targets, reduction="none")
    p = torch.sigmoid(logits)
    p_t = p * targets + (1 - p) * (1 - targets)
    return ((1 - p_t).pow(gamma) * bce).mean()


def masked_cross_entropy(logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
    """Cross-entropy over rows whose target is a label index; rows marked -1 (no lead, out of scope) are
    skipped. With no such row in the batch the loss is 0 (and still part of the graph)."""
    rows = targets >= 0
    if not rows.any():
        return logits.sum() * 0.0
    return F.cross_entropy(logits[rows], targets[rows])


def supervised_contrastive(embeddings: torch.Tensor, team: torch.Tensor, temperature: float) -> torch.Tensor:
    """Multi-label supervised contrastive loss with Jaccard-weighted positives.

    Sentence vectors are compared by cosine similarity. For each anchor row, every other row is a positive
    in proportion to how much their label sets overlap (Jaccard: shared labels / all labels of the two),
    and the loss pulls positives closer than everything else. Rows with no labels are never anchors but
    still serve as negatives.
    """
    team = team.to(embeddings.dtype)
    z = F.normalize(embeddings, dim=-1)
    similarity = z @ z.T / temperature
    n = z.shape[0]
    self_mask = torch.eye(n, dtype=torch.bool, device=z.device)
    # Log-probability of picking row j for anchor i among all other rows.
    log_prob = similarity.masked_fill(self_mask, float("-inf")).log_softmax(dim=1)
    shared = team @ team.T
    union = team.sum(dim=1, keepdim=True) + team.sum(dim=1) - shared
    jaccard = torch.where(union > 0, shared / union.clamp(min=1e-8), torch.zeros_like(shared))
    weights = jaccard.masked_fill(self_mask, 0.0)
    total = weights.sum(dim=1)
    anchors = total > 0
    if not anchors.any():
        return embeddings.sum() * 0.0
    per_anchor = -(weights * log_prob.masked_fill(self_mask, 0.0)).sum(dim=1) / total.clamp(min=1e-8)
    return per_anchor[anchors].mean()


@dataclass
class LossParts:
    total: torch.Tensor
    parts: dict[str, float]


class MultiTaskLoss(nn.Module):
    def __init__(self, config: LossConfig, mode: str) -> None:
        super().__init__()
        self.config = config
        self.mode = mode

    def forward(self, output, team: torch.Tensor, lead: torch.Tensor) -> LossParts:  # type: ignore[no-untyped-def]
        """team: (B, K) 0/1 gold labels; lead: (B,) gold lead index or -1."""
        c = self.config
        parts: dict[str, torch.Tensor] = {}
        if self.mode == "singlelabel":
            parts["label_ce"] = masked_cross_entropy(output.team_logits, lead)
        else:
            parts["team_focal"] = focal_bce(output.team_logits, team, c.focal_gamma)
            parts["lead_ce"] = c.lead_weight * masked_cross_entropy(output.lead_logits, lead)
        if c.use_contrastive and c.contrastive_weight > 0:
            parts["contrastive"] = c.contrastive_weight * supervised_contrastive(
                output.sentence, team, c.contrastive_temperature
            )
        parts["coactivation_l2"] = output.coactivation_penalty
        total = torch.stack(list(parts.values())).sum()
        return LossParts(total=total, parts={name: float(value.detach()) for name, value in parts.items()})
