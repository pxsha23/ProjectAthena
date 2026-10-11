from pathlib import Path

import numpy as np
import pytest

from athena_advisor.baselines import KeywordBaseline, NotApplicable, PriorBaseline, TfidfLogisticBaseline
from athena_advisor.config import SPECIALISTS, load_config
from athena_advisor.data.benchmarks import build_benchmarks
from athena_advisor.data.build import build
from athena_advisor.eval.data import LabelledSplit, load_split
from athena_advisor.eval.metrics import clinc_metrics, multilabel_report, single_label_predictions
from athena_advisor.eval.predictions import Predictions, predictions_path


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """StackSample and every benchmark built from the fixtures, once for this module."""
    out = tmp_path_factory.mktemp("built")
    fixtures = Path(__file__).parent / "fixtures"
    config = load_config("configs/base.yaml", ["data.split_fractions=[0.4, 0.2, 0.2, 0.2]"])
    build(config, fixtures / "stacksample_tiny", out / "stacksample")
    build_benchmarks(fixtures / "benchmarks", out / "benchmarks", config.benchmarks)
    return out


def folder(built: Path, dataset: str) -> Path:
    return built / "stacksample" if dataset == "stacksample" else built / "benchmarks" / dataset


def splits(built: Path, dataset: str) -> tuple[LabelledSplit, LabelledSplit]:
    train = load_split(folder(built, dataset), "train")
    return train, load_split(folder(built, dataset), "test", train.labels)


# ---------------------------------------------------------------- predictions format


def make_predictions(n: int = 3) -> Predictions:
    lead = np.array([[0.7, 0.3], [0.5, 0.5], [0.1, 0.9]][:n])
    return Predictions(
        ids=[f"q{i}" for i in range(n)],
        labels=("x", "y"),
        team_probs=lead,
        lead_probs=lead,
        latency_ms=np.full(n, 1.5),
        meta={"model": "test", "seed": 0},
    )


def test_predictions_round_trip(tmp_path: Path) -> None:
    original = make_predictions()
    path = original.save(predictions_path(tmp_path, "test", "stacksample", "test", 0))
    assert path == tmp_path / "predictions" / "test" / "stacksample" / "test" / "0.npz"
    loaded = Predictions.load(path)
    assert loaded.ids.tolist() == ["q0", "q1", "q2"] and loaded.labels == ("x", "y")
    assert np.allclose(loaded.team_probs, original.team_probs) and loaded.meta == original.meta
    assert loaded.team_probs.dtype == np.float32


def test_predictions_are_validated_and_aligned() -> None:
    with pytest.raises(ValueError, match="sum to 1"):
        Predictions(
            ids=["a"], labels=("x", "y"), team_probs=[[0.5, 0.5]], lead_probs=[[0.5, 0.2]], latency_ms=[1]
        )
    with pytest.raises(ValueError, match="shape"):
        Predictions(ids=["a"], labels=("x",), team_probs=[[0.5, 0.5]], lead_probs=[[1.0]], latency_ms=[1])
    aligned = make_predictions().aligned_to(np.array(["q2", "q0", "q1"]))
    assert aligned.ids.tolist() == ["q2", "q0", "q1"] and aligned.lead_probs[0, 1] == pytest.approx(0.9)
    with pytest.raises(ValueError, match="no prediction"):
        make_predictions().aligned_to(np.array(["missing"]))


# ---------------------------------------------------------------- baselines on every dataset


@pytest.mark.parametrize("dataset", ["stacksample", "mixatis", "mixsnips", "clinc150", "nlbse"])
@pytest.mark.parametrize("make", [PriorBaseline, lambda: TfidfLogisticBaseline(min_df=1)])
def test_baselines_predict_every_dataset(built: Path, dataset: str, make) -> None:  # type: ignore[no-untyped-def]
    train, test = splits(built, dataset)
    predictions = make().fit(train).predict(test, dataset, "test")
    assert predictions.ids.tolist() == test.ids.tolist() and predictions.labels == train.labels
    assert predictions.team_probs.shape == (len(test), len(train.labels))
    assert np.allclose(predictions.lead_probs.sum(axis=1), 1.0)
    assert (predictions.latency_ms >= 0).all() and predictions.meta["dataset"] == dataset


