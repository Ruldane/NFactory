"""Child runs (spec §3.5, scenario E, task 3.11): a change request on a delivered project
starts from the delivered run instead of from scratch."""

from typing import Any

import pytest
from httpx import AsyncClient

from nfactory_core.models import Run

pytestmark = pytest.mark.integration


async def delivered_run(client: AsyncClient, *, state: str = "COMPLETED") -> tuple[str, str]:
    body = {"title": "Annuaire", "type": "api", "description": ""}
    project = (await client.post("/api/v1/projects", json=body)).json()["id"]
    launched = await client.post(
        f"/api/v1/projects/{project}/runs", json={"request": "Une API d'annuaire des contacts"}
    )
    run_id = launched.json()["id"]
    await _set_state(client, run_id, state)
    return project, run_id


async def _set_state(client: AsyncClient, run_id: str, state: str) -> None:
    sessions = client._transport.app.state.database.sessions  # type: ignore[attr-defined]
    async with sessions() as session:
        (await session.get_one(Run, run_id)).state = state
        await session.commit()


async def change(client: AsyncClient, project: str, parent: Any) -> Any:
    return await client.post(
        f"/api/v1/projects/{project}/runs",
        json={"request": "Ajoute un filtre par département", "parent_run_id": parent},
    )


async def test_a_change_request_starts_a_child_of_the_delivered_run(client: AsyncClient) -> None:
    project, parent = await delivered_run(client)

    response = await change(client, project, parent)

    assert response.status_code == 201, response.text
    child = response.json()
    assert child["parent_run_id"] == parent
    assert child["request"] == "Ajoute un filtre par département"
    detail = (await client.get(f"/api/v1/runs/{child['id']}")).json()
    assert detail["parent_run_id"] == parent


async def test_a_first_run_has_no_parent(client: AsyncClient) -> None:
    _, run_id = await delivered_run(client)

    assert (await client.get(f"/api/v1/runs/{run_id}")).json()["parent_run_id"] is None


@pytest.mark.parametrize("state", ["FAILED", "RUNNING", "CANCELLED"])
async def test_only_a_delivered_run_can_be_changed(client: AsyncClient, state: str) -> None:
    project, parent = await delivered_run(client, state=state)

    response = await change(client, project, parent)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "parent_not_completed"


async def test_the_parent_must_belong_to_the_same_project(client: AsyncClient) -> None:
    _, parent = await delivered_run(client)
    other_project, _ = await delivered_run(client)

    response = await change(client, other_project, parent)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_an_unknown_parent_is_not_found(client: AsyncClient) -> None:
    project, _ = await delivered_run(client)

    assert (await change(client, project, "run_nope")).status_code == 404
