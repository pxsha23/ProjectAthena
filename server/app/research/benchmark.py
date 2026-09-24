"""Paper 1 benchmark: strict schema handoffs vs the naive free-text baseline.

Each idea runs through Idea -> Tech Stack -> Code in both modes with the same model. The same static
consistency checks are applied to both, and everything is logged to the database as usual.
Results are written as CSV plus a Markdown summary. Runs can be stopped and resumed.

Usage (from server/):
    uv run python -m app.research.benchmark --limit 3 --out research/results/pilot
    uv run python -m app.research.benchmark --out research/results/pilot --summary-only
"""

import argparse
import asyncio
import csv
import json
import statistics
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select

from app.agents.base import AgentRunFailed
from app.agents.deploy import detect_stack
from app.core.config import get_settings
from app.core.db import dispose_engine, get_session_factory
from app.llm.factory import clear_provider_cache
from app.models import AgentRun, ConsistencyCheck, Project, ProjectFile, User
from app.research.naive import infer_stack, run_naive_pipeline
from app.schemas.agents import DeployAgentInput, GeneratedFile, StackPlan
from app.services import pipeline

SERVER_DIR = Path(__file__).resolve().parents[2]
BENCH_EMAIL = "benchmark@athena.local"
STAGES = ("idea", "stack", "code")

CODE_CHECKS = [
    "files_parse",
    "python_lint",
    "python_dependencies_declared",
    "node_dependencies_declared",
    "code_matches_stack",
]
# These pass trivially when there are no files, so the summary only counts pipelines that produced code.
FILE_CHECKS = {"files_parse", "python_lint", "python_dependencies_declared", "node_dependencies_declared"}
REPORTED_CHECKS = ["spec_has_core_features", "spec_has_target_users", "stack_covers_layers", *CODE_CHECKS]

PIPELINE_FIELDS = [
    "idea_id", "mode", "repeat", "status", "failed_stage", "error", "duration_s", "llm_calls",
    "input_tokens", "output_tokens", "retries", "validation_errors", "model", "files",
    "checks_run", "checks_passed", "all_code_checks_passed", *REPORTED_CHECKS,
    "backend_detected", "deploy_matches_stack", "project_id", "finished_at",
]  # fmt: skip


@dataclass
class Idea:
    id: str
    name: str
    idea: str


def load_ideas(path: Path) -> list[Idea]:
    return [Idea(**item) for item in yaml.safe_load(path.read_text(encoding="utf-8"))]


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=SERVER_DIR,
            capture_output=True,
            text=True,
            check=False,
        )
        return out.stdout.strip() or "unknown"
    except OSError:
        return "unknown"


async def _benchmark_user(session: Any) -> User:
    user = await session.scalar(select(User).where(User.email == BENCH_EMAIL))
    if user is None:
        user = User(email=BENCH_EMAIL, name="Benchmark", password_hash=None)
        session.add(user)
        await session.commit()
    return user


def _flag(value: bool | None) -> int | str:
    return "" if value is None else int(value)


