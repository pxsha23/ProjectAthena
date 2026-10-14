"""Sweeps: run a list of training and baseline jobs, skipping every job that already has a run record.

A sweep file (configs/sweeps/*.yaml) lists job groups; each group expands to one job per dataset and seed:

    name: main
    jobs:
      - train: configs/experiments/full.yaml     # trains the Advisor model with this config
        datasets: [stacksample]
        seeds: [0, 1, 2, 3, 4]
      - baseline: tfidf_lr                       # runs a baseline (config defaults to configs/base.yaml)
        datasets: [stacksample]
        seeds: [0]

Because finished jobs are skipped, the same sweep can be started again in a new Kaggle session (with the
earlier results restored) and it continues where it stopped. A time budget stops starting new jobs before
the session limit.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml

from athena_advisor.config import AdvisorConfig, load_config
from athena_advisor.eval.splits import DATASETS
from athena_advisor.paths import resolve
from athena_advisor.run_metadata import result_path

BASE_CONFIG = "configs/base.yaml"


@dataclass(frozen=True)
class Job:
    kind: str  # "train" or "baseline"
    config: str
    dataset: str
    seed: int
    baseline: str | None = None

    @property
    def label(self) -> str:
        what = self.baseline if self.kind == "baseline" else Path(self.config).stem
        return f"{self.kind} {what} / {self.dataset} / seed {self.seed}"


@dataclass
class JobResult:
    job: Job
    status: str  # done, skipped, not_applicable, stopped, out_of_time, failed
    message: str = ""


def load_sweep(path: str | Path) -> tuple[str, list[Job]]:
    data = yaml.safe_load(resolve(path).read_text(encoding="utf-8"))
    jobs: list[Job] = []
    for group in data["jobs"]:
        unknown = set(group) - {"train", "baseline", "config", "datasets", "seeds"}
        if unknown or ("train" in group) == ("baseline" in group):
            raise ValueError(f"Each job group needs exactly one of 'train' or 'baseline': {group}")
        for dataset in group["datasets"]:
            if dataset not in DATASETS:
                raise ValueError(f"Unknown dataset {dataset!r}")
            for seed in group["seeds"]:
                if "train" in group:
                    jobs.append(Job("train", group["train"], dataset, int(seed)))
                else:
                    jobs.append(
                        Job(
                            "baseline",
                            group.get("config", BASE_CONFIG),
                            dataset,
                            int(seed),
                            group["baseline"],
                        )
                    )
    return data.get("name", Path(path).stem), jobs


def job_config(job: Job, overrides: list[str]) -> AdvisorConfig:
    return load_config(job.config, overrides)


def record_path(job: Job, config: AdvisorConfig) -> Path:
    """Where the job's run record is written (the same rule the trainer and run_baseline use)."""
    if job.kind == "train":
        return result_path(replace(config, experiment=f"{config.experiment}_{job.dataset}"), job.seed)
    return result_path(
        replace(config, experiment=f"baselines_{job.dataset}", condition=job.baseline), job.seed
    )


def is_finished(job: Job, config: AdvisorConfig) -> bool:
    path = record_path(job, config)
    # A baseline that does not apply to a dataset is finished too: it will never produce a record.
    return path.exists() or (job.kind == "baseline" and (path.parent / "not_applicable.json").exists())


def _run_job(job: Job, config: AdvisorConfig) -> JobResult:
    if job.kind == "baseline":
        from athena_advisor.baselines.run import run_baseline

        outcome = run_baseline(job.baseline, job.dataset, config, job.seed)  # type: ignore[arg-type]
        return JobResult(job, outcome.status, outcome.message)
    from athena_advisor.train.trainer import train_run

    result = train_run(config, job.dataset, job.seed)
    if result is None:
        return JobResult(job, "stopped", "stopped before the end; run the sweep again to resume")
    return JobResult(job, "done", f"best epoch {result.state.best_epoch}, record {result.record}")


def run_sweep(
    path: str | Path,
    overrides: list[str] | None = None,
    time_budget_hours: float | None = None,
    runner: Callable[[Job, AdvisorConfig], JobResult] = _run_job,
    log: Callable[[str], Any] = print,
) -> list[JobResult]:
    """Runs every unfinished job in order. With a time budget, no new job starts once it is used up."""
    overrides = overrides or []
    name, jobs = load_sweep(path)
    start = time.monotonic()
    results: list[JobResult] = []
    log(f"Sweep {name}: {len(jobs)} jobs")
    for number, job in enumerate(jobs, start=1):
        prefix = f"[{number}/{len(jobs)}] {job.label}"
        config = job_config(job, overrides)
        if is_finished(job, config):
            results.append(JobResult(job, "skipped", "already finished"))
            log(f"{prefix}: already finished, skipping")
            continue
        if time_budget_hours is not None and time.monotonic() - start > time_budget_hours * 3600:
            results.append(JobResult(job, "out_of_time", "time budget used up"))
            log(f"{prefix}: time budget used up, not started")
            continue
        log(f"{prefix}: running")
        try:
            result = runner(job, config)
        except Exception as exc:  # one broken job must not stop the rest of the sweep
            result = JobResult(job, "failed", f"{type(exc).__name__}: {exc}")
        results.append(result)
        log(f"{prefix}: {result.status} {result.message}")
    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    log(f"Sweep {name} summary: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    return results
