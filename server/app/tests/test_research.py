"""Paper 1 tooling: naive free-text pipeline, file parsing, stack inference and the benchmark runner."""

import csv
from pathlib import Path

import pytest

from app.llm.base import LLMUnavailableError
from app.llm.factory import set_provider_override
from app.llm.fake_provider import FakeProvider
from app.research.benchmark import Idea, load_ideas, run_benchmark
from app.research.naive import check_spec_text, infer_stack, parse_files

IDEA = Idea(id="study", name="StudySync", idea="An app where students find study partners and book rooms.")


def test_parse_files_accepts_common_formats_and_rejects_unsafe_paths() -> None:
    text = (
        "Intro text.\n\nFILE: backend/main.py\n```python\nprint(1)\n```\n\n"
        "### `frontend/src/App.tsx`\n```tsx\nexport default 1\n```\n\n"
        "```json package.json\n{}\n```\n\n"
        "**File:** ../escape.py\n```python\nx\n```\n\n"
        "FILE: .github/workflows/ci.yml\n```yaml\non: push\n```\n"
    )
    parsed = parse_files(text)
    assert [f.path for f in parsed.files] == [
        "backend/main.py",
        ".github/workflows/ci.yml",
        "frontend/src/App.tsx",
        "package.json",
    ]
    assert parsed.files[0].content == "print(1)\n"
    assert parsed.files[0].language == "python"
    assert parsed.rejected_paths == ["../escape.py"]


def test_parse_files_needs_a_code_block_right_after_the_header() -> None:
    assert parse_files("FILE: a.py\nsome prose, then later\n```python\nx\n```\n").files == []


def test_infer_stack_from_free_text() -> None:
    plan = infer_stack("We will use Next.js for the frontend, Express on the backend and MongoDB.")
    assert (plan.frontend_framework, plan.backend_framework, plan.database) == (
        "nextjs",
        "express",
        "mongodb",
    )
    assert plan.backend_language == "javascript"
    assert infer_stack("Something unusual").backend_framework == "none"


def test_spec_text_checks() -> None:
    good = "# Spec\n## Target users\n- Students\n## Core features\n- One\n- Two\n"
    assert all(r.passed for r in check_spec_text(good))
    assert not any(r.passed for r in check_spec_text("Just a paragraph with no structure."))


def test_ideas_file_is_valid() -> None:
    ideas = load_ideas(Path(__file__).resolve().parents[2] / "research" / "ideas.yaml")
    assert len(ideas) == 10 and len({i.id for i in ideas}) == 10


async def test_benchmark_runs_both_modes_and_writes_results(tmp_path: Path) -> None:
    out = tmp_path / "pilot"
    summary = await run_benchmark([IDEA], ["strict", "naive"], 1, out, log=lambda *_: None)

    rows = list(csv.DictReader((out / "pipelines.csv").open(encoding="utf-8")))
    assert [(r["mode"], r["status"]) for r in rows] == [("strict", "completed"), ("naive", "completed")]
    for row in rows:
        assert int(row["files"]) == 6
        assert row["all_code_checks_passed"] == "1"
        assert row["backend_detected"] == "1" and row["deploy_matches_stack"] == "1"
        assert int(row["llm_calls"]) == 3
    assert rows[0]["retries"] == "0"

    runs = list(csv.DictReader((out / "agent_runs.csv").open(encoding="utf-8")))
    assert {r["mode"] for r in runs} == {"strict", "naive"}
    checks = list(csv.DictReader((out / "checks.csv").open(encoding="utf-8")))
    assert any(c["check_name"] == "files_extracted" for c in checks)

    assert "| Measure | strict | naive |" in summary
    assert "Methods paragraph" in summary
    assert (out / "run-config.json").exists()

    # Resume: a second call skips completed pipelines instead of running them again.
    logged: list[str] = []
    await run_benchmark([IDEA], ["strict", "naive"], 1, out, log=logged.append)
    assert all("skipping" in line for line in logged)
    assert len(list(csv.DictReader((out / "pipelines.csv").open(encoding="utf-8")))) == 2


async def test_benchmark_records_naive_handoff_failure(tmp_path: Path) -> None:
    provider = FakeProvider()
    # The code agent answers with prose and no files: the naive handoff breaks, nothing to check.
    provider.queue_text("code", "Sure, I would build it with FastAPI and React. Let me know!")
    for agent in ("idea", "stack", "code"):
        set_provider_override(agent, provider)  # type: ignore[arg-type]
    summary = await run_benchmark([IDEA], ["naive"], 1, tmp_path, log=lambda *_: None)
    [row] = list(csv.DictReader((tmp_path / "pipelines.csv").open(encoding="utf-8")))
    assert row["status"] == "completed" and row["files"] == "0"
    checks = list(csv.DictReader((tmp_path / "checks.csv").open(encoding="utf-8")))
    assert next(c for c in checks if c["check_name"] == "files_extracted")["passed"] == "0"
    # Per-file checks pass trivially on no files, so the summary must not count them as passes.
    assert "| Check: python_lint | n/a |" in summary
    assert "| Check: files_parse | n/a |" in summary


async def test_benchmark_records_agent_failure(tmp_path: Path) -> None:
    provider = FakeProvider()
    provider.queue_text("stack", LLMUnavailableError("model crashed"))
    for agent in ("idea", "stack", "code"):
        set_provider_override(agent, provider)  # type: ignore[arg-type]
    await run_benchmark([IDEA], ["naive"], 1, tmp_path, log=lambda *_: None)
    [row] = list(csv.DictReader((tmp_path / "pipelines.csv").open(encoding="utf-8")))
    assert (row["status"], row["failed_stage"]) == ("failed", "stack")
    assert "model crashed" in row["error"]


@pytest.fixture(autouse=True)
def _restore_fallback_setting():
    from app.core.config import get_settings

    before = get_settings().anthropic_refusal_fallback
    yield
    get_settings().anthropic_refusal_fallback = before