async def run_one(idea: Idea, mode: str, repeat: int) -> dict[str, Any]:
    """Runs one pipeline and returns its row for pipelines.csv."""
    async with get_session_factory()() as session:
        user = await _benchmark_user(session)
        project = Project(
            owner_id=user.id,
            name=f"[benchmark] {idea.name} ({mode} {repeat})",
            idea=idea.idea,
            description=idea.idea[:300],
            mode=mode,
        )
        session.add(project)
        await session.commit()

        started = time.perf_counter()
        status, failed_stage, error = "completed", "", ""
        try:
            if mode == "strict":
                for stage in STAGES:
                    await pipeline.execute_stage(session, project, stage)
            else:
                await run_naive_pipeline(session, project)
        except AgentRunFailed as exc:
            await session.rollback()
            status, failed_stage, error = "failed", exc.agent, exc.message[:300]
        duration = time.perf_counter() - started

        runs = list(await session.scalars(select(AgentRun).where(AgentRun.project_id == project.id)))
        checks = list(
            await session.scalars(select(ConsistencyCheck).where(ConsistencyCheck.project_id == project.id))
        )
        files = list(await session.scalars(select(ProjectFile).where(ProjectFile.project_id == project.id)))
        await session.refresh(project)

        # The stack the code should match: the validated plan (strict) or what the text says (naive).
        plan: StackPlan | None = None
        if mode == "strict" and project.stack:
            plan = StackPlan.model_validate(project.stack)
        elif mode == "naive":
            stack_run = next((r for r in runs if r.agent == "stack" and r.output_json), None)
            plan = infer_stack(stack_run.output_json["text"]) if stack_run else None

        backend_detected = deploy_matches = None
        if files:
            generated = [
                GeneratedFile(path=f.path, language=f.language, content=f.content, purpose="")  # type: ignore[arg-type]
                for f in files
            ]
            detection = detect_stack(DeployAgentInput(stack=plan, files=generated))
            backend_detected = detection.backend_language != "none"
            if plan and plan.backend_framework != "none":
                deploy_matches = detection.backend_framework == plan.backend_framework
            else:
                deploy_matches = None

        by_name = {c.check_name: c.passed for c in checks}
        code_results = [by_name[c] for c in CODE_CHECKS if c in by_name]
        return {
            "idea_id": idea.id,
            "mode": mode,
            "repeat": repeat,
            "status": status,
            "failed_stage": failed_stage,
            "error": error,
            "duration_s": round(duration, 1),
            "llm_calls": len(runs),
            "input_tokens": sum(r.input_tokens for r in runs),
            "output_tokens": sum(r.output_tokens for r in runs),
            "retries": sum(r.retries for r in runs),
            "validation_errors": sum(len(r.validation_errors or []) for r in runs),
            "model": ";".join(sorted({r.model for r in runs if r.model})),
            "files": len(files),
            "checks_run": len(checks),
            "checks_passed": sum(c.passed for c in checks),
            "all_code_checks_passed": _flag(all(code_results) if code_results else None),
            **{name: _flag(by_name.get(name)) for name in REPORTED_CHECKS},
            "backend_detected": _flag(backend_detected),
            "deploy_matches_stack": _flag(deploy_matches),
            "project_id": project.id,
            "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }


# ---------------------------------------------------------------- CSV and summary


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def append_row(path: Path, row: dict[str, Any]) -> None:
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=PIPELINE_FIELDS)
        if new:
            writer.writeheader()
        writer.writerow(row)


