"""The tiny fixtures keep the real StackSample file layout, so code tested on them also works on Kaggle."""

from pathlib import Path

import pandas as pd


def test_questions_fixture_has_the_stacksample_columns(fixtures_dir: Path) -> None:
    questions = pd.read_csv(fixtures_dir / "stacksample_tiny" / "Questions.csv")
    columns = ["Id", "OwnerUserId", "CreationDate", "ClosedDate", "Score", "Title", "Body"]
    assert list(questions.columns) == columns
    assert questions["Id"].is_unique and len(questions) == 8
    # Dates sort chronologically, which the time-based split relies on.
    dates = pd.to_datetime(questions["CreationDate"])
    assert dates.is_monotonic_increasing
    # Bodies are HTML with code blocks, like the real data.
    assert questions["Body"].str.contains("<pre><code>").any()


def test_tags_fixture_points_at_existing_questions(fixtures_dir: Path) -> None:
    folder = fixtures_dir / "stacksample_tiny"
    questions = pd.read_csv(folder / "Questions.csv")
    tags = pd.read_csv(folder / "Tags.csv")
    assert list(tags.columns) == ["Id", "Tag"]
    assert set(tags["Id"]) <= set(questions["Id"])
    assert tags.groupby("Id").size().min() >= 1
