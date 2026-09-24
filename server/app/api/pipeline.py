"""Running pipeline stages, and reading the measurement logs (agent runs, checks, metrics)."""

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy import case, func, select

from app.api.deps import CurrentUser, DbSession, OwnedProject
from app.models import AgentRun, ConsistencyCheck, Project
from app.schemas.api import (
    AgentMetrics,
    AgentRunOut,
    CheckMetrics,
    CheckOut,
    MetricsOut,
    StageName,
    StageRunOut,
)
from app.services import pipeline

router = APIRouter(tags=["pipeline"])


@router.post(
    "/projects/{project_id}/stages/{stage}/run",
    response_model=StageRunOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_stage(stage: StageName, project: OwnedProject, background: BackgroundTasks) -> StageRunOut:
    """Starts a stage in the background. Follow progress on the project WebSocket."""
    try:
        pipeline.assert_can_run(project, stage)
    except pipeline.StageError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    pipeline.mark_running(project.id, stage)
    background.add_task(pipeline.run_stage_job, project.id, stage)
    return StageRunOut(project_id=project.id, stage=stage, status="started")


@router.get("/projects/{project_id}/runs", response_model=list[AgentRunOut])
async def list_runs(project: OwnedProject, db: DbSession) -> list[AgentRun]:
    rows = await db.scalars(
        select(AgentRun).where(AgentRun.project_id == project.id).order_by(AgentRun.started_at.desc())
    )
    return list(rows)


@router.get("/projects/{project_id}/checks", response_model=list[CheckOut])
async def list_checks(project: OwnedProject, db: DbSession) -> list[ConsistencyCheck]:
    rows = await db.scalars(
        select(ConsistencyCheck)
        .where(ConsistencyCheck.project_id == project.id)
        .order_by(ConsistencyCheck.created_at.desc())
    )
    return list(rows)


@router.get("/metrics", response_model=MetricsOut)
async def metrics(db: DbSession, user: CurrentUser) -> MetricsOut:
    """Aggregates over the current user's projects, for the research papers."""
    owned = select(Project.id).where(Project.owner_id == user.id)
    succeeded = func.sum(case((AgentRun.status == "succeeded", 1), else_=0))
    first_try = func.sum(case(((AgentRun.status == "succeeded") & (AgentRun.retries == 0), 1), else_=0))
    agent_rows = await db.execute(
        select(
            AgentRun.agent,
            func.count(),
            succeeded,
            func.avg(AgentRun.duration_ms),
            func.avg(AgentRun.input_tokens),
            func.avg(AgentRun.output_tokens),
            func.avg(AgentRun.retries),
            first_try,
        )
        .where(AgentRun.project_id.in_(owned))
        .group_by(AgentRun.agent)
        .order_by(AgentRun.agent)
    )
    agents = [
        AgentMetrics(
            agent=agent,
            runs=runs,
            succeeded=int(ok or 0),
            success_rate=round((ok or 0) / runs, 4),
            avg_duration_ms=round(float(duration or 0), 1),
            avg_input_tokens=round(float(tin or 0), 1),
            avg_output_tokens=round(float(tout or 0), 1),
            avg_retries=round(float(retries or 0), 3),
            first_try_rate=round((first or 0) / runs, 4),
        )
        for agent, runs, ok, duration, tin, tout, retries, first in agent_rows
    ]

    passed = func.sum(case((ConsistencyCheck.passed, 1), else_=0))
    check_rows = await db.execute(
        select(ConsistencyCheck.check_name, func.count(), passed)
        .where(ConsistencyCheck.project_id.in_(owned))
        .group_by(ConsistencyCheck.check_name)
        .order_by(ConsistencyCheck.check_name)
    )
    checks = [
        CheckMetrics(check_name=name, runs=runs, passed=int(ok or 0), pass_rate=round((ok or 0) / runs, 4))
        for name, runs, ok in check_rows
    ]
    return MetricsOut(agents=agents, checks=checks)
