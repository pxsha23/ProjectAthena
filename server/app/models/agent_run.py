"""Measurement tables: every agent run and every consistency check is recorded here."""

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, JsonType, TZDateTime, utcnow
from app.models.user import new_id


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    agent: Mapped[str] = mapped_column(String(20), index=True)
    stage: Mapped[str | None] = mapped_column(String(20))
    provider: Mapped[str] = mapped_column(String(20))  # api | local | fake | rules
    model: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="running")  # running | succeeded | failed
    # "strict" (schema-validated handoff) or "naive" (free-text baseline, Paper 1).
    mode: Mapped[str] = mapped_column(String(10), default="strict", server_default="strict")

    started_at: Mapped[datetime] = mapped_column(TZDateTime(), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(TZDateTime())
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    # Attempts beyond the first, caused by output that failed schema validation.
    retries: Mapped[int] = mapped_column(Integer, default=0)
    # One entry per failed attempt: {"attempt": n, "error": "..."}.
    validation_errors: Mapped[list[dict[str, Any]]] = mapped_column(JsonType, default=list)
    error: Mapped[str | None] = mapped_column(Text)

    input_json: Mapped[dict[str, Any] | None] = mapped_column(JsonType)
    output_json: Mapped[dict[str, Any] | None] = mapped_column(JsonType)


class ConsistencyCheck(Base):
    __tablename__ = "consistency_checks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    agent_run_id: Mapped[str | None] = mapped_column(ForeignKey("agent_runs.id", ondelete="SET NULL"))
    stage: Mapped[str] = mapped_column(String(20))
    check_name: Mapped[str] = mapped_column(String(60), index=True)
    passed: Mapped[bool] = mapped_column(Boolean)
    severity: Mapped[str] = mapped_column(String(10))  # info | warning | error
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), default=utcnow)
