"""Runs pipeline stages: calls agents, stores their validated output, runs consistency checks,
and publishes progress events for the WebSocket."""

import logging
import re
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentRunFailed
from app.agents.code import CodeAgent
from app.agents.deploy import DeployAgent
from app.agents.eva import EvaAgent
from app.agents.idea import IdeaAgent
from app.agents.stack import StackAgent
from app.agents.summary import SummaryAgent
from app.checker import checks
from app.checker.runner import run_checks
from app.core.db import get_session_factory
from app.models import ChatMessage, Project, ProjectFile
from app.models.project import STAGES
from app.schemas.agents import (
    CodeAgentInput,
    DeployAgentInput,
    EvaAgentInput,
    EvaReport,
    GeneratedFile,
    IdeaAgentInput,
    LearningStat,
    ProjectSpec,
    StackAgentInput,
    StackPlan,
    SummaryAgentInput,
)
from app.services import embeddings
from app.services.progress import hub
from app.services.running import RUNNING

log = logging.getLogger("athena.pipeline")

STATUS_FOR_STAGE = {
    "idea": "draft",
    "stack": "in-progress",
    "code": "in-progress",
    "export": "ready",
    "deploy": "deployed",
}

STAGE_MESSAGES = {
    "idea": "Your spec is ready. Review it and tell me what to change.",
    "stack": "I chose a stack that fits the spec. Each choice has a reason and alternatives.",
    "code": "The code is generated. Open the explorer to start reading it.",
    "eva": "I walked through the app as Alpha, Bravo and Charlie. The report is in the EVA tab.",
    "export": "The code is ready to export. Push it to GitHub or download a zip.",
    "deploy": "Deployment files and your learning summary are ready.",
}
STAGE_AGENT = {
    "idea": "idea",
    "stack": "stack",
    "code": "code",
    "eva": "eva",
    "export": "code",
    "deploy": "deploy",
}

# Projects with a stage currently running (one at a time per project): project id -> stage.
_running = RUNNING


class StageError(Exception):
    """A stage cannot start (missing prerequisite or already running)."""


def stage_index(stage: str) -> int:
    return STAGES.index(stage)


def reached(project: Project, stage: str) -> bool:
    return stage_index(project.stage) >= stage_index(stage)


def assert_can_run(project: Project, stage: str) -> None:
    if project.id in _running:
        raise StageError("Another stage is already running for this project")
    required = {
        "stack": (project.spec is not None, "Run the Idea stage first: there is no spec yet"),
        "code": (project.stack is not None, "Run the Tech Stack stage first"),
        "eva": (reached(project, "code"), "Generate the code before running EVA"),
        "export": (reached(project, "code"), "Generate the code before exporting"),
        "deploy": (reached(project, "code"), "Generate the code before writing deployment files"),
    }
    ok, message = required.get(stage, (True, ""))
    if not ok:
        raise StageError(message)


def mark_running(project_id: str, stage: str) -> None:
    _running[project_id] = stage


def advance(project: Project, stage: str) -> None:
    if stage in STAGES and stage_index(stage) > stage_index(project.stage):
        project.stage = stage
        project.status = STATUS_FOR_STAGE[stage]


def _generated_files(project_files: list[ProjectFile]) -> list[GeneratedFile]:
    return [
        GeneratedFile(path=f.path, language=f.language, content=f.content, purpose="")  # type: ignore[arg-type]
        for f in project_files
    ]


async def _files(session: AsyncSession, project_id: str) -> list[ProjectFile]:
    rows = await session.scalars(
        select(ProjectFile).where(ProjectFile.project_id == project_id).order_by(ProjectFile.path)
    )
    return list(rows)


