"""Hybrid search: access control first, then full text + vector, fused by RRF.

Access control is part of the SQL of both searches: a chunk outside the scope is
never a candidate. A `Scope` with a project sees that project's documents and the
workspace-wide ones; without a project it sees the whole workspace.
"""

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from nfactory_core.knowledge.embedders import Embedder
from nfactory_core.knowledge.store import Scope
from nfactory_core.models import Document, DocumentChunk

RRF_K = 60
CANDIDATES = 20
MAX_TERMS = 32
_WORD = re.compile(r"\w+")


@dataclass(frozen=True)
class Hit:
    """A chunk found by a search, with everything a citation needs."""

    chunk_id: str
    document_id: str
    path: str
    content: str
    start_line: int
    end_line: int
    section: str | None
    symbol: str | None
    page: int | None
    score: float
    matched: tuple[str, ...]  # "text", "vector"


async def search(
    session: AsyncSession,
    scope: Scope,
    query: str,
    *,
    embedder: Embedder | None = None,
    limit: int = 8,
) -> list[Hit]:
    terms = _WORD.findall(query.lower())[:MAX_TERMS]
    if not terms:
        return []
    ranked: dict[str, list[tuple[str, int]]] = {}
    for rank, chunk_id in enumerate(await _text_candidates(session, scope, terms), start=1):
        ranked.setdefault(chunk_id, []).append(("text", rank))
    if embedder is not None:
        (vector,) = await embedder.embed([query])
        candidates = await _vector_candidates(session, scope, embedder.key, vector)
        for rank, chunk_id in enumerate(candidates, start=1):
            ranked.setdefault(chunk_id, []).append(("vector", rank))
    scores = {cid: sum(1 / (RRF_K + r) for _, r in found) for cid, found in ranked.items()}
    top = sorted(scores, key=lambda cid: scores[cid], reverse=True)[:limit]
    rows = {
        c.id: (c, d)
        for c, d in (
            await session.execute(
                select(DocumentChunk, Document)
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(DocumentChunk.id.in_(top))
            )
        ).all()
    }
    return [_hit(*rows[cid], scores[cid], ranked[cid]) for cid in top if cid in rows]


def _visible(scope: Scope) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = [Document.workspace_id == scope.workspace_id]
    if scope.project_id:
        conditions.append(
            or_(Document.project_id == scope.project_id, Document.project_id.is_(None))
        )
    return conditions


async def _text_candidates(session: AsyncSession, scope: Scope, terms: list[str]) -> list[str]:
    # Any term may match ("|"); long terms match as prefixes so plurals still hit.
    tsquery = func.to_tsquery("simple", " | ".join(f"{t}:*" if len(t) >= 4 else t for t in terms))
    rank = func.ts_rank_cd(DocumentChunk.tsv, tsquery)
    rows = await session.scalars(
        select(DocumentChunk.id)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(*_visible(scope), DocumentChunk.tsv.op("@@")(tsquery))
        .order_by(rank.desc(), DocumentChunk.id)
        .limit(CANDIDATES)
    )
    return list(rows.all())


async def _vector_candidates(
    session: AsyncSession, scope: Scope, key: str, vector: list[float]
) -> list[str]:
    rows = await session.scalars(
        select(DocumentChunk.id)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            *_visible(scope),
            DocumentChunk.embedding_model == key,
            DocumentChunk.embedding_dim == len(vector),
        )
        .order_by(DocumentChunk.embedding.cosine_distance(vector), DocumentChunk.id)
        .limit(CANDIDATES)
    )
    return list(rows.all())


def _hit(chunk_row: DocumentChunk, document: Document, score: float, found: Any) -> Hit:
    meta = chunk_row.meta or {}
    return Hit(
        chunk_id=chunk_row.id,
        document_id=document.id,
        path=document.path,
        content=chunk_row.content,
        start_line=int(meta.get("start_line") or 1),
        end_line=int(meta.get("end_line") or 1),
        section=meta.get("section"),
        symbol=meta.get("symbol"),
        page=meta.get("page"),
        score=score,
        matched=tuple(sorted(kind for kind, _ in found)),
    )
