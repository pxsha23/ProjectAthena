"""Sweeps skip finished jobs; restoring and packing results for Kaggle; the results table."""

import json
import zipfile
from pathlib import Path

import pytest

from athena_advisor.baselines import BASELINES
from athena_advisor.config import load_config
from athena_advisor.data.benchmarks import build_benchmarks
from athena_advisor.data.build import build
from athena_advisor.eval.table import results_table
from athena_advisor.kaggle import find_processed_data, pack_results, restore_data, restore_results
from athena_advisor.paths import ml_root
from athena_advisor.sweep import Job, JobResult, is_finished, load_sweep, record_path, run_sweep

FIXTURES = Path(__file__).parent / "fixtures"
SWEEPS = sorted((ml_root() / "configs" / "sweeps").glob("*.yaml"))


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("built") / "data" / "processed"
    config = load_config("configs/base.yaml", ["data.split_fractions=[0.4, 0.2, 0.2, 0.2]"])
    build(config, FIXTURES / "stacksample_tiny", out / "stacksample")
    build_benchmarks(FIXTURES / "benchmarks", out / "benchmarks", config.benchmarks)
    return out


def overrides(built: Path, results: Path) -> list[str]:
    return [
        f"data.processed_dir={built.as_posix()}",
        f"benchmarks.processed_dir={(built / 'benchmarks').as_posix()}",
        f"results_dir={results.as_posix()}",
        "baselines.tfidf_min_df=1",
    ]


