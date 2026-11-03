"""Engine failure approvals (task 2.8): the user decides, the run never switches alone."""

from typing import Any

import httpx
import pytest
import respx
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import create_async_engine

from app.queue import MemoryQueue
from nfactory_core.models import Approval, Run
from nfactory_core.routing import ROLES

pytestmark = pytest.mark.integration

KEY = "sk-approval-test-0123456789abcdefghijkl"
OPENAI = "https://api.openai.com/v1"


def routed(model: str = "model-x", *, local_only: bool = False) -> dict[str, Any]:
    route = {"provider": "openai_api", "model": model, "pricing": None}
    return {
        "mode": "routed",
        "routes": {role: dict(route) for role in ROLES},
        "fallback": "ask_user",
        "local_only": local_only,
    }


async def paused_run(client: AsyncClient, database_url: str, **routing: Any) -> tuple[str, str]:
    """A run waiting for a decision after its engine failed (as the worker leaves it)."""
    await client.put("/api/v1/providers/openai_api/configuration", json={"api_key": KEY})
    with respx.mock:
        respx.get(f"{OPENAI}/models").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "model-x"}, {"id": "model-y"}]})
        )
        assert (await client.post("/api/v1/providers/openai_api/validate")).json()["ok"]
    body = {"title": "Note", "type": "document", "description": ""}
    project_id = (await client.post("/api/v1/projects", json=body)).json()["id"]
    run_id = (
        await client.post(f"/api/v1/projects/{project_id}/runs", json={"request": "Une note"})
    ).json()["id"]
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.execute(
            update(Run)
            .where(Run.id == run_id)
            .values(state="APPROVAL_PENDING", provider_config=routed(**routing))
        )
        approval_id = "apr_test_0001"
        await conn.execute(
            Approval.__table__.insert().values(
                id=approval_id,
                run_id=run_id,
                action_type="provider_fallback",
                summary="OpenAI : quota ou crédit épuisé.",
                details={
                    "role": "requirements",
                    "provider": "openai_api",
                    "model": "model-x",
                    "kind": "quota",
                    "message": "OpenAI : quota ou crédit épuisé.",
                },
                status="pending",
            )
        )
    await engine.dispose()
    return run_id, approval_id


async def test_a_paused_run_shows_the_decision_to_make(
    provider_client: AsyncClient, migrated_database_url: str
) -> None:
    run_id, approval_id = await paused_run(provider_client, migrated_database_url)

    run = (await provider_client.get(f"/api/v1/runs/{run_id}")).json()

    assert run["state"] == "APPROVAL_PENDING"
    assert run["pending_approval"]["id"] == approval_id
    assert run["pending_approval"]["details"]["kind"] == "quota"


async def test_approving_a_replacement_reroutes_the_failed_engine_and_requeues(
    provider_client: AsyncClient, migrated_database_url: str, queue: MemoryQueue
) -> None:
    run_id, approval_id = await paused_run(provider_client, migrated_database_url)
    queue.enqueued.clear()

    response = await provider_client.post(
        f"/api/v1/runs/{run_id}/approvals/{approval_id}/approve",
        json={"provider": "openai_api", "model": "model-y"},
    )

    assert response.status_code == 200, response.text
    run = response.json()
    assert run["state"] == "QUEUED"
    assert {e["model"] for e in run["engines"].values()} == {"model-y"}
    assert run["pending_approval"] is None
    assert queue.enqueued == [run_id]


async def test_approving_without_replacement_retries_the_same_engine(
    provider_client: AsyncClient, migrated_database_url: str, queue: MemoryQueue
) -> None:
    run_id, approval_id = await paused_run(provider_client, migrated_database_url)

    run = (
        await provider_client.post(
            f"/api/v1/runs/{run_id}/approvals/{approval_id}/approve", json={}
        )
    ).json()

    assert run["state"] == "QUEUED"
    assert {e["model"] for e in run["engines"].values()} == {"model-x"}


async def test_rejecting_fails_the_run_with_the_reason(
    provider_client: AsyncClient, migrated_database_url: str, queue: MemoryQueue
) -> None:
    run_id, approval_id = await paused_run(provider_client, migrated_database_url)
    queue.enqueued.clear()

    run = (
        await provider_client.post(f"/api/v1/runs/{run_id}/approvals/{approval_id}/reject")
    ).json()

    assert run["state"] == "FAILED"
    assert "quota" in run["error"]
    assert {s["state"] for s in run["steps"]} == {"SKIPPED"}
    assert queue.enqueued == []


async def test_a_replacement_must_respect_local_only(
    provider_client: AsyncClient, migrated_database_url: str
) -> None:
    run_id, approval_id = await paused_run(provider_client, migrated_database_url, local_only=True)

    response = await provider_client.post(
        f"/api/v1/runs/{run_id}/approvals/{approval_id}/approve",
        json={"provider": "openai_api", "model": "model-y"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "local_only_violation"


async def test_a_decision_is_taken_only_once(
    provider_client: AsyncClient, migrated_database_url: str
) -> None:
    run_id, approval_id = await paused_run(provider_client, migrated_database_url)
    url = f"/api/v1/runs/{run_id}/approvals/{approval_id}"
    await provider_client.post(f"{url}/reject")

    again = await provider_client.post(f"{url}/approve", json={})

    assert again.status_code == 409
    assert again.json()["error"]["code"] == "approval_resolved"


async def test_an_unknown_approval_is_not_found(
    provider_client: AsyncClient, migrated_database_url: str
) -> None:
    run_id, _ = await paused_run(provider_client, migrated_database_url)

    response = await provider_client.post(f"/api/v1/runs/{run_id}/approvals/apr_nope/reject")

    assert response.status_code == 404
