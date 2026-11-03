"""Audit entries belong to a workspace, so each member reads only theirs (task 5.4).

Revision ID: 8b2f4e6a9c31
Revises: 3d9a6c1f7b20
Create Date: 2026-11-03
"""

import sqlalchemy as sa
from alembic import op

revision: str = "8b2f4e6a9c31"
down_revision: str | None = "3d9a6c1f7b20"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("audit_log", sa.Column("workspace_id", sa.String(length=32), nullable=True))
    op.create_index("ix_audit_log_workspace_id", "audit_log", ["workspace_id"])
    # Entries written before this revision came from local mode: one workspace.
    op.execute(
        "UPDATE audit_log SET workspace_id = 'wks_local' WHERE workspace_id IS NULL "
        "AND EXISTS (SELECT 1 FROM workspaces WHERE id = 'wks_local')"
    )


def downgrade() -> None:
    op.drop_index("ix_audit_log_workspace_id", table_name="audit_log")
    op.drop_column("audit_log", "workspace_id")
