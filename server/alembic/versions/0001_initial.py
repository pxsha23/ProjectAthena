"""Initial schema: users, auth tokens, projects, files, chat, agent runs, checks, code chunks.

Revision ID: 0001
Revises:
Create Date: 2026-09-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.core.db import EmbeddingType, JsonType, TZDateTime

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 384  # must match EMBEDDING_DIM in .env


def upgrade() -> None:
    is_postgres = op.get_bind().dialect.name == "postgresql"
    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(200), nullable=True),
        sa.Column("github_id", sa.BigInteger(), nullable=True),
        sa.Column("github_login", sa.String(100), nullable=True),
        sa.Column("github_token_encrypted", sa.String(1000), nullable=True),
        sa.Column("created_at", TZDateTime(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_github_id", "users", ["github_id"], unique=True)

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", TZDateTime(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("created_at", TZDateTime(), nullable=False),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    op.create_table(
        "projects",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("owner_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("idea", sa.Text(), nullable=False),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("stage", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("starred", sa.Boolean(), nullable=False),
        sa.Column("spec", JsonType, nullable=True),
        sa.Column("stack", JsonType, nullable=True),
        sa.Column("eva", JsonType, nullable=True),
        sa.Column("deployment", JsonType, nullable=True),
        sa.Column("learning", JsonType, nullable=True),
        sa.Column("created_at", TZDateTime(), nullable=False),
        sa.Column("updated_at", TZDateTime(), nullable=False),
    )
    op.create_index("ix_projects_owner_id", "projects", ["owner_id"])

    op.create_table(
        "project_files",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "project_id", sa.String(32), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("path", sa.String(500), nullable=False),
        sa.Column("language", sa.String(30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("updated_at", TZDateTime(), nullable=False),
        sa.UniqueConstraint("project_id", "path", name="uq_project_file_path"),
    )
    op.create_index("ix_project_files_project_id", "project_files", ["project_id"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "project_id", sa.String(32), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("agent", sa.String(20), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", TZDateTime(), nullable=False),
    )
    op.create_index("ix_chat_messages_project_id", "chat_messages", ["project_id"])

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "project_id", sa.String(32), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("agent", sa.String(20), nullable=False),
        sa.Column("stage", sa.String(20), nullable=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", TZDateTime(), nullable=False),
        sa.Column("finished_at", TZDateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("retries", sa.Integer(), nullable=False),
        sa.Column("validation_errors", JsonType, nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("input_json", JsonType, nullable=True),
        sa.Column("output_json", JsonType, nullable=True),
    )
    op.create_index("ix_agent_runs_project_id", "agent_runs", ["project_id"])
    op.create_index("ix_agent_runs_agent", "agent_runs", ["agent"])

    op.create_table(
        "consistency_checks",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "project_id", sa.String(32), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "agent_run_id", sa.String(32), sa.ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("stage", sa.String(20), nullable=False),
        sa.Column("check_name", sa.String(60), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", JsonType, nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", TZDateTime(), nullable=False),
    )
    op.create_index("ix_consistency_checks_project_id", "consistency_checks", ["project_id"])
    op.create_index("ix_consistency_checks_check_name", "consistency_checks", ["check_name"])

    op.create_table(
        "code_chunks",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "project_id", sa.String(32), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", EmbeddingType(EMBEDDING_DIM), nullable=False),
        sa.Column("created_at", TZDateTime(), nullable=False),
    )
    op.create_index("ix_code_chunks_project_id", "code_chunks", ["project_id"])
    if is_postgres:
        # Approximate nearest-neighbour index for cosine similarity search.
        op.execute(
            "CREATE INDEX ix_code_chunks_embedding ON code_chunks USING hnsw (embedding vector_cosine_ops)"
        )


def downgrade() -> None:
    for table in (
        "code_chunks",
        "consistency_checks",
        "agent_runs",
        "chat_messages",
        "project_files",
        "projects",
        "refresh_tokens",
        "users",
    ):
        op.drop_table(table)
