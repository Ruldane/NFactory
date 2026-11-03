"""Reusable factory recipes saved by a workspace (task 5.5, spec F38).

Revision ID: c4d7a2e8f513
Revises: 8b2f4e6a9c31
Create Date: 2026-11-03
"""

import sqlalchemy as sa
from alembic import op

revision: str = "c4d7a2e8f513"
down_revision: str | None = "8b2f4e6a9c31"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "saved_recipes",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("workspace_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=5000), nullable=False),
        sa.Column("project_type", sa.String(length=30), nullable=False),
        sa.Column("template_id", sa.String(length=100), nullable=True),
        sa.Column("request", sa.Text(), nullable=False),
        sa.Column("source_run_id", sa.String(length=32), nullable=True),
        sa.Column("created_by", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uses", sa.Integer(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_saved_recipes_workspace_id", "saved_recipes", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_saved_recipes_workspace_id", table_name="saved_recipes")
    op.drop_table("saved_recipes")
