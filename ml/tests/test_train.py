"""Training on CPU with the tiny random BERT and the fixtures: one epoch, resume, and the output files."""

import csv
import json
from pathlib import Path

import numpy as np
import pytest
import torch

from athena_advisor.config import SPECIALISTS, load_config
from athena_advisor.data.benchmarks import build_benchmarks
from athena_advisor.data.build import build
from athena_advisor.eval.predictions import Predictions
from athena_advisor.eval.splits import load_dataset
from athena_advisor.train.data import make_loader
from athena_advisor.train.trainer import run_dir, train_run

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("built")
    config = load_config("configs/base.yaml", ["data.split_fractions=[0.4, 0.2, 0.2, 0.2]"])
    build(config, FIXTURES / "stacksample_tiny", out / "stacksample")
    build_benchmarks(FIXTURES / "benchmarks", out / "benchmarks", config.benchmarks)
    return out


def config_for(built: Path, results: Path, *extra: str):  # type: ignore[no-untyped-def]
    return load_config(
        "configs/experiments/full.yaml",
        [
            f"data.processed_dir={built.as_posix()}",
            f"benchmarks.processed_dir={(built / 'benchmarks').as_posix()}",
            f"results_dir={results.as_posix()}",
            "data.max_length=32",
            "train.batch_size=2",
            "train.eval_batch_size=4",
            "train.device=cpu",
            "train.early_stopping_patience=5",
            *extra,
        ],
    )


def log_rows(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8")))


def test_loader_batches(built: Path, tmp_path: Path, tiny_tokenizer) -> None:  # type: ignore[no-untyped-def]
    splits = load_dataset(config_for(built, tmp_path), "stacksample")
    batch = next(iter(make_loader(splits["train"], tiny_tokenizer, 32, 2, shuffle=False)))
    assert batch.input_ids.shape[0] == 2 and batch.input_ids.shape == batch.attention_mask.shape
    assert batch.context.shape == (2, 43) and torch.all(batch.context[:, 0] == 1)  # StackSample has context
    assert (
        batch.team.shape == (2, len(SPECIALISTS)) and batch.lead.tolist() == splits["train"].lead[:2].tolist()
    )

    benchmark = load_dataset(config_for(built, tmp_path), "clinc150")["train"]
    batch = next(iter(make_loader(benchmark, tiny_tokenizer, 32, 4, shuffle=False)))
    assert torch.all(batch.context == 0)  # benchmarks get the null context


def test_one_epoch_on_cpu_writes_everything(
    built: Path, tmp_path: Path, tiny_tokenizer, make_tiny_bert
) -> None:  # type: ignore[no-untyped-def]
    config = config_for(built, tmp_path, "train.epochs=1")
    result = train_run(config, "stacksample", 0, tokenizer=tiny_tokenizer, encoder_model=make_tiny_bert())
    assert result is not None and result.state.epoch == 1 and result.state.best_epoch == 0
    folder = run_dir(config, "stacksample", 0)
    assert (folder / "last.pt").is_file() and (folder / "best.pt").is_file()
    rows = log_rows(result.log)
    assert len(rows) == 1 and rows[0]["epoch"] == "0" and float(rows[0]["lr_head"]) > 0

    splits = load_dataset(config, "stacksample")
    for split, path in result.predictions.items():
        predictions = Predictions.load(path)
        n = len(splits[split])
        assert predictions.team_probs.shape == predictions.lead_probs.shape == (n, len(SPECIALISTS))
        assert predictions.ids.tolist() == splits[split].ids.tolist()
        assert np.allclose(predictions.lead_probs.sum(axis=1), 1.0)
        assert predictions.meta["model"] == "advisor_full"
    assert path == tmp_path / "predictions" / "advisor_full" / "stacksample" / "test" / "0.npz"

    record = json.loads(result.record.read_text(encoding="utf-8"))
    assert result.record == tmp_path / "ablations_stacksample" / "full" / "0.json"
    assert {"micro_f1", "macro_f1", "lead_accuracy", "team_ece"} <= set(record["metrics"]["test"])
    assert record["metrics"]["training"]["mode"] == "multilabel"


def test_resume_matches_an_uninterrupted_run(
    built: Path, tmp_path: Path, tiny_tokenizer, make_tiny_bert
) -> None:  # type: ignore[no-untyped-def]
    straight = config_for(built, tmp_path / "straight", "train.epochs=2")
    train_run(straight, "stacksample", 0, tokenizer=tiny_tokenizer, encoder_model=make_tiny_bert())

    interrupted = config_for(built, tmp_path / "resumed", "train.epochs=2")
    first = train_run(
        interrupted, "stacksample", 0, tokenizer=tiny_tokenizer, encoder_model=make_tiny_bert(), stop_after=1
    )
    assert first is None  # stopped after epoch 0, no outputs yet
    assert len(log_rows(run_dir(interrupted, "stacksample", 0) / "train_log.csv")) == 1
    # A fresh process would rebuild the model from scratch; resume restores everything from last.pt.
    second = train_run(
        interrupted, "stacksample", 0, tokenizer=tiny_tokenizer, encoder_model=make_tiny_bert(seed=99)
    )
    assert second is not None and second.state.epoch == 2

    resumed_log = log_rows(second.log)
    straight_log = log_rows(run_dir(straight, "stacksample", 0) / "train_log.csv")
    assert [r["epoch"] for r in resumed_log] == ["0", "1"]
    assert [r["train_loss"] for r in resumed_log] == [r["train_loss"] for r in straight_log]
    a = torch.load(run_dir(straight, "stacksample", 0) / "last.pt", weights_only=False)["model"]
    b = torch.load(run_dir(interrupted, "stacksample", 0) / "last.pt", weights_only=False)["model"]
    assert all(torch.equal(a[name], b[name]) for name in a)


def test_finished_run_is_not_trained_again(
    built: Path, tmp_path: Path, tiny_tokenizer, make_tiny_bert
) -> None:  # type: ignore[no-untyped-def]
    config = config_for(built, tmp_path, "train.epochs=1")
    train_run(config, "stacksample", 0, tokenizer=tiny_tokenizer, encoder_model=make_tiny_bert())
    again = train_run(config, "stacksample", 0, tokenizer=tiny_tokenizer, encoder_model=make_tiny_bert())
    assert again is not None and len(log_rows(again.log)) == 1  # resumed, nothing left to train


@pytest.mark.parametrize(("dataset", "mode"), [("clinc150", "singlelabel"), ("mixsnips", "multilabel")])
def test_benchmarks_train_in_their_mode(
    built: Path, tmp_path: Path, tiny_tokenizer, make_tiny_bert, dataset: str, mode: str
) -> None:  # type: ignore[no-untyped-def]
    config = config_for(built, tmp_path, "train.epochs=1")
    result = train_run(config, dataset, 1, tokenizer=tiny_tokenizer, encoder_model=make_tiny_bert())
    record = json.loads(result.record.read_text(encoding="utf-8"))
    assert record["metrics"]["training"]["mode"] == mode
    splits = load_dataset(config, dataset)
    test = Predictions.load(result.predictions["test"])
    assert test.team_probs.shape == (len(splits["test"]), len(splits["train"].labels))
    if mode == "singlelabel":
        assert np.allclose(test.team_probs.sum(axis=1), 1.0)  # softmax over the labels
        assert np.allclose(test.team_probs, test.lead_probs, atol=1e-6)  # the label is the lead
        assert "clinc" in record["metrics"]["test"]
