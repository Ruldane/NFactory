"""Knowledge base API (tasks 3.2 to 3.4): upload, documents, search, embedding engine."""

import json

import httpx
import pytest
import respx
from httpx import AsyncClient

from app.queue import MemoryQueue

pytestmark = pytest.mark.integration

GUIDE = (
    "# Licences\n\nRenouveler chaque licence 30 jours avant.\n\n"
    "# Achats\n\nPasser par le service achats.\n"
)
KEY = "sk-knowledge-test-0123456789abcdefghij"
OPENAI = "https://api.openai.com/v1"


async def upload(
    client: AsyncClient, name: str, data: bytes, project_id: str | None = None
) -> httpx.Response:
    form = {"project_id": project_id} if project_id else {}
    return await client.post("/api/v1/knowledge/documents", files={"file": (name, data)}, data=form)


async def new_project(client: AsyncClient, title: str) -> str:
    body = {"title": title, "type": "api", "description": ""}
    return str((await client.post("/api/v1/projects", json=body)).json()["id"])


async def test_upload_indexes_text_and_queues_vectors(
    client: AsyncClient, queue: MemoryQueue
) -> None:
    response = await upload(client, "licences.md", GUIDE.encode())

    assert response.status_code == 201
    body = response.json()
    assert (body["path"], body["kind"], body["chunks"], body["duplicate"]) == (
        "licences.md",
        "markdown",
        2,
        False,
    )
    assert body["project_id"] is None
    assert queue.indexing  # the worker computes vectors in the background


async def test_identical_reupload_is_a_duplicate(client: AsyncClient) -> None:
    first = (await upload(client, "a.md", GUIDE.encode())).json()

    again = await upload(client, "b.md", GUIDE.encode())

    assert again.status_code == 200
    assert again.json()["duplicate"] is True and again.json()["id"] == first["id"]
    listed = (await client.get("/api/v1/knowledge/documents")).json()["items"]
    assert len(listed) == 1


@pytest.mark.parametrize(
    ("name", "data", "status", "code"),
    [
        ("image.png", b"\x89PNG", 415, "unsupported_file_type"),
        ("vide.md", b"  ", 422, "empty_document"),
        ("gros.txt", b"a" * (10 * 1024 * 1024 + 1), 413, "file_too_large"),
    ],
)
async def test_bad_uploads_are_refused(
    client: AsyncClient, name: str, data: bytes, status: int, code: str
) -> None:
    response = await upload(client, name, data)

    assert response.status_code == status
    assert response.json()["error"]["code"] == code


async def test_a_document_can_be_read_by_line_and_deleted(client: AsyncClient) -> None:
    doc = (await upload(client, "licences.md", GUIDE.encode())).json()

    detail = (await client.get(f"/api/v1/knowledge/documents/{doc['id']}")).json()
    assert detail["content"].splitlines()[2] == "Renouveler chaque licence 30 jours avant."

    assert (await client.delete(f"/api/v1/knowledge/documents/{doc['id']}")).status_code == 204
    missing = await client.get(f"/api/v1/knowledge/documents/{doc['id']}")
    assert missing.status_code == 404


async def test_uploads_are_scoped_to_a_project_of_the_workspace(client: AsyncClient) -> None:
    project = await new_project(client, "Licences")
    unknown = await upload(client, "x.md", GUIDE.encode(), project_id="proj_does_not_exist")
    assert unknown.status_code == 404

    doc = (await upload(client, "x.md", GUIDE.encode(), project_id=project)).json()

    assert doc["project_id"] == project
    listed = (await client.get(f"/api/v1/knowledge/documents?project_id={project}")).json()
    assert [d["id"] for d in listed["items"]] == [doc["id"]]


async def test_search_cites_lines_and_respects_projects(client: AsyncClient) -> None:
    a, b = await new_project(client, "A"), await new_project(client, "B")
    await upload(client, "licences.md", GUIDE.encode(), project_id=a)
    await upload(client, "coffre.md", b"# Coffre\n\nLe code du coffre de B.\n", project_id=b)

    found = (
        await client.get(
            "/api/v1/knowledge/search", params={"q": "renouveler licence", "project_id": a}
        )
    ).json()
    hidden = (
        await client.get(
            "/api/v1/knowledge/search", params={"q": "code du coffre", "project_id": a}
        )
    ).json()

    top = found["hits"][0]
    assert (top["path"], top["start_line"], top["end_line"], top["section"]) == (
        "licences.md",
        1,
        3,
        "Licences",
    )
    assert top["document_id"]
    assert hidden["hits"] == []
    assert found["engine"]["key"] == "local:empreinte-v1"


