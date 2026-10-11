"""The Advisor model and its losses, on a tiny random BERT (2 layers, hidden 32) with no downloads."""

from pathlib import Path

import numpy as np
import pytest
import torch

from athena_advisor.config import SPECIALISTS, AdvisorConfig, load_config
from athena_advisor.data.context import CONTEXT_DIM, ContextSchema, null_context_vector
from athena_advisor.losses import (
    MultiTaskLoss,
    focal_bce,
    masked_cross_entropy,
    supervised_contrastive,
)
from athena_advisor.model.advisor import AdvisorModel, build_model, describe_label, label_descriptions
from athena_advisor.model.coactivation import CoActivation, scaled_pmi
from athena_advisor.model.encoder import TextEncoder, embed_texts
from athena_advisor.model.film import FiLM

VOCAB = Path(__file__).parent / "fixtures" / "tiny_vocab.txt"
HIDDEN = 32
TEXTS = ["my docker build fails", "how to test the api", "python import error when i run the app"]


@pytest.fixture(scope="module")
def tokenizer():  # type: ignore[no-untyped-def]
    from transformers import BertTokenizerFast

    return BertTokenizerFast(vocab_file=str(VOCAB))


def tiny_bert(seed: int = 0):  # type: ignore[no-untyped-def]
    from transformers import BertConfig, BertModel

    torch.manual_seed(seed)
    config = BertConfig(
        vocab_size=sum(1 for _ in VOCAB.open(encoding="utf-8")),
        hidden_size=HIDDEN,
        num_hidden_layers=2,
        num_attention_heads=2,
        intermediate_size=64,
        max_position_embeddings=64,
    )
    return BertModel(config)


def batch(tokenizer, texts=TEXTS):  # type: ignore[no-untyped-def]
    encoded = tokenizer(texts, padding=True, return_tensors="pt")
    return encoded["input_ids"], encoded["attention_mask"]


def model_for(tokenizer, mode: str, *overrides: str, labels=tuple(SPECIALISTS), team=None) -> AdvisorModel:  # type: ignore[no-untyped-def]
    config = load_config("configs/base.yaml", list(overrides))
    model = build_model(config, labels, mode, tokenizer=tokenizer, encoder_model=tiny_bert(), train_team=team)
    return model.eval()


def random_contexts(n: int, present: bool = True) -> torch.Tensor:
    context = torch.rand(n, CONTEXT_DIM)
    context[:, 0] = 1.0 if present else 0.0
    return context


# ---------------------------------------------------------------- shapes in both modes


def test_multilabel_output_shapes(tokenizer) -> None:  # type: ignore[no-untyped-def]
    team = np.array([[1, 1, 0, 0, 0], [0, 0, 0, 1, 1], [0, 1, 1, 0, 0]])
    model = model_for(tokenizer, "multilabel", team=team)
    ids, mask = batch(tokenizer)
    output = model(ids, mask, random_contexts(3))
    b, t, k = ids.shape[0], ids.shape[1], len(SPECIALISTS)
    assert output.team_logits.shape == output.lead_logits.shape == (b, k)
    assert output.sentence.shape == (b, HIDDEN)
    assert output.attention.shape == (b, k, t)
    assert torch.allclose(output.attention.sum(dim=-1), torch.ones(b, k))
    team_probs, lead_probs = model.team_probs(output), model.lead_probs(output)
    assert ((team_probs > 0) & (team_probs < 1)).all()
    assert torch.allclose(lead_probs.sum(dim=-1), torch.ones(b))
    assert output.coactivation_penalty.item() > 0  # PMI-initialised A is not all zero


def test_singlelabel_mode(tokenizer) -> None:  # type: ignore[no-untyped-def]
    labels = ("bug", "enhancement", "question")
    model = model_for(tokenizer, "singlelabel", labels=labels, team=np.eye(3))
    ids, mask = batch(tokenizer)
    output = model(ids, mask)
    assert output.team_logits.shape == (3, 3)
    assert torch.equal(output.lead_logits, output.team_logits)  # the one label is the lead
    assert torch.allclose(model.team_probs(output).sum(dim=-1), torch.ones(3))  # softmax, not sigmoid
    assert model.coactivation is None and output.coactivation_penalty.item() == 0.0


def test_padding_gets_no_attention(tokenizer) -> None:  # type: ignore[no-untyped-def]
    model = model_for(tokenizer, "multilabel")
    ids, mask = batch(tokenizer, ["docker", "python import error when i run the app"])
    weights = model.explain(ids, mask)
    assert mask[0].sum() < mask.shape[1]  # the short text is padded
    assert torch.all(weights[0][:, mask[0] == 0] == 0)
    assert weights.shape == (2, len(SPECIALISTS), ids.shape[1])


