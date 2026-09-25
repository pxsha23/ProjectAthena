"""Chat proposals: an agent can propose a spec or stack change that the student applies or dismisses.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.core.db import JsonType

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("proposal", JsonType, nullable=True))
    op.add_column("chat_messages", sa.Column("proposal_status", sa.String(10), nullable=True))
    op.add_column("chat_messages", sa.Column("suggestions", JsonType, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("chat_messages") as batch:
        batch.drop_column("suggestions")
        batch.drop_column("proposal_status")
        batch.drop_column("proposal")
