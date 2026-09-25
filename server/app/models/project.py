from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, JsonType, TZDateTime, utcnow
from app.models.user import new_id

# Pipeline stages, in order. Mirrors StageId in the frontend.
STAGES = ("idea", "stack", "code", "export", "deploy")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    idea: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(String(300), default="")
    # Furthest stage reached: one of STAGES.
    stage: Mapped[str] = mapped_column(String(20), default="idea")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    starred: Mapped[bool] = mapped_column(Boolean, default=False)
    # Research (Paper 1): "strict" schema handoffs, or the "naive" free-text baseline.
    mode: Mapped[str] = mapped_column(String(10), default="strict", server_default="strict")

    # Latest validated output of each agent (the Pydantic schema, dumped to JSON).
    spec: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    stack: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    eva: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    deployment: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    learning: Mapped[dict[str, Any] | None] = mapped_column(JsonType)

    created_at: Mapped[datetime] = mapped_column(TZDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime(), default=utcnow, onupdate=utcnow)

    files: Mapped[list["ProjectFile"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", order_by="ProjectFile.path"
    )

    @property
    def spec_ready(self) -> bool:
        return self.spec is not None

    @property
    def running_stage(self) -> str | None:
        """The stage an agent is working on right now, if any (not stored in the database)."""
        from app.services.running import RUNNING

        return RUNNING.get(self.id)

    @property
    def stack_plan(self) -> dict[str, Any] | None:
        return self.stack

    @property
    def stack_names(self) -> list[str]:
        """Short technology names for the dashboard, e.g. ["React + Vite", "FastAPI"]."""
        if not self.stack:
            return []
        return [choice["name"] for choice in self.stack.get("choices", [])]


class ProjectFile(Base):
    __tablename__ = "project_files"
    __table_args__ = (UniqueConstraint("project_id", "path", name="uq_project_file_path"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    path: Mapped[str] = mapped_column(String(500))
    language: Mapped[str] = mapped_column(String(30), default="plaintext")
    content: Mapped[str] = mapped_column(Text, default="")
    # Which agent wrote the current content ("user" after a manual edit).
    source: Mapped[str] = mapped_column(String(20), default="code")
    updated_at: Mapped[datetime] = mapped_column(TZDateTime(), default=utcnow, onupdate=utcnow)

    project: Mapped[Project] = relationship(back_populates="files")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(10))  # "user" | "agent"
    agent: Mapped[str | None] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    # A proposed change the student can apply: {"kind": "spec" | "stack", "changes": [...], "value": {...}}.
    proposal: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    proposal_status: Mapped[str | None] = mapped_column(String(10))  # pending | applied | dismissed
    # Follow-up messages the agent suggests the student could send next.
    suggestions: Mapped[list[str] | None] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), default=utcnow)
