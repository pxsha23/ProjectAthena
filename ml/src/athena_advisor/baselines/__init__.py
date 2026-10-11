"""Baselines with one interface: fit on train, predict a split into the saved Predictions format."""

from athena_advisor.baselines.base import Baseline, NotApplicable
from athena_advisor.baselines.keyword import KeywordBaseline
from athena_advisor.baselines.prior import PriorBaseline
from athena_advisor.baselines.setfit_baseline import SetFitBaseline
from athena_advisor.baselines.tfidf_lr import TfidfLogisticBaseline

BASELINES: dict[str, type[Baseline]] = {
    "prior": PriorBaseline,
    "keyword": KeywordBaseline,
    "tfidf_lr": TfidfLogisticBaseline,
    "setfit": SetFitBaseline,
}

__all__ = [
    "BASELINES",
    "Baseline",
    "KeywordBaseline",
    "NotApplicable",
    "PriorBaseline",
    "SetFitBaseline",
    "TfidfLogisticBaseline",
]
