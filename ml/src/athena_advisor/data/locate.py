"""Finds an attached dataset under an input folder (Kaggle mounts datasets at different depths)."""

from pathlib import Path

STACKSAMPLE_FILES = ("Questions.csv", "Tags.csv")


def find_stacksample_dir(root: str | Path) -> Path:
    """The folder under `root` that holds both Questions.csv and Tags.csv.

    When several match (for example two versions of the dataset attached), the shortest path wins and
    ties are broken alphabetically, so the choice is always the same.
    """
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"Input folder {root} does not exist")
    candidates = sorted(
        {p.parent for p in root.rglob(STACKSAMPLE_FILES[0]) if (p.parent / STACKSAMPLE_FILES[1]).is_file()},
        key=lambda p: (len(p.parts), str(p)),
    )
    if not candidates:
        raise FileNotFoundError(
            f"No folder under {root} contains {' and '.join(STACKSAMPLE_FILES)}. "
            "On Kaggle, add the 'stackoverflow/stacksample' dataset to the notebook."
        )
    return candidates[0]
