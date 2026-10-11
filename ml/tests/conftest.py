from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def results_dir(tmp_path: Path) -> str:
    """Run records go to a temporary folder, never into the real results/."""
    return str(tmp_path / "results")
