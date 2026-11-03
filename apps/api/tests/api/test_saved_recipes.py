"""Reusable factory recipes (task 5.5, spec F38): a delivered run saved as a recipe of
the workspace, then replayed as a new project and run with the same type and request."""

import pytest
from httpx import AsyncClient

from app.context import get_user_id
from app.queue import MemoryQueue
from app.services.identity import LOCAL_WORKSPACE_ID
from nfactory_core.models import Membership, Project, Run, Workspace
from nfactory_core.models.identity import User

pytestmark = pytest.mark.integration

REQUEST = "Un classeur Excel de suivi des dépenses, avec catégorie, montant et date."


def sessions_of(client: AsyncClient):  # type: ignore[no-untyped-def]
    return client._transport.app.state.database.sessions  # type: ignore[attr-defined]


@pytest.fixture
async def delivered(demo_client: AsyncClient) -> AsyncClient:
    """A delivered Excel run and a failed one in the local workspace, and a delivered run
    in another workspace."""
    async with sessions_of(demo_client)() as session:
        session.add(User(id="usr_x", local_identity="x", display_name="X"))
        await session.flush()
        session.add(Workspace(id="wks_x", name="X", owner_id="usr_x"))
        await session.flush()
        session.add(
            Project(
                id="proj_dep",
                workspace_id=LOCAL_WORKSPACE_ID,
                title="Dépenses",
                type="excel",
                description="Suivi des dépenses du service",
            )
        )
        session.add(Project(id="proj_x", workspace_id="wks_x", title="X", type="excel"))
        await session.flush()
        session.add(Run(id="run_ok", project_id="proj_dep", request=REQUEST, state="COMPLETED"))
        session.add(Run(id="run_ko", project_id="proj_dep", request="r", state="FAILED"))
        session.add(Run(id="run_x", project_id="proj_x", request="r", state="COMPLETED"))
        await session.commit()
    return demo_client


async def test_a_delivered_run_becomes_a_recipe(delivered: AsyncClient) -> None:
    response = await delivered.post(
        "/api/v1/saved-recipes", json={"run_id": "run_ok", "name": "Suivi des dépenses"}
    )

    assert response.status_code == 201, response.text
    recipe = response.json()
    assert recipe["id"].startswith("rcp_")
    assert recipe["name"] == "Suivi des dépenses"
    assert recipe["project_type"] == "excel" and recipe["request"] == REQUEST
    assert recipe["source_run_id"] == "run_ok"
    assert recipe["description"] == "Suivi des dépenses du service"
    assert recipe["uses"] == 0
    listed = (await delivered.get("/api/v1/saved-recipes")).json()["items"]
    assert [r["id"] for r in listed] == [recipe["id"]]


async def test_only_a_delivered_run_of_the_workspace_is_saved(delivered: AsyncClient) -> None:
    failed = await delivered.post("/api/v1/saved-recipes", json={"run_id": "run_ko", "name": "n"})
    assert failed.status_code == 409
    assert failed.json()["error"]["code"] == "run_not_delivered"

    other = await delivered.post("/api/v1/saved-recipes", json={"run_id": "run_x", "name": "n"})
    assert other.status_code == 404


async def test_a_recipe_can_be_written_by_hand(delivered: AsyncClient) -> None:
    body = {
        "name": "Inventaire",
        "project_type": "powershell",
        "request": "Inventaire des logiciels.",
    }
    response = await delivered.post("/api/v1/saved-recipes", json=body)

    assert response.status_code == 201
    assert response.json()["source_run_id"] is None


async def test_a_recipe_comes_from_a_run_or_from_fields_not_both(delivered: AsyncClient) -> None:
    both = {"name": "n", "run_id": "run_ok", "project_type": "excel", "request": "r"}
    neither = {"name": "n"}

    assert (await delivered.post("/api/v1/saved-recipes", json=both)).status_code == 422
    assert (await delivered.post("/api/v1/saved-recipes", json=neither)).status_code == 422


async def test_replaying_a_recipe_launches_the_same_request(
    delivered: AsyncClient, queue: MemoryQueue
) -> None:
    created = await delivered.post(
        "/api/v1/saved-recipes", json={"run_id": "run_ok", "name": "Suivi des dépenses"}
    )
    recipe_id = created.json()["id"]

    launched = await delivered.post(
        f"/api/v1/saved-recipes/{recipe_id}/launch",
        json={},
        headers={"Idempotency-Key": "k-1"},
    )

    assert launched.status_code == 201, launched.text
    run = launched.json()
    assert run["project"]["type"] == "excel" and run["project"]["title"] == "Suivi des dépenses"
    assert run["project"]["id"] != "proj_dep"
    assert run["request"] == REQUEST
    assert queue.enqueued == [run["id"]]
    again = await delivered.post(
        f"/api/v1/saved-recipes/{recipe_id}/launch",
        json={},
        headers={"Idempotency-Key": "k-1"},
    )
    assert again.status_code == 200 and again.json()["id"] == run["id"]
    (listed,) = (await delivered.get("/api/v1/saved-recipes")).json()["items"]
    assert listed["uses"] == 1 and listed["last_used_at"] is not None


async def test_a_replay_can_take_its_own_title(delivered: AsyncClient) -> None:
    created = await delivered.post(
        "/api/v1/saved-recipes", json={"run_id": "run_ok", "name": "Suivi"}
    )
    launched = await delivered.post(
        f"/api/v1/saved-recipes/{created.json()['id']}/launch", json={"title": "Dépenses 2027"}
    )

    assert launched.json()["project"]["title"] == "Dépenses 2027"


async def test_saving_and_replaying_are_audited(delivered: AsyncClient) -> None:
    created = await delivered.post(
        "/api/v1/saved-recipes", json={"run_id": "run_ok", "name": "Suivi"}
    )
    recipe_id = created.json()["id"]
    await delivered.post(f"/api/v1/saved-recipes/{recipe_id}/launch", json={})
    assert (await delivered.delete(f"/api/v1/saved-recipes/{recipe_id}")).status_code == 204

    actions = [i["action"] for i in (await delivered.get("/api/v1/audit")).json()["items"]]
    assert actions == ["recipe.delete", "recipe.launch", "recipe.save"]
    assert (await delivered.get("/api/v1/saved-recipes")).json()["items"] == []


async def test_a_viewer_lists_recipes_but_cannot_replay_them(delivered: AsyncClient) -> None:
    created = await delivered.post(
        "/api/v1/saved-recipes", json={"run_id": "run_ok", "name": "Suivi"}
    )
    async with sessions_of(delivered)() as session:
        session.add(User(id="usr_v", local_identity="v", display_name="V"))
        await session.flush()
        session.add(Membership(workspace_id=LOCAL_WORKSPACE_ID, user_id="usr_v", role="viewer"))
        await session.commit()
    app = delivered._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[get_user_id] = lambda: "usr_v"
    try:
        assert len((await delivered.get("/api/v1/saved-recipes")).json()["items"]) == 1
        replay = await delivered.post(
            f"/api/v1/saved-recipes/{created.json()['id']}/launch", json={}
        )
        assert replay.status_code == 403
    finally:
        app.dependency_overrides.clear()


async def test_a_recipe_of_another_workspace_is_missing(delivered: AsyncClient) -> None:
    assert (
        await delivered.post("/api/v1/saved-recipes/rcp_nope/launch", json={})
    ).status_code == 404
    assert (await delivered.delete("/api/v1/saved-recipes/rcp_nope")).status_code == 404
