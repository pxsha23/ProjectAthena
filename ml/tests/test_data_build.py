import json
from pathlib import Path

import pandas as pd
import pytest

from athena_advisor.config import SPLITS, load_config
from athena_advisor.data.build import build, load_split
from athena_advisor.data.data_card import write_data_card
from athena_advisor.data.text import build_text
from athena_advisor.run_metadata import file_sha256

FRACTIONS = "data.split_fractions=[0.4, 0.2, 0.2, 0.2]"


@pytest.fixture
def raw_dir(fixtures_dir: Path) -> Path:
    return fixtures_dir / "stacksample_tiny"


def run(raw_dir: Path, out: Path, *overrides: str) -> dict:
    return build(load_config("configs/base.yaml", [FRACTIONS, *overrides]), raw_dir, out)


def all_rows(out: Path) -> pd.DataFrame:
    return pd.concat([load_split(out, s).assign(split=s) for s in SPLITS], ignore_index=True)


def test_build_writes_every_split_with_hashes(raw_dir: Path, tmp_path: Path) -> None:
    info = run(raw_dir, tmp_path)
    assert (info["questions_read"], info["questions_kept"], info["dropped_no_mapped_tag"]) == (8, 7, 1)
    for split in SPLITS:
        parquet = tmp_path / f"{split}.parquet"
        digest = (tmp_path / f"{split}.parquet.sha256").read_text(encoding="utf-8").split()[0]
        assert digest == file_sha256(parquet) == info["files"][split]["sha256"]
    saved = json.loads((tmp_path / "build_info.json").read_text(encoding="utf-8"))
    assert saved == info
    assert info["tag_map"]["sha256"] == file_sha256("configs/tag_map.yaml")
    assert info["context_schema_version"] == "1.0" and info["context_dim"] == 43


def test_dropped_question_and_columns(raw_dir: Path, tmp_path: Path) -> None:
    run(raw_dir, tmp_path)
    rows = all_rows(tmp_path)
    assert 105 not in set(rows["id"])
    assert list(load_split(tmp_path, "train").columns) == [
        "id",
        "creation_date",
        "text",
        "context",
        "team",
        "lead",
    ]
    assert all(len(vector) == 43 and vector[0] == 1.0 for vector in rows["context"])


def test_splits_are_chronological(raw_dir: Path, tmp_path: Path) -> None:
    info = run(raw_dir, tmp_path)
    frames = [load_split(tmp_path, s) for s in SPLITS]
    assert [len(f) for f in frames] == [3, 1, 2, 1] == [info["split_counts"][s] for s in SPLITS]
    for earlier, later in zip(frames, frames[1:], strict=False):
        assert earlier["creation_date"].max() < later["creation_date"].min()
    for frame in frames:
        assert frame["creation_date"].is_monotonic_increasing


def test_text_comes_only_from_title_and_body(raw_dir: Path, tmp_path: Path) -> None:
    run(raw_dir, tmp_path)
    questions = pd.read_csv(raw_dir / "Questions.csv").set_index("Id")
    tags = pd.read_csv(raw_dir / "Tags.csv")
    for row in all_rows(tmp_path).itertuples():
        assert row.text == build_text(questions.at[row.id, "Title"], questions.at[row.id, "Body"])
    # Tags that never appear in a question's title or body never appear in its text.
    text_106 = all_rows(tmp_path).set_index("id").at[106, "text"].lower()
    assert set(tags[tags["Id"] == 106]["Tag"]) == {"nginx", "deployment"} and "deployment" not in text_106


def test_labels_in_the_output(raw_dir: Path, tmp_path: Path) -> None:
    run(raw_dir, tmp_path)
    rows = all_rows(tmp_path).set_index("id")
    assert list(rows.at[103, "team"]) == ["code", "eva"] and rows.at[103, "lead"] == "eva"
    assert list(rows.at[101, "team"]) == ["blueprint", "code"] and rows.at[101, "lead"] == "blueprint"


def test_output_is_deterministic(raw_dir: Path, tmp_path: Path) -> None:
    first = run(raw_dir, tmp_path / "a")
    second = run(raw_dir, tmp_path / "b")
    assert {s: first["files"][s]["sha256"] for s in SPLITS} == {
        s: second["files"][s]["sha256"] for s in SPLITS
    }


def test_train_is_sampled_but_evaluation_splits_stay_complete(raw_dir: Path, tmp_path: Path) -> None:
    info = run(raw_dir, tmp_path, "data.train_max=2")
    assert info["split_counts_before_sampling"]["train"] == 3 and info["split_counts"]["train"] == 2
    for split in SPLITS[1:]:
        assert info["split_counts"][split] == info["split_counts_before_sampling"][split]
    again = run(raw_dir, tmp_path / "again", "data.train_max=2")
    assert again["files"]["train"]["sha256"] == info["files"]["train"]["sha256"]  # same seed, same sample
    other_seed = run(raw_dir, tmp_path / "seed", "data.train_max=1", "data.sample_seed=5")
    assert other_seed["split_counts"]["train"] == 1


def test_sample_size_reads_only_the_first_questions(raw_dir: Path, tmp_path: Path) -> None:
    info = run(raw_dir, tmp_path, "data.sample_size=4", "data.chunk_size=3")
    assert info["questions_read"] == 4 and info["questions_kept"] == 4


def test_bad_split_fractions_are_rejected(raw_dir: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="sum to 1"):
        run(raw_dir, tmp_path, "data.split_fractions=[0.5, 0.5, 0.5, 0.5]")


def test_data_card(raw_dir: Path, tmp_path: Path) -> None:
    run(raw_dir, tmp_path)
    card = write_data_card(tmp_path).read_text(encoding="utf-8")
    assert "CC-BY-SA 3.0" in card and "Other (specified in description)" in card
    assert "https://www.kaggle.com/datasets/stackoverflow/stacksample" in card
    assert "Kept (at least one mapped tag): 7 (87.5%)" in card
    assert "| eva | 1 | 0 | 0 | 0 |" in card  # one eva question in train (103)
    assert "`unit-testing` | eva |" in card and "`python` | code | yes |" in card
    assert "has_error_trace" in card and "checker, deploy, eva, blueprint, code" in card
