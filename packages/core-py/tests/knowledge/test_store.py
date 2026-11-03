"""Ingestion into PostgreSQL: dedup by hash, revisions by path, scoped by project."""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from nfactory_core.knowledge import Scope, ingest
from nfactory_core.models import Document, DocumentChunk, Project, User, Workspace

pytestmark = pytest.mark.integration

GUIDE = b"# Licences\n\nRenouveler 30 jours avant.\n\n## Exceptions\n\nLes licences OEM.\n"


@pytest.fixture
async def session(migrated_database_url: str) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(migrated_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        owner = User(display_name="Test")
        session.add(owner)
        await session.flush()
        workspace = Workspace(name="Savoir", owner_id=owner.id)
        session.add(workspace)
        await session.flush()
        projects = [Project(workspace_id=workspace.id, title=t, type="api") for t in "AB"]
        session.add_all(projects)
        await session.flush()
        session.info.update(workspace=workspace.id, a=projects[0].id, b=projects[1].id)
        yield session
        await session.rollback()
    await engine.dispose()


async def _chunks(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count()).select_from(DocumentChunk)) or 0)


async def test_upload_is_stored_with_its_text_and_located_chunks(session: AsyncSession) -> None:
    scope = Scope(session.info["workspace"], session.info["a"])

    result = await ingest(session, scope, "licences.md", GUIDE)

    doc = result.document
    assert (doc.status, doc.kind, doc.revision, result.duplicate) == (
        "indexed",
        "markdown",
        "1",
        False,
    )
    assert doc.content == GUIDE.decode()
    assert doc.project_id == session.info["a"]
    chunks = (await session.scalars(select(DocumentChunk).order_by(DocumentChunk.ordinal))).all()
    assert [c.meta["section"] for c in chunks] == ["Licences", "Licences > Exceptions"]
    assert (chunks[1].meta["start_line"], chunks[1].meta["end_line"]) == (5, 7)
    assert all(c.embedding is None for c in chunks)  # vectors come later, from the worker


async def test_identical_reupload_adds_no_chunk(session: AsyncSession) -> None:
    scope = Scope(session.info["workspace"], session.info["a"])
    first = await ingest(session, scope, "licences.md", GUIDE)
    before = await _chunks(session)

    again = await ingest(session, scope, "copie.md", GUIDE)

    assert again.duplicate
    assert again.document.id == first.document.id
    assert await _chunks(session) == before


async def test_the_same_file_in_another_project_is_its_own_document(session: AsyncSession) -> None:
    await ingest(session, Scope(session.info["workspace"], session.info["a"]), "l.md", GUIDE)

    other = await ingest(
        session, Scope(session.info["workspace"], session.info["b"]), "l.md", GUIDE
    )

    assert not other.duplicate
    assert other.document.project_id == session.info["b"]


async def test_new_content_at_the_same_path_replaces_the_old_revision(
    session: AsyncSession,
) -> None:
    scope = Scope(session.info["workspace"], None)
    old = await ingest(session, scope, "docs/licences.md", GUIDE)

    new = await ingest(session, scope, "docs/licences.md", b"# Licences\n\nNouvelle regle.\n")

    assert new.replaced and new.document.revision == "2"
    assert await session.get(Document, old.document.id) is None
    contents = (await session.scalars(select(DocumentChunk.content))).all()
    assert contents == ["# Licences\n\nNouvelle regle."]


async def test_upload_paths_are_cleaned(session: AsyncSession) -> None:
    scope = Scope(session.info["workspace"], None)

    result = await ingest(session, scope, "..\\..\\secret/../notes.txt", b"hello")

    assert result.document.path == "secret/notes.txt"
