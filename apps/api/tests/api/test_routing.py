"""Role routing in the API (task 2.8): saved per workspace, frozen into each run."""

import httpx
import pytest
import respx
from httpx import AsyncClient

pytestmark = pytest.mark.integration

KEY = "sk-routing-test-0123456789abcdefghijkl"
OPENAI = "https://api.openai.com/v1"


async def new_project(client: AsyncClient) -> str:
    body = {"title": "Licences", "type": "api", "description": ""}
    return str((await client.post("/api/v1/projects", json=body)).json()["id"])


async def launch(client: AsyncClient, project_id: str) -> httpx.Response:
    return await client.post(f"/api/v1/projects/{project_id}/runs", json={"request": "Une API"})


async def connect_openai(client: AsyncClient) -> None:
    await client.put("/api/v1/providers/openai_api/configuration", json={"api_key": KEY})
    with respx.mock:
        respx.get(f"{OPENAI}/models").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "model-x"}]})
        )
        assert (await client.post("/api/v1/providers/openai_api/validate")).json()["ok"]


async def test_routing_starts_empty_with_ask_user_fallback(provider_client: AsyncClient) -> None:
    body = (await provider_client.get("/api/v1/routing")).json()

    assert body["routing"] == {
        "default": None,
        "roles": {},
        "fallback": "ask_user",
        "local_only": False,
    }
    assert [r["id"] for r in body["roles"]][:2] == ["requirements", "planner"]


async def test_routing_rejects_unknown_roles_and_coding_agents(
    provider_client: AsyncClient,
) -> None:
    bad_role = {"roles": {"chef": {"provider": "openai_api", "model": "m"}}}
    agent = {"default": {"provider": "codex_local", "model": "m"}}

    for body in (bad_role, agent):
        response = await provider_client.put("/api/v1/routing", json=body)
        assert response.status_code == 422


async def test_without_routing_demo_mode_runs_are_flagged_demo(
    provider_client: AsyncClient,
) -> None:
    run = (await launch(provider_client, await new_project(provider_client))).json()

    assert run["is_demo"] is True
    assert run["engines"]["planner"] == {"provider": "demo", "model": "fake-demo-1"}


async def test_routing_to_an_untested_provider_refuses_the_launch(
    provider_client: AsyncClient,
) -> None:
    await provider_client.put("/api/v1/providers/openai_api/configuration", json={"api_key": KEY})
    saved = await provider_client.put(
        "/api/v1/routing", json={"default": {"provider": "openai_api", "model": "model-x"}}
    )
    assert saved.status_code == 200

    response = await launch(provider_client, await new_project(provider_client))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "provider_not_ready"


async def test_a_routed_run_freezes_its_engines_and_is_not_demo(
    provider_client: AsyncClient,
) -> None:
    await connect_openai(provider_client)
    await provider_client.put(
        "/api/v1/providers/openai_api/models/model-x",
        json={"pricing": {"input_per_mtok": 1, "output_per_mtok": 3}},
    )
    await provider_client.put(
        "/api/v1/routing", json={"default": {"provider": "openai_api", "model": "model-x"}}
    )

    run = (await launch(provider_client, await new_project(provider_client))).json()

    assert run["is_demo"] is False
    assert run["engines"]["reviewer"] == {"provider": "openai_api", "model": "model-x"}
    # Changing the routing later does not touch a launched run.
    await provider_client.put("/api/v1/routing", json={})
    again = (await provider_client.get(f"/api/v1/runs/{run['id']}")).json()
    assert again["engines"]["reviewer"]["provider"] == "openai_api"


async def test_local_only_refuses_a_remote_engine_at_launch(provider_client: AsyncClient) -> None:
    await connect_openai(provider_client)
    await provider_client.put(
        "/api/v1/routing",
        json={"default": {"provider": "openai_api", "model": "model-x"}, "local_only": True},
    )

    response = await launch(provider_client, await new_project(provider_client))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "local_only_violation"
