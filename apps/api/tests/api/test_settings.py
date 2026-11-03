"""Workspace settings: run limits the user can change, frozen into each new run."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def test_settings_show_the_environment_and_default_limits(client: AsyncClient) -> None:
    response = await client.get("/api/v1/settings")

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "local"
    assert body["demo_mode"] is True
    assert body["sandbox"] in {"isolated", "local"}
    assert body["run_limits"] == {
        "max_llm_calls": 80,
        "max_agent_steps": 100,
        "max_repair_attempts": 3,
    }
    assert body["limit_bounds"]["max_repair_attempts"] == {"min": 0, "max": 10}


async def test_changed_limits_are_kept_and_frozen_into_new_runs(client: AsyncClient) -> None:
    limits = {"max_llm_calls": 12, "max_agent_steps": 60, "max_repair_attempts": 1}

    saved = await client.put("/api/v1/settings/run-limits", json=limits)

    assert saved.status_code == 200
    assert saved.json()["run_limits"] == limits
    assert (await client.get("/api/v1/settings")).json()["run_limits"] == limits
    body = {"title": "Licences", "type": "api", "description": ""}
    project_id = (await client.post("/api/v1/projects", json=body)).json()["id"]
    run = (
        await client.post(f"/api/v1/projects/{project_id}/runs", json={"request": "Une API"})
    ).json()
    assert run["budget"] == limits


@pytest.mark.parametrize(
    "limits",
    [
        {"max_llm_calls": 0, "max_agent_steps": 60, "max_repair_attempts": 1},
        {"max_llm_calls": 10, "max_agent_steps": 5, "max_repair_attempts": 1},
        {"max_llm_calls": 10, "max_agent_steps": 60, "max_repair_attempts": 11},
        {"max_llm_calls": 10, "max_agent_steps": 60},
    ],
)
async def test_out_of_bounds_limits_are_refused(
    client: AsyncClient, limits: dict[str, int]
) -> None:
    response = await client.put("/api/v1/settings/run-limits", json=limits)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert (await client.get("/api/v1/settings")).json()["run_limits"]["max_llm_calls"] == 80
