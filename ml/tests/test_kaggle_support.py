"""The helpers the Kaggle notebook relies on, and the notebook itself."""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from athena_advisor.config import load_config
from athena_advisor.data.benchmarks import build_benchmarks
from athena_advisor.data.build import build
from athena_advisor.data.locate import find_stacksample_dir
from athena_advisor.data.summary import summarize
from athena_advisor.environment import REQUIRED_MODULES, environment_report, missing_modules
from athena_advisor.paths import ml_root

# ---------------------------------------------------------------- locating the dataset


def test_finds_stacksample_at_any_depth(fixtures_dir: Path, tmp_path: Path) -> None:
    nested = tmp_path / "input" / "datasets" / "stackoverflow" / "stacksample" / "versions" / "1"
    shutil.copytree(fixtures_dir / "stacksample_tiny", nested)
    (tmp_path / "input" / "other").mkdir()
    (tmp_path / "input" / "other" / "Questions.csv").write_text("Id\n", encoding="utf-8")  # no Tags.csv
    assert find_stacksample_dir(tmp_path / "input") == nested


def test_shortest_match_wins(fixtures_dir: Path, tmp_path: Path) -> None:
    shallow, deep = tmp_path / "b", tmp_path / "a" / "deeper"
    shutil.copytree(fixtures_dir / "stacksample_tiny", shallow)
    shutil.copytree(fixtures_dir / "stacksample_tiny", deep)
    assert find_stacksample_dir(tmp_path) == shallow


def test_missing_dataset_is_explained(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="stackoverflow/stacksample"):
        find_stacksample_dir(tmp_path)
    with pytest.raises(FileNotFoundError, match="does not exist"):
        find_stacksample_dir(tmp_path / "nope")


# ---------------------------------------------------------------- summary and environment


def test_summary_covers_every_build(fixtures_dir: Path, tmp_path: Path) -> None:
    config = load_config("configs/base.yaml", ["data.split_fractions=[0.4, 0.2, 0.2, 0.2]"])
    build(config, fixtures_dir / "stacksample_tiny", tmp_path / "stacksample")
    build_benchmarks(fixtures_dir / "benchmarks", tmp_path / "benchmarks", config.benchmarks)
    text = summarize(tmp_path)
    assert "read 8, kept 7 (87.5%), dropped 1" in text
    for name in ("mixatis", "mixsnips", "clinc150", "nlbse"):
        assert f"{name} (benchmarks/{name})" in text
    assert "4 out of scope" not in text and "2 out of scope" in text  # CLINC test has 2 out-of-scope rows
    assert summarize(tmp_path / "empty").startswith("Nothing built")


def test_environment_report() -> None:
    report = environment_report()
    assert report["missing_modules"] == [] and report["torch"]
    assert "cuda_available" in report
    assert missing_modules(("pandas", "a_module_that_does_not_exist")) == ["a_module_that_does_not_exist"]
    assert "sentence_transformers" in REQUIRED_MODULES


def test_build_script_finds_the_input_folder(fixtures_dir: Path, tmp_path: Path) -> None:
    shutil.copytree(fixtures_dir / "stacksample_tiny", tmp_path / "input" / "stacksample")
    result = subprocess.run(
        [
            sys.executable,
            str(ml_root() / "scripts" / "build_stacksample.py"),
            "--input-root",
            str(tmp_path / "input"),
            "--out",
            str(tmp_path / "out"),
            "--set",
            "data.split_fractions=[0.4, 0.2, 0.2, 0.2]",
        ],
        capture_output=True,
        text=True,
        cwd=ml_root(),
    )
    assert result.returncode == 0, result.stderr
    assert "Found StackSample in" in result.stdout
    assert (tmp_path / "out" / "DATA_CARD.md").is_file()


# ---------------------------------------------------------------- the notebooks

NOTEBOOKS = sorted((ml_root() / "notebooks").glob("*.ipynb"))
# Scripts each notebook must call (the training notebooks all follow the same steps).
REQUIRED = {
    "01_prepare_data": {
        "build_stacksample.py",
        "download_benchmarks.py",
        "check_environment.py",
        "summarize_data.py",
    },
    "02_train_main": {"kaggle_restore.py", "sweep.py", "results_table.py", "pack_results.py"},
    "03_ablations": {"kaggle_restore.py", "sweep.py", "results_table.py", "pack_results.py"},
    "04_baselines": {"kaggle_restore.py", "sweep.py", "results_table.py", "pack_results.py"},
    "05_benchmarks": {"kaggle_restore.py", "sweep.py", "results_table.py", "pack_results.py"},
}


def code_cells(path: Path) -> list[str]:
    notebook = json.loads(path.read_text(encoding="utf-8"))
    assert notebook["nbformat"] == 4
    cells = [c for c in notebook["cells"] if c["cell_type"] == "code"]
    assert all(c["outputs"] == [] and c["execution_count"] is None for c in cells), "save without outputs"
    return ["".join(c["source"]) for c in cells]


def test_every_notebook_is_covered() -> None:
    assert {p.stem for p in NOTEBOOKS} == set(REQUIRED)


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.stem)
def test_notebook_only_calls_scripts_and_configs_that_exist(path: Path) -> None:
    sources = code_cells(path)
    called = {m for source in sources for m in re.findall(r"scripts/(\w+\.py)", source)}
    assert REQUIRED[path.stem] <= called
    for script in called:
        assert (ml_root() / "scripts" / script).is_file(), script
    for config in {m for source in sources for m in re.findall(r"(configs/[\w/]+\.yaml)", source)}:
        assert (ml_root() / config).is_file(), config


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.stem)
def test_notebook_python_compiles(path: Path) -> None:
    for source in code_cells(path):
        # Shell (!) and magic (%) lines are IPython, not Python.
        python = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith(("!", "%")))
        compile(python, f"<{path.stem} cell>", "exec")


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.stem)
def test_notebook_never_prints_the_token(path: Path) -> None:
    joined = "\n".join(code_cells(path))
    assert "GITHUB_TOKEN" in joined and "capture_output=True" in joined
    assert not re.search(r"print\([^)]*token", joined)
    assert 'remote", "set-url"' in joined  # the token is removed from the saved remote
