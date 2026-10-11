import json
import shutil
import tarfile
from pathlib import Path

import pandas as pd
import pytest

from athena_advisor.config import BenchmarksConfig
from athena_advisor.data.benchmarks import DATASETS, build_benchmarks, convert_dataset
from athena_advisor.data.benchmarks.common import BENCHMARK_SPLITS, Example
from athena_advisor.data.benchmarks.mix_intent import parse_agif
from athena_advisor.data.benchmarks.nlbse import TEST_FILE, TRAIN_FILE, issue_text
from athena_advisor.data.benchmarks.sources import AGIF_COMMIT, CLINC_COMMIT, SOURCES
from athena_advisor.run_metadata import file_sha256

CONFIG = BenchmarksConfig()


@pytest.fixture
def raw(fixtures_dir: Path) -> Path:
    return fixtures_dir / "benchmarks"


def rows(out: Path, dataset: str) -> pd.DataFrame:
    return pd.concat(
        [pd.read_parquet(out / dataset / f"{s}.parquet") for s in BENCHMARK_SPLITS], ignore_index=True
    )


# ---------------------------------------------------------------- MixATIS / MixSNIPS


def test_agif_parsing_joins_tokens_and_splits_intents() -> None:
    text = "fly O\nto O\nrome B-city\natis_flight#atis_airfare\n\nhello O\ngreet\n"
    first, second = parse_agif(text)
    assert first.tokens == ("fly", "to", "rome") and first.intents == ("atis_flight", "atis_airfare")
    assert second.intents == ("greet",)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("fly O\nto O\n\n", "without an intent"),
        ("atis_flight\n", "without any tokens"),
        ("fly O\nto O", "middle of an utterance"),
        ("fly O extra\nx\n", "expected 'token TAG'"),
    ],
)
def test_agif_parsing_rejects_broken_files(text: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_agif(text)


def test_mixatis_conversion(raw: Path) -> None:
    examples = convert_dataset("mixatis", raw, CONFIG).examples
    by_id = {e.id: e for e in examples}
    first = by_id["mixatis-train-000000"]
    assert first.text == "show me morning flights to boston and the cheapest fare"
    assert first.labels == ("atis_flight", "atis_airfare") and first.lead is None
    single = by_id["mixatis-train-000001"]
    assert single.labels == ("atis_airline",) and single.lead == "atis_airline"
    assert by_id["mixatis-train-000002"].labels == (
        "atis_ground_service",
        "atis_airport",
        "atis_abbreviation",
    )
    assert [sum(e.split == s for e in examples) for s in BENCHMARK_SPLITS] == [3, 1, 2]
    assert not any(e.out_of_scope for e in examples)


def test_mixsnips_conversion(raw: Path) -> None:
    examples = {e.id: e for e in convert_dataset("mixsnips", raw, CONFIG).examples}
    assert examples["mixsnips-train-000000"].labels == ("PlayMusic", "GetWeather")
    assert examples["mixsnips-test-000001"].labels == ("SearchCreativeWork", "PlayMusic")
    assert examples["mixsnips-test-000000"].lead == "BookRestaurant"


# ---------------------------------------------------------------- CLINC150


def test_clinc_out_of_scope_rows(raw: Path) -> None:
    examples = convert_dataset("clinc150", raw, CONFIG).examples
    oos = [e for e in examples if e.out_of_scope]
    assert len(oos) == 4
    assert all(e.labels == () and e.lead is None for e in oos)
    assert all(e.labels == (e.lead,) and e.lead != "oos" for e in examples if not e.out_of_scope)
    # val is renamed dev; out-of-scope rows join their official split.
    counts = {
        s: (sum(e.split == s and not e.out_of_scope for e in examples), sum(e.split == s for e in oos))
        for s in BENCHMARK_SPLITS
    }
    assert counts == {"train": (4, 1), "dev": (2, 1), "test": (3, 2)}


def test_clinc_rejects_a_mislabelled_row(raw: Path, tmp_path: Path) -> None:
    data = json.loads((raw / "clinc150" / "data_full.json").read_text(encoding="utf-8"))
    data["oos_test"][0][1] = "weather"
    (tmp_path / "clinc150").mkdir()
    (tmp_path / "clinc150" / "data_full.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="oos_test"):
        convert_dataset("clinc150", tmp_path, CONFIG)


# ---------------------------------------------------------------- NLBSE


def test_nlbse_labels_text_and_dev_split(raw: Path) -> None:
    conversion = convert_dataset("nlbse", raw, CONFIG)
    examples = conversion.examples
    assert {label for e in examples for label in e.labels} == {"bug", "enhancement", "question"}
    assert all(e.labels == (e.lead,) for e in examples)
    split_sizes = {s: sum(e.split == s for e in examples) for s in BENCHMARK_SPLITS}
    assert split_sizes == {"train": 9, "dev": 1, "test": 4}  # dev = round(10 * 0.1) taken from train
    by_id = {e.id: e for e in examples}
    first_train = next(e for e in examples if e.id.endswith("000000") and e.split != "test")
    assert (
        first_train.text == "Saving a note twice duplicates it Steps: 1. Create a note 2. Press save twice "
        "The note shows up two times in the list."
    )
    assert by_id["nlbse-test-000002"].text.startswith("Does it work with RAW files? I shoot in RAW, does")
    assert conversion.facts["Official test rows (all kept)"] == 4


def test_issue_text_handles_missing_parts() -> None:
    assert issue_text("Title", float("nan")) == "Title"
    assert issue_text("  A \n title ", "body\ttext") == "A title body text"


def test_nlbse_dev_split_is_seeded(raw: Path) -> None:
    def dev_ids(seed: int) -> set[str]:
        config = BenchmarksConfig(seed=seed, nlbse_dev_fraction=0.3)
        return {e.id for e in convert_dataset("nlbse", raw, config).examples if e.split == "dev"}

    assert dev_ids(0) == dev_ids(0) and len(dev_ids(0)) == 3
    assert any(dev_ids(seed) != dev_ids(0) for seed in range(1, 6))


def test_nlbse_train_cap_keeps_test_complete(raw: Path) -> None:
    config = BenchmarksConfig(nlbse_train_max=4, nlbse_dev_fraction=0.25)
    examples = convert_dataset("nlbse", raw, config).examples
    sizes = {s: sum(e.split == s for e in examples) for s in BENCHMARK_SPLITS}
    assert sizes == {"train": 3, "dev": 1, "test": 4}
    again = {e.id for e in convert_dataset("nlbse", raw, config).examples}
    assert again == {e.id for e in examples}  # same seed, same sample


def test_nlbse_reads_the_official_tar_archives(raw: Path, tmp_path: Path) -> None:
    folder = tmp_path / "nlbse"
    folder.mkdir()
    for name in (TRAIN_FILE, TEST_FILE):
        csv = raw / "nlbse" / name.replace(".tar.gz", ".csv")
        with tarfile.open(folder / name, "w:gz") as archive:
            archive.add(csv, arcname=csv.name)
    from_archives = convert_dataset("nlbse", tmp_path, CONFIG)
    from_csv = convert_dataset("nlbse", raw, CONFIG)
    assert from_archives.examples == from_csv.examples
    assert set(from_archives.source_files) == {TRAIN_FILE, TEST_FILE}


def test_nlbse_rejects_unknown_labels(raw: Path, tmp_path: Path) -> None:
    shutil.copytree(raw / "nlbse", tmp_path / "nlbse")
    path = tmp_path / "nlbse" / TEST_FILE.replace(".tar.gz", ".csv")
    path.write_text(
        path.read_text(encoding="utf-8").replace(",question,", ",documentation,"), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="documentation"):
        convert_dataset("nlbse", tmp_path, CONFIG)


# ---------------------------------------------------------------- common format and output


def test_example_rules() -> None:
    with pytest.raises(ValueError, match="out-of-scope"):
        Example(id="x", text="t", labels=("a",), lead=None, out_of_scope=True, split="test")
    with pytest.raises(ValueError, match="lead must be one of the labels"):
        Example(id="x", text="t", labels=("a",), lead="b", out_of_scope=False, split="test")
    with pytest.raises(ValueError, match="Unknown split"):
        Example(id="x", text="t", labels=("a",), lead="a", out_of_scope=False, split="val")


def test_build_writes_parquet_hashes_and_cards(raw: Path, tmp_path: Path) -> None:
    infos = build_benchmarks(raw, tmp_path, CONFIG)
    assert set(infos) == set(DATASETS)
    for dataset in DATASETS:
        folder = tmp_path / dataset
        frame = rows(tmp_path, dataset)
        assert list(frame.columns) == ["id", "text", "labels", "lead", "out_of_scope", "split"]
        # Split integrity: every id is unique, and each file holds only its own split.
        assert frame["id"].is_unique
        for split in BENCHMARK_SPLITS:
            part = pd.read_parquet(folder / f"{split}.parquet")
            assert set(part["split"]) <= {split}
            digest = (folder / f"{split}.parquet.sha256").read_text(encoding="utf-8").split()[0]
            assert (
                digest == file_sha256(folder / f"{split}.parquet") == infos[dataset]["files"][split]["sha256"]
            )
        card = (folder / "DATA_CARD.md").read_text(encoding="utf-8")
        source = SOURCES[dataset]
        assert source.homepage in card and source.licence in card and source.citation in card
    assert AGIF_COMMIT in (tmp_path / "mixatis" / "DATA_CARD.md").read_text(encoding="utf-8")
    assert CLINC_COMMIT in (tmp_path / "clinc150" / "DATA_CARD.md").read_text(encoding="utf-8")
    assert "10.1145/3528588.3528664" in (tmp_path / "nlbse" / "DATA_CARD.md").read_text(encoding="utf-8")


def test_multi_intent_labels_survive_the_round_trip(raw: Path, tmp_path: Path) -> None:
    build_benchmarks(raw, tmp_path, CONFIG, datasets=("mixatis",))
    frame = rows(tmp_path, "mixatis").set_index("id")
    assert list(frame.at["mixatis-train-000002", "labels"]) == [
        "atis_ground_service",
        "atis_airport",
        "atis_abbreviation",
    ]
    assert pd.isna(frame.at["mixatis-train-000002", "lead"])  # stored as null in the parquet file


def test_output_is_deterministic(raw: Path, tmp_path: Path) -> None:
    first = build_benchmarks(raw, tmp_path / "a", CONFIG)
    second = build_benchmarks(raw, tmp_path / "b", CONFIG)
    assert {d: first[d]["files"] for d in DATASETS} == {d: second[d]["files"] for d in DATASETS}


def test_every_source_is_documented() -> None:
    for name in DATASETS:
        source = SOURCES[name]
        assert source.files and all(url.startswith("https://") for url in source.files.values())
        assert source.licence and source.citation.startswith("@") and source.version
    # GitHub downloads are pinned to a commit, never to a moving branch.
    assert all(AGIF_COMMIT in url for name in ("mixatis", "mixsnips") for url in SOURCES[name].files.values())
    assert all(CLINC_COMMIT in url for url in SOURCES["clinc150"].files.values())
