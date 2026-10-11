from pathlib import Path

import pandas as pd
import pytest
import yaml

from athena_advisor.config import SPECIALISTS
from athena_advisor.data.labels import Label, load_tag_map

TAG_MAP = "configs/tag_map.yaml"


@pytest.fixture(scope="module")
def tag_map():
    return load_tag_map(TAG_MAP)


def test_tag_map_is_complete_and_consistent(tag_map) -> None:
    assert 200 <= len(tag_map.entries) <= 300
    assert {e.specialist for e in tag_map.entries.values()} == set(SPECIALISTS)
    assert tag_map.priority == ("checker", "deploy", "eva", "blueprint", "code")
    for broad in ("python", "javascript", "java"):
        assert tag_map.entries[broad].generic is True
    assert tag_map.entries["flask"].generic is False
    assert len(tag_map.sha256) == 64


def test_tag_map_rejects_mistakes(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    base = {"priority": ["checker", "deploy", "eva", "blueprint", "code"]}
    cases = [
        ({**base, "tags": [{"tag": "x", "specialist": "nobody", "generic": False}]}, "unknown specialist"),
        ({**base, "tags": [{"tag": "x", "specialist": "code", "generic": False}] * 2}, "twice"),
        ({**base, "tags": [{"tag": "x", "specialist": "code", "generic": "yes"}]}, "true or false"),
        ({"priority": ["code"], "tags": []}, "exactly once"),
    ]
    for data, message in cases:
        bad.write_text(yaml.safe_dump(data), encoding="utf-8")
        with pytest.raises(ValueError, match=message):
            load_tag_map(bad)


def fixture_labels(tag_map, fixtures_dir: Path) -> dict[int, Label | None]:
    tags = pd.read_csv(fixtures_dir / "stacksample_tiny" / "Tags.csv")
    return {qid: tag_map.label(group["Tag"].tolist()) for qid, group in tags.groupby("Id")}


def test_question_without_a_mapped_tag_is_dropped(tag_map, fixtures_dir: Path) -> None:
    labels = fixture_labels(tag_map, fixtures_dir)
    assert labels[105] is None  # tagged forms + mobile, neither in the map
    assert all(label is not None for qid, label in labels.items() if qid != 105)


def test_fixture_teams_and_leads(tag_map, fixtures_dir: Path) -> None:
    labels = fixture_labels(tag_map, fixtures_dir)
    expected = {
        # postgresql and mongodb are generic code tags; database-design is specific, so blueprint leads.
        101: (("blueprint", "code"), "blueprint"),
        # python is generic; typeerror is a specific code tag.
        102: (("code",), "code"),
        # flask (code) and unit-testing (eva) tie 1-1: eva comes first in the priority order.
        103: (("code", "eva"), "eva"),
        104: (("deploy",), "deploy"),
        106: (("deploy",), "deploy"),
        107: (("code",), "code"),
        # express (code) and rest (blueprint) tie; mysql is generic and does not count.
        108: (("blueprint", "code"), "blueprint"),
    }
    assert {qid: (label.team, label.lead) for qid, label in labels.items() if label} == expected


def test_specific_tags_beat_a_majority_of_generic_ones(tag_map) -> None:
    label = tag_map.label(["python", "python-3.x", "javascript", "docker"])
    assert label == Label(team=("code", "deploy"), lead="deploy")


def test_generic_tags_count_when_there_is_nothing_specific(tag_map) -> None:
    # 2 generic code tags against 1 generic deploy tag.
    assert tag_map.label(["python", "python-3.x", "linux"]).lead == "code"
    assert tag_map.label(["python", "linux"]).lead == "deploy"  # 1-1 tie: deploy comes before code


def test_priority_order_breaks_every_tie(tag_map) -> None:
    assert tag_map.label(["pip", "docker", "pytest", "orm", "flask"]).lead == "checker"
    assert tag_map.label(["docker", "pytest"]).lead == "deploy"
    assert tag_map.label(["orm", "flask"]).lead == "blueprint"


def test_team_order_and_duplicates(tag_map) -> None:
    label = tag_map.label(["pytest", "docker", "docker", "orm", "unknown-tag"])
    assert label.team == ("blueprint", "deploy", "eva")  # always in the fixed specialist order
    assert tag_map.label(["unknown-tag", "another-one"]) is None
    assert tag_map.label([]) is None
