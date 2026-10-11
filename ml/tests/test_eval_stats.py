import numpy as np
import pytest

from athena_advisor.eval import stats
from athena_advisor.eval.metrics import micro_f1


def accuracy(correct: np.ndarray) -> float:
    return float(np.mean(correct))


def test_bootstrap_interval_is_seeded_and_contains_the_point() -> None:
    correct = np.array([1] * 70 + [0] * 30)
    first = stats.bootstrap_ci(accuracy, correct, seed=0)
    assert first == stats.bootstrap_ci(accuracy, correct, seed=0)
    assert first.point == 0.7 and first.low < 0.7 < first.high
    assert stats.bootstrap_ci(accuracy, correct, seed=1) != first
    # More data, narrower interval.
    big = stats.bootstrap_ci(accuracy, np.tile(correct, 20), seed=0)
    assert big.high - big.low < first.high - first.low


def test_bootstrap_with_a_two_array_metric() -> None:
    rng = np.random.default_rng(0)
    y_true = rng.integers(0, 2, size=(200, 4))
    interval = stats.bootstrap_ci(micro_f1, y_true, y_true, n_resamples=200)
    assert interval.point == interval.low == interval.high == 1.0
    with pytest.raises(ValueError, match="same number of rows"):
        stats.bootstrap_ci(micro_f1, y_true, y_true[:10])


def test_paired_bootstrap() -> None:
    rng = np.random.default_rng(1)
    a = rng.random(300) < 0.6
    same = stats.paired_bootstrap(accuracy, [a], [a])
    assert same.difference == 0.0 and same.p_value == 1.0
    better = a | (rng.random(300) < 0.5)  # b is right wherever a is, and more often
    result = stats.paired_bootstrap(accuracy, [a], [better])
    assert result.difference > 0 and result.low > 0 and result.p_value < 0.01
    assert stats.paired_bootstrap(accuracy, [a], [better]) == result  # seeded


def test_mcnemar_exact_and_chi_square() -> None:
    a = np.array([True] * 10 + [False] * 5)
    b = np.array([False] * 10 + [False] * 5)
    exact = stats.mcnemar(a, b)
    assert (exact.only_a_correct, exact.only_b_correct, exact.exact) == (10, 0, True)
    assert exact.p_value == pytest.approx(2 * 0.5**10)

    a = np.array([True] * 40 + [False] * 20 + [True] * 100)
    b = np.array([False] * 40 + [True] * 20 + [True] * 100)
    large = stats.mcnemar(a, b)
    assert not large.exact and large.statistic == pytest.approx((abs(40 - 20) - 1) ** 2 / 60)
    assert 0.01 < large.p_value < 0.05

    tied = stats.mcnemar(np.ones(5, bool), np.ones(5, bool))
    assert tied.p_value == 1.0


def test_across_seeds() -> None:
    summary = stats.across_seeds([1.0, 2.0, 3.0])
    assert (summary.mean, summary.std, summary.n) == (2.0, 1.0, 3)
    assert stats.across_seeds([0.5]).std == 0.0
    assert stats.format_mean_std(summary) == "2.000 ± 1.000"
    with pytest.raises(ValueError):
        stats.across_seeds([])
