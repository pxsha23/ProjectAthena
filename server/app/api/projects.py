"""Projects, files and chat."""

import json
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Response, status
from sqlalchemy import select

from app.agents.base import AgentRunFailed
from app.agents.chat import ChatAgent
from app.api.deps import CurrentUser, DbSession, OwnedProject
from app.models import ChatMessage, Project, ProjectFile
from app.schemas.agents import ChatAgentInput
from app.schemas.agents.chat import ChatTurn
from app.schemas.api import (
    ChatIn,
    FileOut,
    FileWrite,
    MessageOut,
    ProjectCreate,
    ProjectDetailOut,
    ProjectOut,
    ProjectUpdate,
)
from app.services import embeddings

router = APIRouter(prefix="/projects", tags=["projects"])

EXTENSION_LANGUAGE = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".json": "json",
    ".md": "markdown",
    ".css": "css",
    ".html": "html",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".toml": "toml",
}

FilePath = Annotated[str, Path(min_length=1, max_length=500)]


def _language_for(path: str) -> str:
    if path.rsplit("/", 1)[-1].lower() == "dockerfile":
        return "dockerfile"
    suffix = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return EXTENSION_LANGUAGE.get(suffix, "plaintext")


def _check_path(path: str) -> str:
    path = path.replace("\\", "/")
    if path.startswith("/") or ".." in path.split("/"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid file path")
    return path


@router.get("", response_model=list[ProjectOut])
async def list_projects(db: DbSession, user: CurrentUser) -> list[Project]:
    rows = await db.scalars(
        select(Project).where(Project.owner_id == user.id).order_by(Project.updated_at.desc())
    )
    return list(rows)


@router.post("", response_model=ProjectDetailOut, status_code=status.HTTP_201_CREATED)
async def create_project(body: ProjectCreate, db: DbSession, user: CurrentUser) -> Project:
    project = Project(
        owner_id=user.id, name=body.name.strip(), idea=body.idea.strip(), description=body.idea.strip()[:300]
    )
    db.add(project)
    await db.flush()
    db.add(ChatMessage(project_id=project.id, role="user", content=project.idea))
    await db.commit()
    return project


@router.get("/{project_id}", response_model=ProjectDetailOut)
async def get_project(project: OwnedProject) -> Project:
    return project


@router.patch("/{project_id}", response_model=ProjectDetailOut)
async def update_project(body: ProjectUpdate, project: OwnedProject, db: DbSession) -> Project:
    if body.name is not None:
        project.name = body.name.strip()
    if body.starred is not None:
        project.starred = body.starred
    await db.commit()
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project: OwnedProject, db: DbSession) -> Response:
    await db.delete(project)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- files


@router.get("/{project_id}/files", response_model=list[FileOut])
async def list_files(project: OwnedProject, db: DbSession) -> list[ProjectFile]:
    rows = await db.scalars(
        select(ProjectFile).where(ProjectFile.project_id == project.id).order_by(ProjectFile.path)
    )
    return list(rows)


async def _get_file(db: DbSession, project_id: str, path: str) -> ProjectFile | None:
    return await db.scalar(
        select(ProjectFile).where(ProjectFile.project_id == project_id, ProjectFile.path == path)
    )


@router.get("/{project_id}/files/{path:path}", response_model=FileOut)
async def read_file(project: OwnedProject, path: FilePath, db: DbSession) -> ProjectFile:
    row = await _get_file(db, project.id, _check_path(path))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="File not found")
    return row


@router.put("/{project_id}/files/{path:path}", response_model=FileOut)
async def write_file(project: OwnedProject, path: FilePath, body: FileWrite, db: DbSession) -> ProjectFile:
    """Saves an edit from the editor (Ctrl+S). Creates the file if it does not exist."""
    path = _check_path(path)
    row = await _get_file(db, project.id, path)
    if row is None:
        row = ProjectFile(project_id=project.id, path=path, language=body.language or _language_for(path))
        db.add(row)
    row.content = body.content
    row.source = "user"
    if body.language:
        row.language = body.language
    await db.commit()
    await db.refresh(row)
    files = list(await db.scalars(select(ProjectFile).where(ProjectFile.project_id == project.id)))
    await embeddings.index_project(db, project.id, files)
    return row


@router.delete("/{project_id}/files/{path:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(project: OwnedProject, path: FilePath, db: DbSession) -> Response:
    row = await _get_file(db, project.id, _check_path(path))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="File not found")
    await db.delete(row)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- chat


@router.get("/{project_id}/messages", response_model=list[MessageOut])
async def list_messages(project: OwnedProject, db: DbSession) -> list[ChatMessage]:
    rows = await db.scalars(
        select(ChatMessage).where(ChatMessage.project_id == project.id).order_by(ChatMessage.created_at)
    )
    return list(rows)


@router.post("/{project_id}/messages", response_model=list[MessageOut], status_code=status.HTTP_201_CREATED)
async def send_message(body: ChatIn, project: OwnedProject, db: DbSession) -> list[ChatMessage]:
    """Stores the user's message, asks the chosen agent, and returns both messages."""
    history = list(
        await db.scalars(
            select(ChatMessage)
            .where(ChatMessage.project_id == project.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(10)
        )
    )[::-1]
    question = ChatMessage(project_id=project.id, role="user", content=body.content)
    db.add(question)
    await db.commit()

    files = await db.scalars(select(ProjectFile.path).where(ProjectFile.project_id == project.id))
    context = {"spec": project.spec, "stack": project.stack, "files": list(files), "eva": project.eva}
    agent_input = ChatAgentInput(
        agent=body.agent_id,
        question=body.content,
        project_name=project.name,
        stage=project.stage,
        context=json.dumps(context, ensure_ascii=False),
        history=[ChatTurn(role=m.role, content=m.content) for m in history],  # type: ignore[arg-type]
    )
    try:
        outcome = await ChatAgent().run(db, agent_input, project_id=project.id, stage=project.stage)
    except AgentRunFailed as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail=f"The agent could not answer: {exc.message}"
        ) from exc

    reply = ChatMessage(
        project_id=project.id, role="agent", agent=body.agent_id, content=outcome.output.reply
    )
    db.add(reply)
    await db.commit()
    return [question, reply]