async def _upsert_files(
    session: AsyncSession, project_id: str, files: list[GeneratedFile], source: str, *, replace_all: bool
) -> None:
    if replace_all:
        await session.execute(delete(ProjectFile).where(ProjectFile.project_id == project_id))
        existing: dict[str, ProjectFile] = {}
    else:
        existing = {f.path: f for f in await _files(session, project_id)}
    for f in files:
        row = existing.get(f.path)
        if row:
            row.content, row.language, row.source = f.content, f.language, source
        else:
            session.add(
                ProjectFile(
                    project_id=project_id, path=f.path, language=f.language, content=f.content, source=source
                )
            )
    await session.flush()


def _learning_stats(files: list[ProjectFile], topics: int) -> list[LearningStat]:
    lines = sum(len(f.content.splitlines()) for f in files)
    routes = sum(
        len(
            re.findall(
                r"@\w+\.(?:get|post|put|patch|delete)\(|\b(?:app|router)\.(?:get|post|put|patch|delete)\(",
                f.content,
            )
        )
        for f in files
    )
    return [
        LearningStat(label="Files generated", value=str(len(files))),
        LearningStat(label="Lines of code", value=str(lines)),
        LearningStat(label="API routes", value=str(routes)),
        LearningStat(label="Topics covered", value=str(topics)),
    ]


async def _say(session: AsyncSession, project_id: str, stage: str) -> None:
    session.add(
        ChatMessage(
            project_id=project_id, role="agent", agent=STAGE_AGENT[stage], content=STAGE_MESSAGES[stage]
        )
    )


async def _publish_checks(project_id: str, stage: str, rows: list[Any]) -> None:
    await hub.publish(
        project_id,
        "checks_completed",
        stage=stage,
        passed=sum(r.passed for r in rows),
        total=len(rows),
        failed=[r.check_name for r in rows if not r.passed],
    )


async def _run_idea(session: AsyncSession, project: Project) -> None:
    await hub.publish(project.id, "agent_started", agent="idea", stage="idea")
    outcome = await IdeaAgent().run(
        session,
        IdeaAgentInput(idea=project.idea, project_name=project.name),
        project_id=project.id,
        stage="idea",
    )
    project.spec = outcome.output.to_json_dict()
    project.description = outcome.output.summary[:300]
    await _agent_done(project.id, outcome.run)
    rows = await run_checks(
        session,
        project_id=project.id,
        stage="idea",
        agent_run_id=outcome.run.id,
        check=lambda: checks.check_spec(outcome.output),
    )
    await _publish_checks(project.id, "idea", rows)


async def _run_stack(session: AsyncSession, project: Project) -> None:
    await hub.publish(project.id, "agent_started", agent="stack", stage="stack")
    spec = ProjectSpec.model_validate(project.spec)
    outcome = await StackAgent().run(
        session, StackAgentInput(spec=spec), project_id=project.id, stage="stack"
    )
    project.stack = outcome.output.to_json_dict()
    await _agent_done(project.id, outcome.run)
    rows = await run_checks(
        session,
        project_id=project.id,
        stage="stack",
        agent_run_id=outcome.run.id,
        check=lambda: checks.check_stack(outcome.output),
    )
    await _publish_checks(project.id, "stack", rows)


async def _run_code(session: AsyncSession, project: Project) -> None:
    await hub.publish(project.id, "agent_started", agent="code", stage="code")
    spec, stack = ProjectSpec.model_validate(project.spec), StackPlan.model_validate(project.stack)
    outcome = await CodeAgent().run(
        session, CodeAgentInput(spec=spec, stack=stack), project_id=project.id, stage="code"
    )
    await _upsert_files(session, project.id, outcome.output.files, "code", replace_all=True)
    await _agent_done(project.id, outcome.run)
    rows = await run_checks(
        session,
        project_id=project.id,
        stage="code",
        agent_run_id=outcome.run.id,
        check=lambda: checks.check_code(outcome.output.files, stack),
    )
    await _publish_checks(project.id, "code", rows)
    count = await embeddings.index_project(session, project.id, await _files(session, project.id))
    await hub.publish(project.id, "index_updated", chunks=count)