def test_prior_predicts_train_frequencies(built: Path) -> None:
    train, test = splits(built, "stacksample")
    predictions = PriorBaseline().fit(train).predict(test, "stacksample", "test")
    # Train (fixture): blueprint in 1 of 3 teams, code in 3, eva in 1; leads: blueprint, code, eva.
    assert np.allclose(predictions.team_probs[0], [1 / 3, 1.0, 0.0, 0.0, 1 / 3])
    assert np.allclose(predictions.lead_probs[0], [1 / 3, 1 / 3, 0.0, 0.0, 1 / 3])
    assert np.allclose(predictions.team_probs, predictions.team_probs[0])  # the text is ignored


def test_keyword_matches_whole_tags_and_labels_them() -> None:
    baseline = KeywordBaseline()
    assert baseline.matched_tags("My Dockerfile breaks when PYTEST runs") == ["dockerfile", "pytest"]
    assert baseline.matched_tags("C# and node.js, also C++") == ["c#", "node.js", "c++"]
    assert baseline.matched_tags("a reactive design for flasks") == []  # no partial words

    train = LabelledSplit(
        ids=np.array(["t0", "t1"]),
        texts=["", ""],
        labels=tuple(SPECIALISTS),
        team=np.array([[0, 1, 0, 0, 0], [0, 1, 0, 0, 0]]),
        lead=np.array([1, 1]),
        out_of_scope=np.zeros(2, bool),
    )
    baseline.fit(train)
    team, lead = baseline.predict_probs(["My Dockerfile breaks when pytest runs", "nothing technical here"])
    order = list(SPECIALISTS)
    assert team[0].tolist() == [1.0 if s in ("deploy", "eva") else 0.0 for s in order]
    assert order[int(lead[0].argmax())] == "deploy"  # deploy and eva tie: priority order picks deploy
    assert team[1].sum() == 0 and order[int(lead[1].argmax())] == "code"  # no tag: train lead frequencies


@pytest.mark.parametrize("dataset", ["mixatis", "mixsnips", "clinc150", "nlbse"])
def test_keyword_is_skipped_for_benchmarks(built: Path, dataset: str) -> None:
    train, test = splits(built, dataset)
    with pytest.raises(NotApplicable, match="not specialists"):
        KeywordBaseline().fit(train).predict(test, dataset, "test")


def test_keyword_on_stacksample_scores(built: Path) -> None:
    train, test = splits(built, "stacksample")
    predictions = KeywordBaseline().fit(train).predict(test, "stacksample", "test")
    report = multilabel_report(
        test.team, predictions.team_probs, test.lead, predictions.lead_probs, test.labels
    )
    assert 0.0 <= report["micro_f1"] <= 1.0 and report["lead_rows"] == len(test)


def test_tfidf_learns_a_separable_task() -> None:
    labels = ("alpha", "beta")
    texts = ["red apple pie"] * 10 + ["blue ocean wave"] * 10
    team = np.array([[1, 0]] * 10 + [[0, 1]] * 10)
    split = LabelledSplit(
        ids=np.array([f"r{i}" for i in range(20)]),
        texts=texts,
        labels=labels,
        team=team,
        lead=team.argmax(axis=1),
        out_of_scope=np.zeros(20, bool),
    )
    team_probs, lead_probs = (
        TfidfLogisticBaseline(min_df=1).fit(split).predict_probs(["red apple", "blue wave"])
    )
    assert team_probs[0].argmax() == 0 and team_probs[1].argmax() == 1
    assert np.array_equal(team_probs, lead_probs)  # single-label data: one prediction for both


def test_tfidf_multilabel_keeps_constant_labels(built: Path) -> None:
    train, test = splits(built, "stacksample")
    model = TfidfLogisticBaseline(min_df=1).fit(train)
    checker, deploy = SPECIALISTS.index("checker"), SPECIALISTS.index("deploy")
    # No train question has checker or deploy in its team: those labels get a constant 0.
    assert model.team_models[checker] == 0.0 and model.team_models[deploy] == 0.0
    team, _ = model.predict_probs(test.texts)
    assert (team[:, checker] == 0).all()


def test_clinc_out_of_scope_rows_are_not_a_class(built: Path) -> None:
    train, test = splits(built, "clinc150")
    assert "oos" not in train.labels and train.out_of_scope.sum() == 1
    predictions = TfidfLogisticBaseline(min_df=1).fit(train).predict(test, "clinc150", "test")
    predicted = single_label_predictions(predictions.lead_probs, oos_threshold=0.99)
    result = clinc_metrics(test.lead, test.out_of_scope, predicted)
    assert result["out_of_scope_rows"] == 2 and result["out_of_scope_recall"] == 1.0
