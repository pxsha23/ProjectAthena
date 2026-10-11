"""SetFit baseline (tiny random model, no downloads), simple decision rules, and the baseline runner."""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from athena_advisor.baselines.run import load_dataset, run_baseline
from athena_advisor.baselines.setfit_baseline import SetFitBaseline, has_contrastive_pairs, stratified_sample
from athena_advisor.config import load_config
from athena_advisor.data.benchmarks import build_benchmarks
from athena_advisor.data.build import build
from athena_advisor.decide.simple import call_all, top1
from athena_advisor.eval.data import LabelledSplit, load_split
from athena_advisor.eval.predictions import Predictions
from athena_advisor.paths import ml_root

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("built")
    config = load_config("configs/base.yaml", ["data.split_fractions=[0.4, 0.2, 0.2, 0.2]"])
    build(config, FIXTURES / "stacksample_tiny", out / "stacksample")
    build_benchmarks(FIXTURES / "benchmarks", out / "benchmarks", config.benchmarks)
    return out


def overrides(built: Path, results: Path) -> list[str]:
    return [
        f"data.processed_dir={built.as_posix()}",
        f"benchmarks.processed_dir={(built / 'benchmarks').as_posix()}",
        f"results_dir={results.as_posix()}",
    ]


def _dimension(word) -> int:  # type: ignore[no-untyped-def]
    # Renamed in newer sentence-transformers releases.
    getter = getattr(word, "get_embedding_dimension", None) or word.get_word_embedding_dimension
    return getter()


@pytest.fixture(scope="module")
def tiny_encoder(tmp_path_factory: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
    """A 1-layer, 16-dimension BERT with random weights and a small vocabulary, built locally."""
    from sentence_transformers import SentenceTransformer, models
    from transformers import BertConfig, BertModel, BertTokenizerFast

    folder = tmp_path_factory.mktemp("tiny_encoder")
    vocab = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]", *"abcdefghijklmnopqrstuvwxyz0123456789"]
    (folder / "vocab.txt").write_text("\n".join(vocab), encoding="utf-8")
    BertTokenizerFast(vocab_file=str(folder / "vocab.txt")).save_pretrained(folder)
    config = BertConfig(
        vocab_size=len(vocab),
        hidden_size=16,
        num_hidden_layers=1,
        num_attention_heads=2,
        intermediate_size=32,
        max_position_embeddings=64,
    )
    BertModel(config).save_pretrained(folder)
    word = models.Transformer(str(folder), max_seq_length=32)
    return SentenceTransformer(modules=[word, models.Pooling(_dimension(word), "mean")], device="cpu")


# ---------------------------------------------------------------- SetFit


def test_stratified_sample_keeps_every_group() -> None:
    groups = np.array([0] * 90 + [1] * 9 + [2] * 1)
    rows = stratified_sample(groups, 10, seed=0)
    assert len(rows) == 10 and len(set(rows.tolist())) == 10
    picked = groups[rows]
    assert (picked == 2).sum() == 1 and (picked == 1).sum() >= 1 and (picked == 0).sum() >= 7
    assert np.array_equal(rows, stratified_sample(groups, 10, seed=0))
    assert not np.array_equal(rows, stratified_sample(groups, 10, seed=3))
    assert np.array_equal(stratified_sample(groups, 500, seed=0), np.arange(100))  # small data: all rows


@pytest.mark.parametrize("dataset", ["stacksample", "mixsnips", "clinc150", "nlbse"])
def test_setfit_predictions_have_the_right_shape(built: Path, tiny_encoder, dataset: str) -> None:  # type: ignore[no-untyped-def]
    config = load_config("configs/base.yaml", overrides(built, built / "unused"))
    splits = load_dataset(config, dataset)
    baseline = SetFitBaseline(model=tiny_encoder, train_max=6, num_iterations=1, batch_size=4)
    baseline.fit(splits["train"], seed=0)
    assert baseline.train_rows <= 6
    predictions = baseline.predict(splits["test"], dataset, "test", seed=0)
    k = len(splits["train"].labels)
    assert predictions.team_probs.shape == predictions.lead_probs.shape == (len(splits["test"]), k)
    assert np.allclose(predictions.lead_probs.sum(axis=1), 1.0)
    assert ((predictions.team_probs >= 0) & (predictions.team_probs <= 1)).all()
    assert predictions.meta["model"] == "setfit"


def test_contrastive_pair_check() -> None:
    assert has_contrastive_pairs(np.array([[1, 0], [1, 0], [0, 1]], dtype=bool))
    assert not has_contrastive_pairs(np.array([[1, 1], [1, 0], [1, 1]], dtype=bool))  # every pair shares one
    assert not has_contrastive_pairs(np.array([[1, 0], [0, 1]], dtype=bool))  # no pair shares a label


