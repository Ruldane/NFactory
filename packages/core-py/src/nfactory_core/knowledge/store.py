"""Store an upload as a document and its chunks (spec §7.2, ADR-0007).

A file already present in the same scope (same sha256) is not indexed twice; a new
file at an existing path replaces that path's previous revision.
"""

import hashlib
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from nfactory_core.knowledge.chunking import chunk
from nfactory_core.knowledge.extract import extract
from nfactory_core.models import Document, DocumentChunk

MAX_PATH = 1000


@dataclass(frozen=True)
class Scope:
    """Who may see a document: a workspace, and optionally one of its projects."""

    workspace_id: str
    project_id: str | None = None


@dataclass(frozen=True)
class Ingested:
    document: Document
    duplicate: bool = False
    replaced: bool = False


def clean_path(name: str) -> str:
    """A display label only, never a filesystem path: drop traversal and empty parts."""
    parts = [p for p in name.replace("\\", "/").split("/") if p not in ("", ".", "..")]
    return "/".join(parts)[-MAX_PATH:] or "document"


async def ingest(session: AsyncSession, scope: Scope, filename: str, data: bytes) -> Ingested:
    """Extract, chunk and store `data`. Raises `ExtractionError` on a bad file."""
    path = clean_path(filename)
    checksum = hashlib.sha256(data).hexdigest()
    same_file = await session.scalar(_in_scope(scope).where(Document.checksum == checksum).limit(1))
    if same_file is not None:
        return Ingested(same_file, duplicate=True)

    extracted = extract(path, data)  # before any write: a bad file changes nothing
    previous = await session.scalar(_in_scope(scope).where(Document.path == path).limit(1))
    revision = "1"
    if previous is not None:
        revision = str(int(previous.revision or "1") + 1)
        await session.execute(delete(Document).where(Document.id == previous.id))

    document = Document(
        workspace_id=scope.workspace_id,
        project_id=scope.project_id,
        source="upload",
        path=path,
        revision=revision,
        acl={"visibility": "project" if scope.project_id else "workspace"},
        checksum=checksum,
        status="indexed",
        kind=extracted.kind,
        content=extracted.text,
        size_bytes=len(data),
    )
    session.add(document)
    await session.flush()
    session.add_all(
        DocumentChunk(
            document_id=document.id,
            ordinal=c.ordinal,
            content=c.content,
            meta={
                "start_line": c.start_line,
                "end_line": c.end_line,
                "section": c.section,
                "symbol": c.symbol,
                "page": c.page,
                "language": extracted.language,
            },
        )
        for c in chunk(extracted)
    )
    await session.flush()
    return Ingested(document, replaced=previous is not None)


def _in_scope(scope: Scope):  # type: ignore[no-untyped-def]
    project = (
        Document.project_id == scope.project_id
        if scope.project_id
        else Document.project_id.is_(None)
    )
    return select(Document).where(Document.workspace_id == scope.workspace_id, project)
