"""Fill the vector index of a workspace, one batch at a time (ADR-0007).

A chunk is pending when its vector was not made by the active embedder. Each vector
records its embedder key and dimension, so switching embedder re-indexes and never
mixes two embedders' vectors in one search.
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nfactory_core.knowledge.embedders import Embedder
from nfactory_core.models import Document, DocumentChunk


@dataclass(frozen=True)
class IndexStatus:
    total: int
    embedded: int

    @property
    def complete(self) -> bool:
        return self.embedded >= self.total


async def index_batch(
    session: AsyncSession, workspace_id: str, embedder: Embedder, size: int = 64
) -> int:
    """Embed up to `size` pending chunks; returns how many were embedded (0: done).

    Provider errors propagate: a failing embedder is never swapped for another.
    """
    pending = (
        await session.scalars(
            select(DocumentChunk)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                Document.workspace_id == workspace_id,
                DocumentChunk.embedding_model.is_distinct_from(embedder.key),
            )
            .order_by(DocumentChunk.id)
            .limit(size)
        )
    ).all()
    if not pending:
        return 0
    vectors = await embedder.embed([c.content for c in pending])
    for chunk_row, vector in zip(pending, vectors, strict=True):
        chunk_row.embedding = vector
        chunk_row.embedding_model = embedder.key
        chunk_row.embedding_dim = len(vector)
    await session.flush()
    return len(pending)


async def index_status(session: AsyncSession, workspace_id: str, key: str) -> IndexStatus:
    row = (
        await session.execute(
            select(
                func.count(DocumentChunk.id),
                func.count(DocumentChunk.id).filter(DocumentChunk.embedding_model == key),
            )
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(Document.workspace_id == workspace_id)
        )
    ).one()
    return IndexStatus(total=int(row[0]), embedded=int(row[1]))
