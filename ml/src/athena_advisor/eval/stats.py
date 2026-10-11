"""Statistics for the papers: confidence intervals, paired tests and seed summaries.

Every resampling method takes a seed, so the reported intervals and p-values can be reproduced exactly.
A "metric" here is any function from arrays (rows first) to one number, for example
    lambda t, p: micro_f1(t, p)
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
from scipy import stats

N_RESAMPLES = 1000
CONFIDENCE = 0.95

Metric = Callable[..., float]


@dataclass(frozen=True)
class Interval:
    point: float
    low: float
    high: float


@dataclass(frozen=True)
class PairedResult:
    difference: float  # metric(b) - metric(a) on the full data
    low: float
    high: float
    p_value: float


def _n_rows(arrays: Sequence[np.ndarray]) -> int:
    sizes = {len(a) for a in arrays}
    if len(sizes) != 1:
        raise ValueError("All arrays must have the same number of rows")
    return sizes.pop()


def bootstrap_ci(
    metric: Metric,
    *arrays: np.ndarray,
    n_resamples: int = N_RESAMPLES,
    seed: int = 0,
    confidence: float = CONFIDENCE,
) -> Interval:
    """Percentile bootstrap: recompute the metric on rows drawn with replacement, then take the middle
    95% of the resampled values as the interval."""
    arrays = tuple(np.asarray(a) for a in arrays)
    n = _n_rows(arrays)
    rng = np.random.default_rng(seed)
    values = np.empty(n_resamples)
    for i in range(n_resamples):
        rows = rng.integers(0, n, size=n)
        values[i] = metric(*(a[rows] for a in arrays))
    tail = (1 - confidence) / 2 * 100
    low, high = np.nanpercentile(values, [tail, 100 - tail])
    return Interval(point=float(metric(*arrays)), low=float(low), high=float(high))


def paired_bootstrap(
    metric: Metric,
    arrays_a: Sequence[np.ndarray],
    arrays_b: Sequence[np.ndarray],
    n_resamples: int = N_RESAMPLES,
    seed: int = 0,
    confidence: float = CONFIDENCE,
) -> PairedResult:
    """Is system B better than system A on the same rows?

    Both systems are scored on the SAME resampled rows each time, so row difficulty cancels out. The
    two-sided p-value is twice the share of resamples where the difference falls on the other side of 0.
    """
    arrays_a = tuple(np.asarray(a) for a in arrays_a)
    arrays_b = tuple(np.asarray(b) for b in arrays_b)
    n = _n_rows((*arrays_a, *arrays_b))
    rng = np.random.default_rng(seed)
    differences = np.empty(n_resamples)
    for i in range(n_resamples):
        rows = rng.integers(0, n, size=n)
        differences[i] = metric(*(b[rows] for b in arrays_b)) - metric(*(a[rows] for a in arrays_a))
    observed = float(metric(*arrays_b) - metric(*arrays_a))
    tail = (1 - confidence) / 2 * 100
    low, high = np.percentile(differences, [tail, 100 - tail])
    p_value = min(1.0, 2 * min(float((differences <= 0).mean()), float((differences >= 0).mean())))
    return PairedResult(difference=observed, low=float(low), high=float(high), p_value=p_value)


@dataclass(frozen=True)
class McNemarResult:
    only_a_correct: int
    only_b_correct: int
    statistic: float
    p_value: float
    exact: bool


def mcnemar(correct_a: np.ndarray, correct_b: np.ndarray, exact_below: int = 25) -> McNemarResult:
    """McNemar's test for two classifiers on the same rows (used for lead accuracy).

    Only the rows where exactly one system is right carry information. With few such rows the exact
    binomial test is used; otherwise the chi-square test with continuity correction.
    """
    correct_a, correct_b = np.asarray(correct_a, bool), np.asarray(correct_b, bool)
    _n_rows((correct_a, correct_b))
    b = int((correct_a & ~correct_b).sum())
    c = int((~correct_a & correct_b).sum())
    if b + c == 0:
        return McNemarResult(b, c, 0.0, 1.0, exact=True)
    if b + c < exact_below:
        p = stats.binomtest(min(b, c), b + c, 0.5).pvalue
        return McNemarResult(b, c, float(min(b, c)), float(p), exact=True)
    statistic = (abs(b - c) - 1) ** 2 / (b + c)
    return McNemarResult(b, c, float(statistic), float(stats.chi2.sf(statistic, df=1)), exact=False)


@dataclass(frozen=True)
class SeedSummary:
    mean: float
    std: float
    n: int


def across_seeds(values: Sequence[float]) -> SeedSummary:
    """Mean and sample standard deviation (n - 1) of one metric over the seeds of a condition."""
    values = [float(v) for v in values]
    if not values:
        raise ValueError("No values to summarise")
    std = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
    return SeedSummary(mean=float(np.mean(values)), std=std, n=len(values))


def format_mean_std(summary: SeedSummary, digits: int = 3) -> str:
    return f"{summary.mean:.{digits}f} ± {summary.std:.{digits}f}" if not math.isnan(summary.mean) else "n/a"
