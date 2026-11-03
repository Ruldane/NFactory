"""Enterprise Brain storage: documents and their searchable chunks (spec §7)."""

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from nfactory_core.models.base import Base, created_column, id_column, optional_timestamp


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = id_column("doc")
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(40))  # upload | folder | git
    path: Mapped[str] = mapped_column(String(1000))
    revision: Mapped[str | None] = mapped_column(String(100))
    acl: Mapped[dict[str, Any]] = mapped_column(default=dict)
    checksum: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    kind: Mapped[str | None] = mapped_column(String(20))  # markdown | text | code | pdf | docx
    # Extracted text: citations point at its lines.
    content: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    expires_at: Mapped[datetime | None] = optional_timestamp()
    created_at: Mapped[datetime] = created_column()

    # Lookups made on every upload: same file (dedup) or same path (new revision).
    __table_args__ = (
        Index("ix_documents_scope_checksum", "workspace_id", "checksum"),
        Index("ix_documents_scope_path", "workspace_id", "path"),
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    id: Mapped[str] = id_column("chk")
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    # No fixed dimension on purpose: each embedding model gets its own partial index
    # (phase 3), so switching models never mixes vectors of different sizes.
    embedding: Mapped[Any] = mapped_column(Vector(), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(200))
    embedding_dim: Mapped[int | None] = mapped_column(Integer)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", default=dict)
    # "simple" config keeps full-text search language-neutral (French and English docs).
    tsv: Mapped[Any] = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple', content)", persisted=True)
    )

    __table_args__ = (Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),)
