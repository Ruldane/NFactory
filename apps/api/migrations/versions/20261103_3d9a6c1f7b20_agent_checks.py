"""Sandbox checks of a coding agent's change made on the user's machine (task 4.4).

Revision ID: 3d9a6c1f7b20
Revises: 7c1e4b9d2a10
Create Date: 2026-11-03
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "3d9a6c1f7b20"
down_revision: str | None = "7c1e4b9d2a10"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "agent_checks",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.String(length=32), nullable=False),
        sa.Column("task_id", sa.String(length=20), nullable=False),
        sa.Column("repo_id", sa.String(length=50), nullable=False),
        sa.Column("runtime", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.String(length=1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_checks_task_id", "agent_checks", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_checks_task_id", table_name="agent_checks")
    op.drop_table("agent_checks")