async def export_details(out: Path, project_ids: list[str]) -> None:
    """Writes every agent run and check of the benchmark projects, for deeper analysis."""
    async with get_session_factory()() as session:
        runs = list(await session.scalars(select(AgentRun).where(AgentRun.project_id.in_(project_ids))))
        checks = list(
            await session.scalars(
                select(ConsistencyCheck).where(ConsistencyCheck.project_id.in_(project_ids))
            )
        )
    with (out / "agent_runs.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "project_id",
                "agent",
                "mode",
                "provider",
                "model",
                "status",
                "duration_ms",
                "input_tokens",
                "output_tokens",
                "retries",
                "validation_errors",
                "error",
                "started_at",
            ]
        )
        for r in sorted(runs, key=lambda r: r.started_at):
            w.writerow(
                [
                    r.project_id,
                    r.agent,
                    r.mode,
                    r.provider,
                    r.model,
                    r.status,
                    r.duration_ms,
                    r.input_tokens,
                    r.output_tokens,
                    r.retries,
                    len(r.validation_errors or []),
                    (r.error or "")[:300],
                    r.started_at.isoformat(),
                ]
            )
    with (out / "checks.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["project_id", "stage", "check_name", "passed", "severity", "message", "duration_ms"])
        for c in sorted(checks, key=lambda c: (c.project_id, c.created_at)):
            w.writerow(
                [c.project_id, c.stage, c.check_name, int(c.passed), c.severity, c.message, c.duration_ms]
            )


def _rate(rows: list[dict[str, str]], field: str) -> str:
    values = [int(r[field]) for r in rows if r.get(field) not in ("", None)]
    return f"{100 * sum(values) / len(values):.0f}% ({sum(values)}/{len(values)})" if values else "n/a"


def _mean_sd(rows: list[dict[str, str]], field: str, scale: float = 1.0, digits: int = 1) -> str:
    values = [float(r[field]) / scale for r in rows if r.get(field) not in ("", None)]
    if not values:
        return "n/a"
    sd = statistics.stdev(values) if len(values) > 1 else 0.0
    return f"{statistics.mean(values):.{digits}f} ± {sd:.{digits}f}"


def _with_files(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [r for r in rows if r.get("files") not in ("", None) and int(r["files"]) > 0]


def _check_rate(name: str) -> Any:
    if name in FILE_CHECKS:
        return lambda rs: _rate(_with_files(rs), name)
    return lambda rs: _rate(rs, name)


def write_summary(out: Path, config: dict[str, Any]) -> str:
    rows = read_rows(out / "pipelines.csv")
    modes = [m for m in ("strict", "naive") if any(r["mode"] == m for r in rows)]
    table_rows = [
        ("Pipelines", lambda rs: str(len(rs))),
        ("Completed all stages", lambda rs: f"{sum(r['status'] == 'completed' for r in rs)}/{len(rs)}"),
        ("Code produced (files > 0)", lambda rs: f"{sum(int(r['files']) > 0 for r in rs)}/{len(rs)}"),
        ("All code checks passed", lambda rs: _rate(rs, "all_code_checks_passed")),
        *[(f"Check: {name}", _check_rate(name)) for name in REPORTED_CHECKS],
        ("Backend detected for deployment", lambda rs: _rate(rs, "backend_detected")),
        ("Deployment matches chosen stack", lambda rs: _rate(rs, "deploy_matches_stack")),
        ("Time per pipeline (min)", lambda rs: _mean_sd(rs, "duration_s", 60)),
        ("Input tokens", lambda rs: _mean_sd(rs, "input_tokens", digits=0)),
        ("Output tokens", lambda rs: _mean_sd(rs, "output_tokens", digits=0)),
        ("Schema retries per pipeline", lambda rs: _mean_sd(rs, "retries", digits=2)),
    ]
    lines = [
        "# Paper 1 benchmark: strict schema handoffs vs naive free text",
        "",
        f"Generated {datetime.now(UTC):%Y-%m-%d %H:%M} UTC from `{out.as_posix()}/pipelines.csv`.",
        "",
        "| Measure | " + " | ".join(modes) + " |",
        "|---|" + "---|" * len(modes),
    ]
    for label, fn in table_rows:
        lines.append(
            f"| {label} | " + " | ".join(fn([r for r in rows if r["mode"] == m]) for m in modes) + " |"
        )

    ideas = sorted({r["idea_id"] for r in rows})
    lines += [
        "",
        "Rates are over the pipelines where the check ran; values are mean ± standard deviation. "
        "Per-file checks (files_parse, python_lint, dependency checks) count only pipelines that produced "
        "at least one file, since they pass trivially on no files.",
        "",
        "## Setup",
        "",
        f"- Model: {config.get('model')} via {config.get('provider')}"
        f" (context {config.get('num_ctx')} tokens, temperature 0.2)",
        f"- Ideas: {len(ideas)} ({', '.join(ideas)}); repeats per idea and mode: {config.get('repeats')}",
        f"- Stages: {', '.join(STAGES)}; schema retry limit (strict): {config.get('max_retries')}",
        f"- Refusal fallback: {config.get('refusal_fallback')}; code version: {config.get('git_commit')}",
        "",
        "## Methods paragraph (draft for the synopsis)",
        "",
        f"We compared two handoff designs in a three-agent pipeline (Idea, Tech Stack, Code) using the same "
        f"locally hosted model ({config.get('model')}). In the strict condition, every agent returned output "
        f"that had to validate against a Pydantic schema with unknown fields rejected; invalid output was "
        f"retried up to {config.get('max_retries')} times with the validation error fed back. In the naive "
        f"condition, agents exchanged free Markdown text with no validation or retries, and files were "
        f"extracted from the Code Agent's text with a lenient parser. Both conditions used identical role "
        f"instructions and were evaluated with the same static consistency checks (syntax, pyflakes lint, "
        f"declared Python and npm dependencies, code matching the chosen stack, spec completeness) and "
        f"rule-based deployment detection. No generated code was executed. We ran {len(ideas)} app ideas in "
        f"each condition ({len(rows)} pipelines in total).",
        "",
    ]
    text = "\n".join(lines)
    (out / "summary.md").write_text(text, encoding="utf-8")
    return text


# ---------------------------------------------------------------- CLI


def run_config(repeats: int) -> dict[str, Any]:
    s = get_settings()
    provider = s.provider_for("code")
    model = s.model_override_for("code") or (s.ollama_model if provider == "local" else s.anthropic_model)
    return {
        "started_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "provider": {"local": "Ollama", "api": "Anthropic API", "fake": "fake provider"}[provider],
        "model": model if provider != "fake" else "fake-model",
        "num_ctx": s.ollama_num_ctx if provider == "local" else "n/a",
        "max_retries": s.agent_max_retries,
        "refusal_fallback": "off",
        "repeats": repeats,
        "git_commit": _git_commit(),
    }


async def run_benchmark(
    ideas: list[Idea], modes: list[str], repeats: int, out: Path, log: Any = print
) -> str:
    # The Anthropic refusal fallback must be off during benchmark runs.
    get_settings().anthropic_refusal_fallback = False
    clear_provider_cache()  # rebuild providers so the setting above takes effect

    out.mkdir(parents=True, exist_ok=True)
    config_path = out / "run-config.json"
    config = json.loads(config_path.read_text()) if config_path.exists() else run_config(repeats)
    config_path.write_text(json.dumps(config, indent=2))

    done = {(r["idea_id"], r["mode"], r["repeat"]) for r in read_rows(out / "pipelines.csv")}
    total = len(ideas) * len(modes) * repeats
    step = 0
    for repeat in range(1, repeats + 1):
        for idea in ideas:
            for mode in modes:  # alternate modes per idea so time-of-day effects are spread evenly
                step += 1
                if (idea.id, mode, str(repeat)) in done:
                    log(f"[{step}/{total}] {idea.id} {mode} #{repeat}: already done, skipping")
                    continue
                log(f"[{step}/{total}] {idea.id} {mode} #{repeat}: running...")
                row = await run_one(idea, mode, repeat)
                append_row(out / "pipelines.csv", row)
                log(
                    f"[{step}/{total}] {idea.id} {mode} #{repeat}: {row['status']} in {row['duration_s']}s, "
                    f"{row['files']} files, checks {row['checks_passed']}/{row['checks_run']}"
                )

    project_ids = [r["project_id"] for r in read_rows(out / "pipelines.csv")]
    await export_details(out, project_ids)
    return write_summary(out, config)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--ideas", type=Path, default=SERVER_DIR / "research" / "ideas.yaml")
    parser.add_argument("--limit", type=int, default=None, help="use only the first N ideas")
    parser.add_argument("--modes", default="strict,naive")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--summary-only", action="store_true", help="rebuild summary.md from pipelines.csv")
    args = parser.parse_args()

    if args.summary_only:
        config_path = args.out / "run-config.json"
        config = json.loads(config_path.read_text()) if config_path.exists() else {}
        print(write_summary(args.out, config))
        return

    ideas = load_ideas(args.ideas)[: args.limit]
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    if not set(modes) <= {"strict", "naive"}:
        parser.error("--modes must contain only strict and/or naive")

    async def go() -> None:
        try:
            print(await run_benchmark(ideas, modes, args.repeats, args.out))
        finally:
            await dispose_engine()

    asyncio.run(go())


if __name__ == "__main__":
    main()