async def _run_eva(session: AsyncSession, project: Project) -> None:
    await hub.publish(project.id, "agent_started", agent="eva", stage="eva")
    spec = ProjectSpec.model_validate(project.spec)
    files = _generated_files(await _files(session, project.id))
    outcome = await EvaAgent().run(
        session, EvaAgentInput(spec=spec, files=files), project_id=project.id, stage="eva"
    )
    project.eva = outcome.output.to_json_dict()
    await _agent_done(project.id, outcome.run)


async def _run_deploy(session: AsyncSession, project: Project) -> None:
    await hub.publish(project.id, "agent_started", agent="deploy", stage="deploy")
    stack = StackPlan.model_validate(project.stack) if project.stack else None
    files = _generated_files(await _files(session, project.id))
    bundle, run = await DeployAgent().run(
        session, DeployAgentInput(stack=stack, files=files), project_id=project.id
    )
    await _upsert_files(session, project.id, bundle.files, "deploy", replace_all=False)
    project.deployment = bundle.to_json_dict()
    await _agent_done(project.id, run)
    rows = await run_checks(
        session,
        project_id=project.id,
        stage="deploy",
        agent_run_id=run.id,
        check=lambda: checks.check_deployment(bundle.files),
    )
    await _publish_checks(project.id, "deploy", rows)

    await hub.publish(project.id, "agent_started", agent="summary", stage="deploy")
    all_files = await _files(session, project.id)
    outcome = await SummaryAgent().run(
        session,
        SummaryAgentInput(
            project_name=project.name,
            spec=ProjectSpec.model_validate(project.spec),
            stack=stack or StackPlan.model_validate(project.stack),
            file_paths=[f.path for f in all_files],
            deployment_targets=bundle.targets,
            eva=EvaReport.model_validate(project.eva) if project.eva else None,
        ),
        project_id=project.id,
        stage="deploy",
    )
    summary = outcome.output
    summary.overview.stats = _learning_stats(all_files, len(summary.topics))
    project.learning = summary.to_json_dict()
    await _agent_done(project.id, outcome.run)
    await embeddings.index_project(session, project.id, all_files)


async def _agent_done(project_id: str, run: Any) -> None:
    await hub.publish(
        project_id,
        "agent_succeeded",
        agent=run.agent,
        runId=run.id,
        durationMs=run.duration_ms,
        retries=run.retries,
    )


RUNNERS = {"idea": _run_idea, "stack": _run_stack, "code": _run_code, "eva": _run_eva, "deploy": _run_deploy}


async def execute_stage(session: AsyncSession, project: Project, stage: str) -> None:
    """Runs one stage for a project using the given session. Raises AgentRunFailed on agent failure."""
    runner = RUNNERS.get(stage)
    if runner is not None:
        await runner(session, project)
    advance(project, stage)  # "eva" is not a pipeline stage, so it never advances
    await _say(session, project.id, stage)
    await session.commit()


async def run_stage_job(project_id: str, stage: str) -> None:
    """Background task entry point: opens its own session, runs the stage, reports progress."""
    _running[project_id] = stage
    try:
        async with get_session_factory()() as session:
            project = await session.get(Project, project_id)
            if project is None:
                return
            await hub.publish(project_id, "stage_started", stage=stage)
            try:
                await execute_stage(session, project, stage)
            except AgentRunFailed as exc:
                await session.rollback()
                log.warning("Stage %s failed for project %s: %s", stage, project_id, exc.message)
                await hub.publish(
                    project_id,
                    "stage_failed",
                    stage=stage,
                    agent=exc.agent,
                    runId=exc.run_id,
                    error=exc.message,
                )
                return
            except Exception as exc:  # unexpected bug: report it instead of failing silently
                await session.rollback()
                log.exception("Stage %s crashed for project %s", stage, project_id)
                await hub.publish(project_id, "stage_failed", stage=stage, error=f"Internal error: {exc}")
                return
            await hub.publish(
                project_id, "stage_completed", stage=stage, projectStage=project.stage, status=project.status
            )
    finally:
        _running.pop(project_id, None)
