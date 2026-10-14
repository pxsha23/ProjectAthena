from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def results_dir(tmp_path: Path) -> str:
    """Run records go to a temporary folder, never into the real results/."""
    return str(tmp_path / "results")


TINY_VOCAB = FIXTURES / "tiny_vocab.txt"


@pytest.fixture(scope="session")
def tiny_tokenizer():  # type: ignore[no-untyped-def]
    """A WordPiece tokenizer over a small local vocabulary: no downloads."""
    from transformers import BertTokenizerFast

    return BertTokenizerFast(vocab_file=str(TINY_VOCAB))


@pytest.fixture
def make_tiny_bert():  # type: ignore[no-untyped-def]
    """Factory for a seeded random BERT with 2 layers and hidden size 32."""

    def make(seed: int = 0):  # type: ignore[no-untyped-def]
        import torch
        from transformers import BertConfig, BertModel

        torch.manual_seed(seed)
        config = BertConfig(
            vocab_size=sum(1 for _ in TINY_VOCAB.open(encoding="utf-8")),
            hidden_size=32,
            num_hidden_layers=2,
            num_attention_heads=2,
            intermediate_size=64,
            max_position_embeddings=64,
        )
        return BertModel(config)

    return make
