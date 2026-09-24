"""Runs consistency checks and logs every result to the consistency_checks table."""

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.checker.checks import CheckResult
from app.models import ConsistencyCheck


async def run_checks(
    session: AsyncSession,
    *,
    project_id: str,
    stage: str,
    agent_run_id: str | None,
    check: Callable[[], list[CheckResult]],
) -> list[ConsistencyCheck]:
    results = check()
    rows = [
        ConsistencyCheck(
            project_id=project_id,
            agent_run_id=agent_run_id,
            stage=stage,
            check_name=r.name,
            passed=r.passed,
            severity=r.severity,
            message=r.message,
            details=r.details,
            duration_ms=round(r.duration_ms),
        )
        for r in results
    ]
    session.add_all(rows)
    await session.commit()
    return rows
