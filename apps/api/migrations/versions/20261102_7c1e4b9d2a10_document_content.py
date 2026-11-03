"""Knowledge base: keep each document's kind, size and extracted text (ADR-0007).

Revision ID: 7c1e4b9d2a10
Revises: 55207a00156b
Create Date: 2026-11-02
"""

import sqlalchemy as sa
from alembic import op

revision: str = "7c1e4b9d2a10"
down_revision: str | None = "55207a00156b"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("kind", sa.String(length=20), nullable=True))
    op.add_column("documents", sa.Column("content", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("size_bytes", sa.Integer(), nullable=True))
    # Lookups made on every upload: same file (dedup) or same path (new revision).
    op.create_index("ix_documents_scope_checksum", "documents", ["workspace_id", "checksum"])
    op.create_index("ix_documents_scope_path", "documents", ["workspace_id", "path"])


def downgrade() -> None:
    op.drop_index("ix_documents_scope_path", table_name="documents")
    op.drop_index("ix_documents_scope_checksum", table_name="documents")
    op.drop_column("documents", "size_bytes")
    op.drop_column("documents", "content")
    op.drop_column("documents", "kind")
