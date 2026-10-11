"""A. Text encoder: a pretrained transformer that turns tokens into one vector per token.

Returns the token states (batch, tokens, hidden) and the attention mask (1 for real tokens, 0 for padding).
"""

import torch
from torch import nn


class TextEncoder(nn.Module):
    def __init__(self, model: str | nn.Module) -> None:
        super().__init__()
        if isinstance(model, str):
            from transformers import AutoModel

            model = AutoModel.from_pretrained(model)
        self.model = model

    @property
    def hidden_size(self) -> int:
        return int(self.model.config.hidden_size)

    def forward(
        self, input_ids: torch.Tensor, attention_mask: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        output = self.model(input_ids=input_ids, attention_mask=attention_mask)
        return output.last_hidden_state, attention_mask


def mean_pool(states: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """Average of the real (unpadded) token vectors: one vector per text."""
    weights = mask.unsqueeze(-1).to(states.dtype)
    return (states * weights).sum(dim=1) / weights.sum(dim=1).clamp(min=1.0)


@torch.no_grad()
def embed_texts(encoder: TextEncoder, tokenizer, texts: list[str], max_length: int = 128) -> torch.Tensor:  # type: ignore[no-untyped-def]
    """Mean-pooled embeddings of short texts (used once, to initialise the label queries)."""
    was_training = encoder.training
    encoder.eval()
    batch = tokenizer(texts, padding=True, truncation=True, max_length=max_length, return_tensors="pt")
    states, mask = encoder(batch["input_ids"], batch["attention_mask"])
    encoder.train(was_training)
    return mean_pool(states, mask)
