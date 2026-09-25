"""Workspace chat: builds each agent's context (with retrieval over the project's code), stores the
reply and any proposed spec or stack change, and applies a proposal once the student accepts it."""

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat import ChatAgent
from app.agents.stack import check_stack_plan
from app.checker import checks
from app.checker.runner import run_checks
from app.models import ChatMessage, ConsistencyCheck, Project, ProjectFile
from app.schemas.agents import ChatAgentInput, ChatTurn, CodeSnippet, ProjectSpec, StackPlan
from app.services import embeddings
from app.services.pipeline import advance

HISTORY_MESSAGES = 10
SEARCH_RESULTS = 4
SNIPPET_MAX_LINES = 80


class ProposalError(Exception):
    """The proposal cannot be applied (already handled, or no longer valid)."""


async def reply(session: AsyncSession, project: Project, agent: str, content: str) -> list[ChatMessage]:
    """Stores the student's message, asks the agent, and returns both messages.

    Raises AgentRunFailed when the agent cannot answer; the student's message is kept either way.
    """
    history = list(
        await session.scalars(
            select(ChatMessage)
            .where(ChatMessage.project_id == project.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(HISTORY_MESSAGES)
        )
    )[::-1]
    question = ChatMessage(project_id=project.id, role="user", agent=agent, content=content)
    session.add(question)
    await session.commit()

    files = list(await session.scalars(select(ProjectFile).where(ProjectFile.project_id == project.id)))
    agent_input = ChatAgentInput(
        agent=agent,  # type: ignore[arg-type]
        question=content,
        project_name=project.name,
        stage=project.stage,
        context=await _context(session, project, agent, files),
        code=await _relevant_code(session, project.id, content, files) if agent != "idea" else [],
        history=[ChatTurn(role=m.role, content=m.content) for m in history],  # type: ignore[arg-type]
    )
    outcome = await ChatAgent().run(session, agent_input, project_id=project.id, stage=project.stage)
    output = outcome.output

    answer = ChatMessage(
        project_id=project.id,
        role="agent",
        agent=agent,
        content=output.reply,
        suggestions=output.suggested_actions or None,
    )
    if output.spec_update is not None:
        answer.proposal = {
            "kind": "spec",
            "changes": output.changes,
            "value": output.spec_update.to_json_dict(),
        }
        answer.proposal_status = "pending"
    elif output.stack_update is not None:
        answer.proposal = {
            "kind": "stack",
            "changes": output.changes,
            "value": output.stack_update.to_json_dict(),
        }
        answer.proposal_status = "pending"
    session.add(answer)
    await session.commit()
    return [question, answer]


async def apply_proposal(session: AsyncSession, project: Project, message: ChatMessage) -> None:
    """Applies a pending spec or stack proposal to the project, then runs the usual checks on it."""
    if not message.proposal or message.proposal_status != "pending":
        raise ProposalError("This proposal was already applied or dismissed")
    kind, value = message.proposal["kind"], message.proposal["value"]
    had_code = project.stage in ("code", "export", "deploy")

    if kind == "spec":
        spec = ProjectSpec.model_validate(value)
        project.spec = spec.to_json_dict()
        project.description = spec.summary[:300]
        await run_checks(
            session,
            project_id=project.id,
            stage="idea",
            agent_run_id=None,
            check=lambda: checks.check_spec(spec),
        )
    else:
        stack = StackPlan.model_validate(value)
        try:
            check_stack_plan(stack)
        except ValueError as exc:
            raise ProposalError(str(exc)) from exc
        if project.spec is None:
            raise ProposalError("Write the spec first: the stack is chosen for a spec")
        project.stack = stack.to_json_dict()
        advance(project, "stack")
        await run_checks(
            session,
            project_id=project.id,
            stage="stack",
            agent_run_id=None,
            check=lambda: checks.check_stack(stack),
        )

    message.proposal_status = "applied"
    if had_code:
        # The student should learn that upstream changes do not rewrite the code by themselves.
        what = "spec" if kind == "spec" else "tech stack"
        rerun = "Tech Stack and Code stages" if kind == "spec" else "Code stage"
        session.add(
            ChatMessage(
                project_id=project.id,
                role="agent",
                agent="idea" if kind == "spec" else "stack",
                content=f"The {what} is updated. The existing code was written for the old {what}, so run "
                f"the {rerun} again to bring the code in line with it.",
            )
        )
    await session.commit()


async def dismiss_proposal(session: AsyncSession, message: ChatMessage) -> None:
    if not message.proposal or message.proposal_status != "pending":
        raise ProposalError("This proposal was already applied or dismissed")
    message.proposal_status = "dismissed"
    await session.commit()


# ---------------------------------------------------------------- context building


async def _context(
    session: AsyncSession, project: Project, agent: str, files: list[ProjectFile]
) -> dict[str, Any]:
    context: dict[str, Any] = {"idea": project.idea, "spec": project.spec}
    if agent == "idea":
        return context
    context["stack"] = project.stack
    context["files"] = [f.path for f in files]
    if agent in ("code", "eva", "deploy"):
        context["failedChecks"] = await _failed_checks(session, project.id)
    if agent in ("code", "eva"):
        context["eva"] = project.eva
    if agent == "deploy":
        deployment = project.deployment or {}
        context["deployment"] = {
            "detection": deployment.get("detection"),
            "targets": deployment.get("targets"),
        }
    return context


async def _failed_checks(session: AsyncSession, project_id: str) -> list[dict[str, str]]:
    """The latest result of each check, when it failed."""
    rows = await session.scalars(
        select(ConsistencyCheck)
        .where(ConsistencyCheck.project_id == project_id)
        .order_by(ConsistencyCheck.created_at.desc())
    )
    latest: dict[str, ConsistencyCheck] = {}
    for row in rows:
        latest.setdefault(row.check_name, row)
    return [
        {"check": row.check_name, "stage": row.stage, "message": row.message}
        for row in latest.values()
        if not row.passed
    ]


async def _relevant_code(
    session: AsyncSession, project_id: str, question: str, files: list[ProjectFile]
) -> list[CodeSnippet]:
    """Files the question names, then the closest code-search matches (retrieval-augmented answers)."""
    snippets: list[CodeSnippet] = []
    by_path = {f.path: f for f in files}
    lowered = question.lower()
    for path, file in by_path.items():
        name = path.rsplit("/", 1)[-1].lower()
        if path.lower() in lowered or re.search(rf"(?<![\w./-]){re.escape(name)}(?![\w-])", lowered):
            lines = file.content.splitlines()
            snippets.append(
                CodeSnippet(
                    path=path,
                    start_line=1,
                    end_line=min(len(lines), SNIPPET_MAX_LINES),
                    content="\n".join(lines[:SNIPPET_MAX_LINES]),
                )
            )
        if len(snippets) >= 2:
            break

    seen = {(s.path, s.start_line) for s in snippets}
    for hit in await embeddings.search(session, project_id, question, limit=SEARCH_RESULTS):
        if (hit.file_path, hit.start_line) not in seen and hit.file_path not in {s.path for s in snippets}:
            snippets.append(
                CodeSnippet(
                    path=hit.file_path, start_line=hit.start_line, end_line=hit.end_line, content=hit.content
                )
            )
    return snippets