def write_sweep(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


# ---------------------------------------------------------------- sweep files


def test_sweep_files_expand_to_the_planned_jobs() -> None:
    counts = {path.stem: len(load_sweep(path)[1]) for path in SWEEPS}
    assert counts == {"main": 5, "ablations": 25, "baselines": 8, "benchmarks": 44}
    for path in SWEEPS:
        for job in load_sweep(path)[1]:
            assert (ml_root() / job.config).is_file(), job.config
            assert job.baseline is None or job.baseline in BASELINES


def test_ablation_sweep_covers_every_ablation() -> None:
    conditions = {load_config(job.config).condition for job in load_sweep("configs/sweeps/ablations.yaml")[1]}
    assert conditions == {"plain", "no_film", "no_label_attention", "no_coactivation", "no_contrastive"}


def test_bad_job_groups_are_rejected(tmp_path: Path) -> None:
    both = write_sweep(
        tmp_path / "a.yaml",
        "jobs:\n  - {train: x.yaml, baseline: prior, datasets: [stacksample], seeds: [0]}\n",
    )
    with pytest.raises(ValueError, match="exactly one"):
        load_sweep(both)
    unknown = write_sweep(
        tmp_path / "b.yaml", "jobs:\n  - {baseline: prior, datasets: [imagenet], seeds: [0]}\n"
    )
    with pytest.raises(ValueError, match="Unknown dataset"):
        load_sweep(unknown)


# ---------------------------------------------------------------- skipping finished jobs


def test_finished_jobs_are_skipped(built: Path, tmp_path: Path) -> None:
    sweep = write_sweep(
        tmp_path / "s.yaml",
        "name: t\njobs:\n"
        "  - {train: configs/experiments/full.yaml, datasets: [stacksample], seeds: [0, 1]}\n"
        "  - {baseline: prior, datasets: [stacksample], seeds: [0]}\n",
    )
    sets = overrides(built, tmp_path / "results")
    # Pretend seed 0 of the training job has already finished in an earlier session.
    config = load_config("configs/experiments/full.yaml", sets)
    done = record_path(Job("train", "configs/experiments/full.yaml", "stacksample", 0), config)
    assert done == tmp_path / "results" / "ablations_stacksample" / "full" / "0.json"
    done.parent.mkdir(parents=True)
    done.write_text("{}", encoding="utf-8")

    ran: list[Job] = []

    def fake_runner(job: Job, config) -> JobResult:  # type: ignore[no-untyped-def]
        ran.append(job)
        return JobResult(job, "done")

    results = run_sweep(sweep, sets, runner=fake_runner, log=lambda *_: None)
    assert [r.status for r in results] == ["skipped", "done", "done"]
    assert [(j.kind, j.seed) for j in ran] == [("train", 1), ("baseline", 0)]


def test_real_baseline_sweep_continues_where_it_stopped(built: Path, tmp_path: Path) -> None:
    sweep = write_sweep(
        tmp_path / "s.yaml",
        "jobs:\n"
        "  - {baseline: prior, datasets: [stacksample, clinc150], seeds: [0]}\n"
        "  - {baseline: keyword, datasets: [mixatis], seeds: [0]}\n",
    )
    sets = overrides(built, tmp_path / "results")
    first = run_sweep(sweep, sets, log=lambda *_: None)
    assert [r.status for r in first] == ["done", "done", "not_applicable"]
    second = run_sweep(sweep, sets, log=lambda *_: None)
    assert [r.status for r in second] == ["skipped", "skipped", "skipped"]  # not applicable counts as done


def test_time_budget_and_failures(built: Path, tmp_path: Path) -> None:
    sweep = write_sweep(
        tmp_path / "s.yaml", "jobs:\n  - {baseline: prior, datasets: [stacksample], seeds: [0, 1]}\n"
    )
    sets = overrides(built, tmp_path / "results")
    out_of_time = run_sweep(sweep, sets, time_budget_hours=-1, log=lambda *_: None)
    assert [r.status for r in out_of_time] == ["out_of_time", "out_of_time"]

    def broken(job: Job, config) -> JobResult:  # type: ignore[no-untyped-def]
        if job.seed == 0:
            raise RuntimeError("GPU fell over")
        return JobResult(job, "done")

    results = run_sweep(sweep, sets, runner=broken, log=lambda *_: None)
    assert [r.status for r in results] == ["failed", "done"]  # one failure does not stop the sweep
    assert "GPU fell over" in results[0].message


def test_record_path_matches_the_trainer(built: Path, tmp_path: Path, tiny_tokenizer, make_tiny_bert) -> None:  # type: ignore[no-untyped-def]
    from athena_advisor.train.trainer import train_run

    sets = [
        *overrides(built, tmp_path),
        "train.epochs=1",
        "train.batch_size=2",
        "train.device=cpu",
        "data.max_length=32",
    ]
    config = load_config("configs/experiments/plain.yaml", sets)
    result = train_run(config, "stacksample", 3, tokenizer=tiny_tokenizer, encoder_model=make_tiny_bert())
    job = Job("train", "configs/experiments/plain.yaml", "stacksample", 3)
    assert record_path(job, config) == result.record and is_finished(job, config)


# ---------------------------------------------------------------- Kaggle inputs and outputs


def test_restore_data_from_the_zip(built: Path, tmp_path: Path) -> None:
    inputs = tmp_path / "input" / "notebook-01-output"
    inputs.mkdir(parents=True)
    with zipfile.ZipFile(inputs / "athena_data.zip", "w") as archive:
        for file in built.rglob("*"):
            if file.is_file():
                archive.write(file, ("data/processed" / file.relative_to(built)).as_posix())
    assert find_processed_data(tmp_path / "input") == inputs / "athena_data.zip"
    target = restore_data(tmp_path / "input", tmp_path / "ml")
    assert (target / "stacksample" / "train.parquet").is_file()
    assert (target / "benchmarks" / "clinc150" / "info.json").is_file()


def test_restore_data_from_an_unzipped_folder(built: Path, tmp_path: Path) -> None:
    import shutil

    shutil.copytree(built, tmp_path / "input" / "some" / "data" / "processed")
    assert find_processed_data(tmp_path / "input") == tmp_path / "input" / "some" / "data" / "processed"
    target = restore_data(tmp_path / "input", tmp_path / "ml")
    assert (target / "benchmarks" / "nlbse" / "test.parquet").is_file()
    with pytest.raises(FileNotFoundError, match="notebook 01"):
        restore_data(tmp_path / "empty", tmp_path / "ml2")


def test_results_round_trip_without_checkpoints(tmp_path: Path) -> None:
    ml = tmp_path / "ml"
    record = ml / "results" / "ablations_stacksample" / "full" / "0.json"
    checkpoint = ml / "results" / "runs" / "ablations" / "full" / "stacksample" / "seed_0" / "last.pt"
    log = checkpoint.with_name("train_log.csv")
    for file, text in ((record, "{}"), (checkpoint, "weights"), (log, "epoch\n0\n")):
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8")

    zip_path, count = pack_results(ml, tmp_path / "working" / "athena_results_main.zip")
    names = zipfile.ZipFile(zip_path).namelist()
    assert count == 2 and "results/ablations_stacksample/full/0.json" in names
    assert not any(name.endswith(".pt") for name in names)

    # A new session: the zip is an input; existing files are never overwritten.
    fresh = tmp_path / "fresh"
    (fresh / "results" / "ablations_stacksample" / "full").mkdir(parents=True)
    (fresh / "results" / "ablations_stacksample" / "full" / "0.json").write_text(
        '{"newer": 1}', encoding="utf-8"
    )
    assert restore_results(tmp_path / "working", fresh) == 1  # only the log: the record already exists
    kept = json.loads(
        (fresh / "results" / "ablations_stacksample" / "full" / "0.json").read_text(encoding="utf-8")
    )
    assert kept == {"newer": 1}


def test_results_table(tmp_path: Path) -> None:
    for seed, f1 in ((0, 0.6), (1, 0.8)):
        path = tmp_path / "ablations_stacksample" / "full" / f"{seed}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"metrics": {"test": {"micro_f1": f1, "macro_f1": 0.5, "lead_accuracy": None}}})
        )
    (tmp_path / "baselines_mixatis" / "keyword").mkdir(parents=True)
    (tmp_path / "baselines_mixatis" / "keyword" / "not_applicable.json").write_text("{}")
    table = results_table(tmp_path)
    assert "ablations_stacksample  full" in table and "0.700 ± 0.141" in table and "n/a" in table
    assert "keyword" not in table
    assert results_table(tmp_path / "nothing").startswith("No run records")
