"""The full Athena Advisor model, assembled from config. Every part can be switched off for ablations.

    tokens -> A. encoder -> C. FiLM (context from B. state encoder) -> D. label attention or mean pooling
           -> F. heads -> E. co-activation (multi-label only) -> team logits, lead logits

Modes:
- multilabel (StackSample, MixATIS, MixSNIPS): team = independent sigmoid per label; lead = softmax over the
  per-label lead scores.
- singlelabel (CLINC150, NLBSE): team = softmax over labels (exactly one label), and the lead is that same
  label, so the lead logits are the team logits. Co-activation is not used: labels never co-occur, so
  their PMI is undefined.
The contrastive loss uses the mean-pooled sentence vector after FiLM, which is returned as `sentence`.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import torch
import yaml
from torch import nn

from athena_advisor.config import AdvisorConfig
from athena_advisor.data.context import CONTEXT_DIM
from athena_advisor.model.coactivation import CoActivation, scaled_pmi
from athena_advisor.model.encoder import TextEncoder, embed_texts, mean_pool
from athena_advisor.model.film import FiLM
from athena_advisor.model.heads import AttentionLeadHead, PooledHeads
from athena_advisor.model.label_attention import LabelAttention
from athena_advisor.paths import resolve

Mode = Literal["multilabel", "singlelabel"]


@dataclass
class AdvisorOutput:
    team_logits: torch.Tensor  # (B, K)
    lead_logits: torch.Tensor  # (B, K)
    sentence: torch.Tensor  # (B, H) mean-pooled tokens after FiLM, for the contrastive loss
    attention: torch.Tensor | None  # (B, K, T) per-label token weights, None without label attention
    coactivation_penalty: torch.Tensor  # scalar, 0 when co-activation is off


def describe_label(name: str) -> str:
    """A readable description from a benchmark label name: atis_flight -> "flight",
    PlayMusic -> "play music", credit_limit_change -> "credit limit change"."""
    name = re.sub(r"^atis_", "", name)
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)
    return re.sub(r"[_\-#]+", " ", name).strip().lower()


def label_descriptions(labels: tuple[str, ...], specialists_file: str | Path) -> list[str]:
    """Specialist labels use configs/specialists.yaml; any other label is described from its name."""
    path = resolve(specialists_file)
    known = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}
    return [known.get(label) or describe_label(label) for label in labels]


class AdvisorModel(nn.Module):
    def __init__(
        self,
        encoder: TextEncoder,
        labels: tuple[str, ...],
        mode: Mode,
        *,
        use_film: bool,
        use_label_attention: bool,
        use_coactivation: bool,
        context_dim: int = CONTEXT_DIM,
        context_hidden: int = 64,
        dropout: float = 0.1,
        init_queries: torch.Tensor | None = None,
        coactivation_init: np.ndarray | None = None,
        coactivation_l2: float = 0.001,
    ) -> None:
        super().__init__()
        if mode not in ("multilabel", "singlelabel"):
            raise ValueError(f"Unknown mode {mode!r}")
        self.labels = labels
        self.mode = mode
        self.context_dim = context_dim
        hidden, k = encoder.hidden_size, len(labels)
        self.encoder = encoder
        self.dropout = nn.Dropout(dropout)
        self.film = FiLM(context_dim, hidden, context_hidden) if use_film else None
        if use_label_attention:
            self.label_attention: LabelAttention | None = LabelAttention(hidden, k, init_queries)
            self.lead_head: AttentionLeadHead | None = AttentionLeadHead(hidden)
            self.pooled_heads: PooledHeads | None = None
        else:
            self.label_attention, self.lead_head = None, None
            self.pooled_heads = PooledHeads(hidden, k)
        use_coactivation = use_coactivation and mode == "multilabel"
        self.coactivation = CoActivation(k, coactivation_init, coactivation_l2) if use_coactivation else None

    def forward(
        self, input_ids: torch.Tensor, attention_mask: torch.Tensor, context: torch.Tensor | None = None
    ) -> AdvisorOutput:
        states, mask = self.encoder(input_ids, attention_mask)
        if self.film is not None:
            if context is None:
                # No context at all: the null vector (present = 0), which leaves the tokens unchanged.
                context = states.new_zeros(states.shape[0], self.context_dim)
            states = self.film(states, context.to(states.dtype))
        states = self.dropout(states)
        sentence = mean_pool(states, mask)

        attention = None
        if self.label_attention is not None:
            vectors, team_logits, attention = self.label_attention(states, mask)
            lead_logits = self.lead_head(vectors)  # type: ignore[misc]
        else:
            team_logits, lead_logits = self.pooled_heads(sentence)  # type: ignore[misc]

        penalty = team_logits.new_zeros(())
        if self.coactivation is not None:
            team_logits = self.coactivation(team_logits)
            penalty = self.coactivation.penalty()
        if self.mode == "singlelabel":
            # Exactly one label, which is also the lead.
            lead_logits = team_logits
        return AdvisorOutput(team_logits, lead_logits, sentence, attention, penalty)

    def team_probs(self, output: AdvisorOutput) -> torch.Tensor:
        if self.mode == "singlelabel":
            return output.team_logits.softmax(dim=-1)
        return torch.sigmoid(output.team_logits)

    def lead_probs(self, output: AdvisorOutput) -> torch.Tensor:
        return output.lead_logits.softmax(dim=-1)

    @torch.no_grad()
    def explain(
        self, input_ids: torch.Tensor, attention_mask: torch.Tensor, context: torch.Tensor | None = None
    ) -> torch.Tensor:
        """Per-label attention weights over tokens (B, K, T): which words each label looked at."""
        if self.label_attention is None:
            raise RuntimeError("explain() needs label attention, which is switched off in this config")
        output = self.forward(input_ids, attention_mask, context)
        assert output.attention is not None
        return output.attention


def build_model(
    config: AdvisorConfig,
    labels: tuple[str, ...],
    mode: Mode,
    *,
    tokenizer=None,  # type: ignore[no-untyped-def]
    encoder_model: nn.Module | None = None,
    train_team: np.ndarray | None = None,
) -> AdvisorModel:
    """Builds the model for one dataset.

    tokenizer / encoder_model default to config.model.encoder from the Hugging Face hub; tests pass tiny
    local ones. train_team (the train 0/1 label matrix) initialises co-activation from PMI.
    """
    settings = config.model
    encoder = TextEncoder(encoder_model if encoder_model is not None else settings.encoder)
    init_queries = None
    if settings.use_label_attention:
        if tokenizer is None:
            from transformers import AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(settings.encoder)
        descriptions = label_descriptions(labels, settings.specialists_file)
        init_queries = embed_texts(encoder, tokenizer, descriptions, config.data.max_length)
    coactivation_init = None
    if settings.use_coactivation and mode == "multilabel" and train_team is not None:
        coactivation_init = scaled_pmi(train_team, settings.coactivation_pmi_scale)
    return AdvisorModel(
        encoder,
        labels,
        mode,
        use_film=settings.use_film,
        use_label_attention=settings.use_label_attention,
        use_coactivation=settings.use_coactivation,
        context_hidden=settings.context_hidden,
        dropout=settings.dropout,
        init_queries=init_queries,
        coactivation_init=coactivation_init,
        coactivation_l2=settings.coactivation_l2,
    )