def test_setfit_falls_back_to_head_only_on_tiny_samples(built: Path, tiny_encoder) -> None:  # type: ignore[no-untyped-def]
    config = load_config("configs/base.yaml", overrides(built, built / "unused"))
    stacksample = load_dataset(config, "stacksample")["train"]  # all 3 train questions share "code"
    assert SetFitBaseline(model=tiny_encoder, num_iterations=1).fit(stacksample).contrastive is False
    # Two groups of two: same-label and different-label pairs both exist, so SetFit trains fully.
    pairs = LabelledSplit(
        ids=np.array(["a", "b", "c", "d"]),
        texts=["red apple", "red cherry", "blue ocean", "blue sky"],
        labels=("red", "blue"),
        team=np.array([[1, 0], [1, 0], [0, 1], [0, 1]], dtype=np.int8),
        lead=np.array([0, 0, 1, 1]),
        out_of_scope=np.zeros(4, bool),
    )
    full = SetFitBaseline(model=tiny_encoder, num_iterations=1, batch_size=2).fit(pairs)
    assert full.contrastive is True


# ---------------------------------------------------------------- simple decision rules


def test_call_all_and_top1_on_a_known_array() -> None:
    team = np.array([[0.2, 0.9, 0.4], [0.7, 0.1, 0.65]])
    lead = np.array([[0.1, 0.3, 0.6], [0.5, 0.2, 0.3]])
    predictions = Predictions(
        ids=["a", "b"], labels=("x", "y", "z"), team_probs=team, lead_probs=lead, latency_ms=[1, 1]
    )
    everything = call_all(predictions)
    assert everything.active.tolist() == [[1, 1, 1], [1, 1, 1]]
    assert everything.lead.tolist() == [2, 0]  # the highest lead probability, not the highest team one
    single = top1(predictions)
    assert single.active.tolist() == [[0, 1, 0], [1, 0, 0]]
    assert single.lead.tolist() == [1, 0]  # the one active label is also the lead


# ---------------------------------------------------------------- run_baseline


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ml_root() / "scripts" / "run_baseline.py"), *args],
        capture_output=True,
        text=True,
        cwd=ml_root(),
    )


def test_run_baseline_writes_three_splits_and_a_record(built: Path, tmp_path: Path) -> None:
    sets = [arg for o in overrides(built, tmp_path) for arg in ("--set", o)]
    result = run_script(
        "--baseline",
        "tfidf_lr",
        "--dataset",
        "stacksample",
        "--seed",
        "0",
        *sets,
        "--set",
        "baselines.tfidf_min_df=1",
    )
    assert result.returncode == 0, result.stderr
    assert "Wrote" in result.stdout
    for split in ("val_tune", "val_cal", "test"):
        assert (tmp_path / "predictions" / "tfidf_lr" / "stacksample" / split / "0.npz").is_file()
    record = json.loads(
        (tmp_path / "baselines_stacksample" / "tfidf_lr" / "0.json").read_text(encoding="utf-8")
    )
    assert record["seed"] == 0 and record["metadata"]["config"]["condition"] == "tfidf_lr"
    test_metrics = record["metrics"]["test"]
    assert {"micro_f1", "macro_f1", "lead_accuracy", "lead_rows", "team_ece", "decision_rules"} <= set(
        test_metrics
    )
    assert set(test_metrics["decision_rules"]) == {"call_all", "top1"}
    assert len(record["metadata"]["data_hashes"]) == 4  # the four StackSample parquet files

    again = run_script(
        "--baseline",
        "tfidf_lr",
        "--dataset",
        "stacksample",
        "--seed",
        "0",
        *sets,
        "--set",
        "baselines.tfidf_min_df=1",
    )
    assert "Already done" in again.stdout


def test_not_applicable_is_reported_clearly(built: Path, tmp_path: Path) -> None:
    sets = [arg for o in overrides(built, tmp_path) for arg in ("--set", o)]
    result = run_script("--baseline", "keyword", "--dataset", "mixatis", *sets)
    assert result.returncode == 0
    assert "Not applicable: keyword baseline skipped for mixatis" in result.stdout
    assert result.stdout.count("Not applicable") == 1  # reported once, not once per seed
    note = json.loads(
        (tmp_path / "baselines_mixatis" / "keyword" / "not_applicable.json").read_text(encoding="utf-8")
    )
    assert note["dataset"] == "mixatis" and "not specialists" in note["reason"]
    assert not (tmp_path / "predictions").exists()


def test_benchmark_dev_is_split_into_fixed_halves(built: Path, tmp_path: Path) -> None:
    config = load_config("configs/base.yaml", overrides(built, tmp_path))
    first, second = load_dataset(config, "clinc150"), load_dataset(config, "clinc150")
    dev = load_split(built / "benchmarks" / "clinc150", "dev")
    assert sorted([*first["val_tune"].ids, *first["val_cal"].ids]) == sorted(dev.ids)
    assert not set(first["val_tune"].ids) & set(first["val_cal"].ids)
    assert first["val_tune"].ids.tolist() == second["val_tune"].ids.tolist()  # same halves every time

    outcome = run_baseline("prior", "clinc150", config, seed=1)
    assert outcome.status == "done" and set(outcome.predictions) == {"val_tune", "val_cal", "test"}
    record = json.loads(outcome.record.read_text(encoding="utf-8"))
    assert record["metrics"]["test"]["clinc"]["out_of_scope_rows"] == 2