async def test_the_default_engine_is_local_and_reports_its_progress(client: AsyncClient) -> None:
    await upload(client, "licences.md", GUIDE.encode())

    body = (await client.get("/api/v1/knowledge/settings")).json()

    assert body["embedding"] == {"provider": "local", "model": "empreinte-v1"}
    assert body["index"] == {"total": 2, "embedded": 0}
    offered = {o["provider"] for o in body["options"]}
    assert offered == {"local", "openai_api", "custom_openai_compatible", "ollama_local"}


@pytest.mark.parametrize(
    ("choice", "status", "code"),
    [
        ({"provider": "anthropic_api", "model": "x"}, 422, "embeddings_unsupported"),
        ({"provider": "openai_api", "model": "embed-x"}, 409, "provider_not_ready"),
    ],
)
async def test_unusable_engines_are_refused(
    client: AsyncClient, choice: dict[str, str], status: int, code: str
) -> None:
    response = await client.put("/api/v1/knowledge/settings", json={"embedding": choice})

    assert response.status_code == status
    assert response.json()["error"]["code"] == code


async def test_a_connected_provider_embeds_the_query(
    provider_client: AsyncClient, queue: MemoryQueue
) -> None:
    await provider_client.put("/api/v1/providers/openai_api/configuration", json={"api_key": KEY})
    with respx.mock:
        respx.get(f"{OPENAI}/models").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "embed-x"}]})
        )
        assert (await provider_client.post("/api/v1/providers/openai_api/validate")).json()["ok"]
    saved = await provider_client.put(
        "/api/v1/knowledge/settings",
        json={"embedding": {"provider": "openai_api", "model": "embed-x"}},
    )
    assert saved.status_code == 200
    assert queue.indexing  # switching engine re-indexes

    with respx.mock:
        route = respx.post(f"{OPENAI}/embeddings").mock(
            return_value=httpx.Response(
                200, json={"data": [{"index": 0, "embedding": [0.1, 0.2]}], "usage": {}}
            )
        )
        result = (
            await provider_client.get("/api/v1/knowledge/search", params={"q": "licence"})
        ).json()

    assert json.loads(route.calls[0].request.content)["input"] == ["licence"]
    assert result["engine"]["key"] == "openai_api:embed-x"


async def test_a_failing_engine_is_reported_never_replaced(provider_client: AsyncClient) -> None:
    await provider_client.put("/api/v1/providers/openai_api/configuration", json={"api_key": KEY})
    with respx.mock:
        respx.get(f"{OPENAI}/models").mock(return_value=httpx.Response(200, json={"data": []}))
        await provider_client.post("/api/v1/providers/openai_api/validate")
    await provider_client.put(
        "/api/v1/knowledge/settings",
        json={"embedding": {"provider": "openai_api", "model": "embed-x"}},
    )
    await upload(provider_client, "licences.md", GUIDE.encode())

    with respx.mock:
        respx.post(f"{OPENAI}/embeddings").mock(return_value=httpx.Response(429, json={}))
        result = (
            await provider_client.get("/api/v1/knowledge/search", params={"q": "licence"})
        ).json()

    assert result["engine"]["used"] is False
    assert "OpenAI" in result["engine"]["error"]
    assert result["hits"] and all(h["matched"] == ["text"] for h in result["hits"])


async def test_an_indexing_failure_is_shown_to_the_user(
    client: AsyncClient, migrated_database_url: str
) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.services.identity import LOCAL_WORKSPACE_ID
    from nfactory_core.models import Workspace

    engine = create_async_engine(migrated_database_url)
    async with engine.begin() as connection:
        await connection.execute(
            Workspace.__table__.update()
            .where(Workspace.__table__.c.id == LOCAL_WORKSPACE_ID)
            .values(data_policy={"knowledge": {"index_error": "OpenAI : clé refusée."}})
        )
    await engine.dispose()

    body = (await client.get("/api/v1/knowledge/settings")).json()

    assert body["index_error"] == "OpenAI : clé refusée."
