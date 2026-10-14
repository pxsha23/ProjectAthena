"""Runs one baseline on one dataset for one seed: train, predict the evaluation splits, record metrics.

Evaluation splits are val_tune, val_cal and test for every dataset:
- StackSample has them already.
- A benchmark has one official dev split. It is cut into val_tune and val_cal halves with the fixed
  benchmarks seed, so every model and seed sees the same halves.

Outputs:
    results/predictions/<baseline>/<dataset>/<split>/<seed>.npz        one per evaluation split
    results/baselines_<dataset>/<baseline>/<seed>.json                  run record with metrics
    results/baselines_<dataset>/<baseline>/not_applicable.json          when the baseline does not apply
A run whose record and predictions already exist is skipped unless force=True.
"""

import json
from dataclasses import dataclass, field, replace
from pathlib import Path

from athena_advisor.baselines import BASELINES, Baseline, NotApplicable
from athena_advisor.baselines.keyword import KeywordBaseline
from athena_advisor.baselines.setfit_baseline import SetFitBaseline
from athena_advisor.baselines.tfidf_lr import TfidfLogisticBaseline
from athena_advisor.config import AdvisorConfig
from athena_advisor.eval.predictions import Predictions, predictions_path
from athena_advisor.eval.report import dataset_metrics
from athena_advisor.eval.splits import EVAL_SPLITS, dataset_folder, load_dataset
from athena_advisor.run_metadata import result_path, write_run_record
from athena_advisor.seed import set_seed


@dataclass
class RunOutcome:
    status: str  # "done", "skipped" (already done) or "not_applicable"
    message: str
    record: Path | None = None
    predictions: dict[str, Path] = field(default_factory=dict)


def make_baseline(name: str, config: AdvisorConfig) -> Baseline:
    settings = config.baselines
    if name == "tfidf_lr":
        return TfidfLogisticBaseline(min_df=settings.tfidf_min_df, max_features=settings.tfidf_max_features)
    if name == "setfit":
        return SetFitBaseline(
            model=settings.setfit_model,
            train_max=settings.setfit_train_max,
            num_iterations=settings.setfit_num_iterations,
            epochs=settings.setfit_epochs,
            batch_size=settings.setfit_batch_size,
        )
    if name == "keyword":
        return KeywordBaseline(config.data.tag_map)
    if name in BASELINES:
        return BASELINES[name]()
    raise ValueError(f"Unknown baseline {name!r}; choose from {sorted(BASELINES)}")


def run_baseline(
    name: str, dataset: str, config: AdvisorConfig, seed: int, force: bool = False
) -> RunOutcome:
    config = replace(config, experiment=f"baselines_{dataset}", condition=name)
    baseline = make_baseline(name, config)
    record_path = result_path(config, seed)
    paths = {s: predictions_path(config.results_dir, name, dataset, s, seed) for s in EVAL_SPLITS}

    try:
        baseline.applies_to(dataset)
    except NotApplicable as exc:
        note = record_path.parent / "not_applicable.json"
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text(
            json.dumps({"baseline": name, "dataset": dataset, "reason": str(exc)}, indent=2) + "\n",
            encoding="utf-8",
        )
        return RunOutcome("not_applicable", f"Not applicable: {exc}", note)

    if not force and record_path.exists() and all(p.exists() for p in paths.values()):
        return RunOutcome(
            "skipped", f"Already done: {record_path} (use --force to run again)", record_path, paths
        )

    splits = load_dataset(config, dataset)
    set_seed(seed)
    baseline.fit(splits["train"], seed=seed)
    metrics: dict[str, object] = {"train_rows": len(splits["train"])}
    if hasattr(baseline, "train_rows"):
        metrics["train_rows_used"] = baseline.train_rows  # SetFit trains on a sample
    if hasattr(baseline, "contrastive"):
        metrics["contrastive_training"] = baseline.contrastive  # False: head only (sample too small)
    for split in EVAL_SPLITS:
        predictions = baseline.predict(splits[split], dataset, split, seed)
        predictions.save(paths[split])
        metrics[split] = dataset_metrics(
            dataset, splits[split], Predictions.load(paths[split]), config.baselines.report_threshold
        )
    folder = dataset_folder(config, dataset)
    record = write_run_record(config, seed, metrics, sorted(folder.glob("*.parquet")), overwrite=True)
    return RunOutcome("done", f"Wrote {record}", record, paths)