# ---------------------------------------------------------------- FiLM


def test_film_starts_as_identity_and_ignores_missing_context() -> None:
    film = FiLM(CONTEXT_DIM, HIDDEN)
    states = torch.randn(4, 6, HIDDEN)
    assert torch.equal(film(states, random_contexts(4)), states)  # zero-initialised last layer
    torch.nn.init.normal_(film.state_encoder.net[-1].weight)
    torch.nn.init.normal_(film.state_encoder.net[-1].bias)
    assert not torch.allclose(film(states, random_contexts(4)), states)  # learned weights now act
    assert torch.equal(film(states, random_contexts(4, present=False)), states)  # no context: unchanged


def test_model_without_context_matches_null_context(tokenizer) -> None:  # type: ignore[no-untyped-def]
    model = model_for(tokenizer, "multilabel")
    torch.nn.init.normal_(model.film.state_encoder.net[-1].weight)
    ids, mask = batch(tokenizer)
    null = torch.as_tensor(np.stack([null_context_vector()] * 3))
    real = torch.as_tensor(
        np.stack([ContextSchema.from_stackoverflow_body("<p>docker fails on port 8000</p>").encode()] * 3)
    )
    without = model(ids, mask).team_logits
    assert torch.allclose(without, model(ids, mask, null).team_logits)
    assert not torch.allclose(without, model(ids, mask, real).team_logits)


# ---------------------------------------------------------------- label attention and descriptions


def test_queries_start_from_label_descriptions(tokenizer) -> None:  # type: ignore[no-untyped-def]
    model = model_for(tokenizer, "multilabel")
    descriptions = label_descriptions(tuple(SPECIALISTS), "configs/specialists.yaml")
    assert descriptions[0].startswith("Planning how the app is built")
    expected = embed_texts(TextEncoder(tiny_bert()), tokenizer, descriptions)
    assert torch.allclose(model.label_attention.queries, expected, atol=1e-5)


def test_benchmark_label_descriptions() -> None:
    assert describe_label("atis_flight") == "flight"
    assert describe_label("atis_ground_service") == "ground service"
    assert describe_label("PlayMusic") == "play music"
    assert describe_label("SearchCreativeWork") == "search creative work"
    assert describe_label("credit_limit_change") == "credit limit change"
    assert label_descriptions(("atis_airfare", "code"), "configs/specialists.yaml")[0] == "airfare"


# ---------------------------------------------------------------- co-activation


def test_scaled_pmi() -> None:
    # Labels 0 and 1 always appear together; label 2 never appears with them.
    team = np.array([[1, 1, 0]] * 5 + [[0, 0, 1]] * 5)
    pmi = scaled_pmi(team, scale=0.1)
    assert np.all(np.diag(pmi) == 0)
    assert pmi[0, 1] > 0 and pmi[1, 0] == pmi[0, 1]
    assert pmi[0, 2] < 0 and np.isfinite(pmi).all()


def test_coactivation_keeps_a_zero_diagonal() -> None:
    layer = CoActivation(3, l2=0.5)
    with torch.no_grad():
        layer.A.copy_(torch.tensor([[9.0, 1.0, 0.0], [0.0, 9.0, 0.0], [0.0, 2.0, 9.0]]))
    z = torch.zeros(1, 3)  # sigmoid(0) = 0.5 for every label
    # The diagonal (9) is ignored: z'_0 = 0.5 * 1, z'_1 = 0, z'_2 = 0.5 * 2.
    assert torch.allclose(layer(z), torch.tensor([[0.5, 0.0, 1.0]]))
    assert layer.penalty().item() == pytest.approx(0.5 * (1.0 + 4.0))


# ---------------------------------------------------------------- presets and ablations


@pytest.mark.parametrize(
    ("name", "film", "attention", "coactivation", "contrastive"),
    [
        ("full", True, True, True, True),
        ("plain", False, False, False, False),
        ("no_film", False, True, True, True),
        ("no_label_attention", True, False, True, True),
        ("no_coactivation", True, True, False, True),
        ("no_contrastive", True, True, True, False),
    ],
)
def test_ablation_configs(
    name: str, film: bool, attention: bool, coactivation: bool, contrastive: bool
) -> None:
    config = load_config(f"configs/experiments/{name}.yaml")
    assert (config.experiment, config.condition) == ("ablations", name)
    m = config.model
    assert (m.use_film, m.use_label_attention, m.use_coactivation, config.loss.use_contrastive) == (
        film,
        attention,
        coactivation,
        contrastive,
    )


