"""Where the ml/ project lives, so relative paths in configs work from any working directory."""

import os
from pathlib import Path


def ml_root() -> Path:
    """The ml/ folder.

    Order: the ATHENA_ML_ROOT environment variable (set this on Kaggle), then the source checkout this
    package was installed from, then the current directory.
    """
    if env := os.environ.get("ATHENA_ML_ROOT"):
        return Path(env).resolve()
    checkout = Path(__file__).resolve().parents[2]
    if (checkout / "pyproject.toml").is_file():
        return checkout
    return Path.cwd()


def resolve(path: str | Path) -> Path:
    """Absolute paths stay as they are; relative ones are relative to ml/."""
    path = Path(path)
    return path if path.is_absolute() else ml_root() / path
