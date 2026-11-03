"""Background indexing (task 3.3): the worker fills the vector index of a workspace."""

import json
from collections.abc import AsyncIterator

import httpx
import pytest
import respx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.services.identity import LOCAL_WORKSPACE_ID, ensure_local_identity
from nfactory_core.config import Settings
from nfactory_core.knowledge import Scope, ingest
from nfactory_core.knowledge.embedders import LOCAL_KEY
from nfactory_core.models import DocumentChunk, ProviderConnection, Workspace
from nfactory_core.secrets import SecretStore
from nfactory_worker.jobs.indexing import index_pending_workspaces, index_workspace

pytestmark = pytest.mark.integration

Sessions = async_sessionmaker[AsyncSession]
MASTER = "worker-tests-master-key-0123456789abcdef"
KEY = "sk-index-test-0123456789abcdefghijkl"
EMBED = "https://api.openai.com/v1/embeddings"
GUIDE = b"# Licences\n\nRenouveler 30 jours avant.\n\n# Achats\n\nService achats.\n"


@pytest.fixture
async def sessions(migrated_database_url: str) -> AsyncIterator[Sessions]:
    engine = create_async_engine(migrated_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await ensure_local_identity(session)
        await ingest(session, Scope(LOCAL_WORKSPACE_ID), "licences.md", GUIDE)
        await session.commit()
    yield factory
    await engine.dispose()


SETTINGS = Settings(nfactory_secret_key=MASTER)  # type: ignore[arg-type]


async def _keys(sessions: Sessions) -> list[str | None]:
    async with sessions() as session:
        return list((await session.scalars(select(DocumentChunk.embedding_model))).all())


async def _use_openai(sessions: Sessions) -> None:
    async with sessions() as session:
        session.add(
            ProviderConnection(
                workspace_id=LOCAL_WORKSPACE_ID,
                kind="openai_api",
                display_name="OpenAI",
                status="connected",
                secret_ref=await SecretStore(MASTER).put(session, LOCAL_WORKSPACE_ID, KEY),
            )
        )
        workspace = await session.get_one(Workspace, LOCAL_WORKSPACE_ID)
        workspace.data_policy = {
            **(workspace.data_policy or {}),
            "knowledge": {"embedding": {"provider": "openai_api", "model": "embed-x"}},
        }
        await session.commit()


async def _policy(sessions: Sessions) -> dict[str, object]:
    async with sessions() as session:
        workspace = await session.get_one(Workspace, LOCAL_WORKSPACE_ID)
        return dict((workspace.data_policy or {}).get("knowledge") or {})


async def test_the_local_fingerprint_indexes_without_network(sessions: Sessions) -> None:
    report = await index_workspace(sessions, LOCAL_WORKSPACE_ID, SETTINGS)

    assert report.embedded == 2 and report.error is None
    assert await _keys(sessions) == [LOCAL_KEY, LOCAL_KEY]


@respx.mock
async def test_a_connected_provider_computes_the_vectors(sessions: Sessions) -> None:
    await _use_openai(sessions)
    route = respx.post(EMBED).mock(
        side_effect=lambda request: httpx.Response(
            200,
            json={
                "data": [
                    {"index": i, "embedding": [0.1 * (i + 1), 0.5]}
                    for i in range(len(json.loads(request.content)["input"]))
                ],
                "usage": {"prompt_tokens": 9, "total_tokens": 9},
            },
        )
    )

    report = await index_workspace(sessions, LOCAL_WORKSPACE_ID, SETTINGS)

    assert route.called and report.embedded == 2
    assert await _keys(sessions) == ["openai_api:embed-x"] * 2
    assert route.calls[0].request.headers["authorization"] == f"Bearer {KEY}"


@respx.mock
async def test_a_failing_provider_is_recorded_and_never_replaced(sessions: Sessions) -> None:
    await _use_openai(sessions)
    respx.post(EMBED).mock(return_value=httpx.Response(401, json={"error": {"message": "no"}}))

    report = await index_workspace(sessions, LOCAL_WORKSPACE_ID, SETTINGS)

    assert report.embedded == 0
    assert report.error and "OpenAI" in report.error
    assert await _keys(sessions) == [None, None]  # no local vectors slipped in instead
    assert "OpenAI" in str((await _policy(sessions))["index_error"])


@respx.mock
async def test_a_later_success_clears_the_error(sessions: Sessions) -> None:
    await _use_openai(sessions)
    respx.post(EMBED).mock(return_value=httpx.Response(401, json={}))
    await index_workspace(sessions, LOCAL_WORKSPACE_ID, SETTINGS)
    respx.post(EMBED).mock(
        return_value=httpx.Response(
            200, json={"data": [{"index": 0, "embedding": [1.0]}, {"index": 1, "embedding": [2.0]}]}
        )
    )

    await index_workspace(sessions, LOCAL_WORKSPACE_ID, SETTINGS)

    assert (await _policy(sessions)).get("index_error") is None


async def test_the_periodic_pass_indexes_every_workspace_with_pending_chunks(
    sessions: Sessions,
) -> None:
    indexed = await index_pending_workspaces(sessions, SETTINGS)

    assert indexed == [LOCAL_WORKSPACE_ID]
    assert await index_pending_workspaces(sessions, SETTINGS) == []  # nothing left