def test_plain_preset_is_the_plain_classifier(tokenizer) -> None:  # type: ignore[no-untyped-def]
    config = load_config("configs/experiments/plain.yaml")
    model = build_model(
        config, tuple(SPECIALISTS), "multilabel", tokenizer=tokenizer, encoder_model=tiny_bert()
    )
    assert model.film is None and model.label_attention is None and model.coactivation is None
    assert model.pooled_heads is not None
    ids, mask = batch(tokenizer)
    output = model(ids, mask, random_contexts(3))
    assert output.attention is None and output.team_logits.shape == (3, len(SPECIALISTS))
    with pytest.raises(RuntimeError, match="label attention"):
        model.explain(ids, mask)


# ---------------------------------------------------------------- losses


def test_focal_bce() -> None:
    logits = torch.tensor([[2.0, -1.0, 0.5]])
    targets = torch.tensor([[1, 0, 0]])
    plain = torch.nn.functional.binary_cross_entropy_with_logits(logits, targets.float())
    assert torch.allclose(focal_bce(logits, targets, gamma=0.0), plain)
    assert focal_bce(logits, targets, gamma=2.0) < plain  # easy decisions count less


def test_masked_cross_entropy() -> None:
    logits = torch.tensor([[3.0, 0.0], [0.0, 3.0], [5.0, -5.0]], requires_grad=True)
    targets = torch.tensor([0, 1, -1])
    expected = torch.nn.functional.cross_entropy(logits[:2], targets[:2])
    assert torch.allclose(masked_cross_entropy(logits, targets), expected)
    none = masked_cross_entropy(logits, torch.tensor([-1, -1, -1]))
    assert none.item() == 0.0 and none.requires_grad


def test_supervised_contrastive() -> None:
    team = torch.tensor([[1, 0], [1, 0], [0, 1], [0, 1], [0, 0]])
    grouped = torch.tensor([[1.0, 0.0], [0.9, 0.1], [0.0, 1.0], [0.1, 0.9], [0.7, 0.7]])
    mixed = torch.tensor([[1.0, 0.0], [0.0, 1.0], [0.9, 0.1], [0.1, 0.9], [0.7, 0.7]])
    assert supervised_contrastive(grouped, team, 0.07) < supervised_contrastive(mixed, team, 0.07)
    no_labels = supervised_contrastive(grouped, torch.zeros(5, 2), 0.07)
    assert no_labels.item() == 0.0


def test_multitask_loss_parts(tokenizer) -> None:  # type: ignore[no-untyped-def]
    config = AdvisorConfig()
    team = torch.tensor([[1, 1, 0, 0, 0], [0, 0, 0, 1, 0], [0, 1, 1, 0, 0]])
    lead = torch.tensor([0, 3, -1])
    model = model_for(tokenizer, "multilabel", team=team.numpy())
    ids, mask = batch(tokenizer)
    result = MultiTaskLoss(config.loss, "multilabel")(model(ids, mask), team, lead)
    assert set(result.parts) == {"team_focal", "lead_ce", "contrastive", "coactivation_l2"}
    assert result.total.item() == pytest.approx(sum(result.parts.values()), rel=1e-5)

    off = load_config("configs/experiments/no_contrastive.yaml").loss
    assert "contrastive" not in MultiTaskLoss(off, "multilabel")(model(ids, mask), team, lead).parts

    single = model_for(tokenizer, "singlelabel", labels=("bug", "enhancement", "question"))
    parts = MultiTaskLoss(config.loss, "singlelabel")(
        single(ids, mask), torch.eye(3, dtype=torch.long), torch.tensor([0, 1, 2])
    ).parts
    assert set(parts) == {"label_ce", "contrastive", "coactivation_l2"}


def test_training_steps_reduce_the_loss(tokenizer) -> None:  # type: ignore[no-untyped-def]
    team = torch.tensor([[1, 0, 0, 1, 0], [0, 1, 1, 0, 0], [0, 0, 0, 0, 1]])
    lead = torch.tensor([3, 2, 4])
    model = model_for(tokenizer, "multilabel", team=team.numpy())
    model.train()
    loss_fn = MultiTaskLoss(AdvisorConfig().loss, "multilabel")
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-2)
    ids, mask = batch(tokenizer)
    context = random_contexts(3)
    first = None
    for _ in range(15):
        optimizer.zero_grad()
        loss = loss_fn(model(ids, mask, context), team, lead).total
        loss.backward()
        first = first if first is not None else loss.item()
        optimizer.step()
    # Gradients reached the encoder, FiLM and co-activation.
    assert model.film.state_encoder.net[-1].weight.grad.abs().sum() > 0
    assert model.coactivation.A.grad.abs().sum() > 0
    assert next(model.encoder.parameters()).grad is not None
    assert loss.item() < first
