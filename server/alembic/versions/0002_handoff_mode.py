"""Handoff mode (strict / naive) on projects and agent runs, for the Paper 1 comparison.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("projects", "agent_runs"):
        op.add_column(table, sa.Column("mode", sa.String(10), nullable=False, server_default="strict"))


def downgrade() -> None:
    for table in ("projects", "agent_runs"):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("mode")
