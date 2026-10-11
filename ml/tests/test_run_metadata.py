import hashlib
import json
from pathlib import Path

import pytest

from athena_advisor.config import load_config
from athena_advisor.run_metadata import file_sha256, result_path, write_run_record


def test_file_hash_matches_hashlib(fixtures_dir: Path) -> None:
    path = fixtures_dir / "stacksample_tiny" / "Tags.csv"
    assert file_sha256(path) == hashlib.sha256(path.read_bytes()).hexdigest()


def test_run_record_has_everything_needed_to_repeat_the_run(fixtures_dir: Path, results_dir: str) -> None:
    config = load_config("configs/experiments/ablation_no_film.yaml", [f"results_dir={results_dir}"])
    folder = fixtures_dir / "stacksample_tiny"
    data = [folder / "Questions.csv", folder / "Tags.csv"]

    path = write_run_record(config, seed=3, metrics={"micro_f1": 0.5}, data_files=data)

    assert path == Path(results_dir) / "ablations" / "no_film" / "3.json" == result_path(config, 3)
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["seed"] == 3 and record["metrics"] == {"micro_f1": 0.5}
    meta = record["metadata"]
    assert meta["config"]["model"]["use_film"] is False
    assert meta["config_fingerprint"] == config.fingerprint()
    assert set(meta["data_hashes"].values()) == {file_sha256(p) for p in data}
    assert len(meta["git"]["commit"]) == 40 and isinstance(meta["git"]["dirty"], bool)
    assert meta["hardware"]["torch"] and "cuda_available" in meta["hardware"]
    assert meta["timestamp_utc"].endswith("+00:00")


def test_existing_records_are_not_overwritten_by_accident(results_dir: str) -> None:
    config = load_config(overrides=[f"results_dir={results_dir}"])
    write_run_record(config, seed=0, metrics={"a": 1})
    with pytest.raises(FileExistsError):
        write_run_record(config, seed=0, metrics={"a": 2})
    path = write_run_record(config, seed=0, metrics={"a": 2}, overwrite=True)
    assert json.loads(path.read_text(encoding="utf-8"))["metrics"] == {"a": 2}
