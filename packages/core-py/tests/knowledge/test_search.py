"""Versioned vector index and hybrid search with access control (tasks 3.3, 3.4)."""

from collections.abc import AsyncIterator, Sequence

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from nfactory_core.knowledge import Scope, index_batch, index_status, ingest, search
from nfactory_core.knowledge.embedders import LOCAL_KEY, LocalHashEmbedder
from nfactory_core.models import DocumentChunk, Project, User, Workspace

pytestmark = pytest.mark.integration

LICENCES = b"""# Licences logicielles

Renouveler chaque licence 30 jours avant son expiration.

# Sauvegardes

Les sauvegardes partent chaque nuit vers le NAS.
"""
SECRET_B = b"# Projet B\n\nLe mot de passe du coffre du projet B est au service paie.\n"
SHARED = b"# Charte\n\nToute licence achetee passe par le service achats.\n"


class OtherEngine(LocalHashEmbedder):
    """Same math, different index key: its vectors must never meet the local ones."""

    key = "ollama_local:autre-modele"

    def __init__(self) -> None:
        super().__init__(dim=64)


@pytest.fixture
async def session(migrated_database_url: str) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(migrated_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        owner = User(display_name="Test")
        session.add(owner)
        await session.flush()
        spaces = [Workspace(name=n, owner_id=owner.id) for n in ("W", "Autre")]
        session.add_all(spaces)
        await session.flush()
        projects = [Project(workspace_id=spaces[0].id, title=t, type="api") for t in "AB"]
        session.add_all(projects)
        await session.flush()
        w, other = spaces[0].id, spaces[1].id
        a, b = projects[0].id, projects[1].id
        await ingest(session, Scope(w, a), "licences.md", LICENCES)
        await ingest(session, Scope(w, b), "coffre.md", SECRET_B)
        await ingest(session, Scope(w, None), "charte.md", SHARED)
        await ingest(session, Scope(other, None), "ailleurs.md", b"# Licence\n\nAutre espace.\n")
        session.info.update(w=w, other=other, a=a, b=b)
        yield session
        await session.rollback()
    await engine.dispose()


async def _index_all(session: AsyncSession, workspace: str, embedder: LocalHashEmbedder) -> int:
    total = 0
    while done := await index_batch(session, workspace, embedder, size=2):
        total += done
    return total


def _paths(hits: Sequence[object]) -> list[str]:
    return [h.path for h in hits]  # type: ignore[attr-defined]


async def test_indexing_embeds_every_chunk_of_the_workspace_once(session: AsyncSession) -> None:
    embedded = await _index_all(session, session.info["w"], LocalHashEmbedder())

    assert embedded == 4  # 2 + 1 + 1 chunks in W; the other workspace is untouched
    assert await _index_all(session, session.info["w"], LocalHashEmbedder()) == 0
    status = await index_status(session, session.info["w"], LOCAL_KEY)
    assert (status.total, status.embedded) == (4, 4)


async def test_changing_engine_reindexes_without_mixing(session: AsyncSession) -> None:
    await _index_all(session, session.info["w"], LocalHashEmbedder())

    assert await index_batch(session, session.info["w"], OtherEngine(), size=1) == 1
    status = await index_status(session, session.info["w"], OtherEngine.key)
    assert (status.total, status.embedded) == (4, 1)

    keys = set((await session.scalars(select(DocumentChunk.embedding_model))).all())
    assert keys == {LOCAL_KEY, OtherEngine.key, None}  # None: the other workspace
    hits = await search(session, Scope(session.info["w"]), "licence", embedder=OtherEngine())
    vector_hits = [h for h in hits if "vector" in h.matched]
    assert len(vector_hits) == 1  # only the re-embedded chunk; local vectors are ignored


async def test_hybrid_search_cites_the_exact_source(session: AsyncSession) -> None:
    await _index_all(session, session.info["w"], LocalHashEmbedder())

    hits = await search(
        session,
        Scope(session.info["w"], session.info["a"]),
        "quand renouveler les licences ?",
        embedder=LocalHashEmbedder(),
    )

    top = hits[0]
    assert (top.path, top.section, top.start_line, top.end_line) == (
        "licences.md",
        "Licences logicielles",
        1,
        3,
    )
    assert set(top.matched) == {"text", "vector"}
    assert "30 jours" in top.content


async def test_a_project_never_sees_another_projects_documents(session: AsyncSession) -> None:
    await _index_all(session, session.info["w"], LocalHashEmbedder())
    scope_a = Scope(session.info["w"], session.info["a"])

    hits = await search(
        session, scope_a, "mot de passe du coffre du projet B", embedder=LocalHashEmbedder()
    )

    assert "coffre.md" not in _paths(hits)
    assert "ailleurs.md" not in _paths(hits)
    shared = await search(session, scope_a, "service achats", embedder=LocalHashEmbedder())
    assert _paths(shared)[0] == "charte.md"  # workspace-wide documents stay visible


async def test_text_search_works_before_any_vector_exists(session: AsyncSession) -> None:
    hits = await search(session, Scope(session.info["w"], session.info["a"]), "sauvegardes NAS")

    assert hits[0].path == "licences.md"
    assert hits[0].section == "Sauvegardes"
    assert hits[0].matched == ("text",)


async def test_a_query_without_words_returns_nothing(session: AsyncSession) -> None:
    assert await search(session, Scope(session.info["w"]), " ?! ") == []
