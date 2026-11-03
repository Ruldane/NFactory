"""Basic RBAC (task 5.4, spec F33): a member's role decides what they may do in a
workspace. Too low a role gets 403 `forbidden`; an ID from a workspace they cannot act
in stays a 404, exactly like a missing one."""

from collections.abc import Callable

import pytest
from httpx import AsyncClient

from app.context import get_user_id
from app.services.identity import LOCAL_WORKSPACE_ID
from nfactory_core.models import Membership, Project, Run, Workspace
from nfactory_core.models.identity import User

pytestmark = pytest.mark.integration

AsRole = Callable[[str | None], object]


@pytest.fixture
async def as_role(client: AsyncClient):  # type: ignore[no-untyped-def]
    """Act as a user holding `role` in the local workspace (None: not a member)."""
    app = client._transport.app  # type: ignore[attr-defined]
    sessions = app.state.database.sessions

    async def become(role: str | None) -> AsyncClient:
        user_id = f"usr_{role or 'stranger'}"
        async with sessions() as session:
            session.add(User(id=user_id, local_identity=user_id, display_name=role or "x"))
            await session.flush()
            if role:
                session.add(Membership(workspace_id=LOCAL_WORKSPACE_ID, user_id=user_id, role=role))
            await session.commit()
        app.dependency_overrides[get_user_id] = lambda: user_id
        return client

    yield become
    app.dependency_overrides.clear()


@pytest.fixture
async def seeded(client: AsyncClient) -> str:
    """A project with a run in the local workspace; returns the run id."""
    sessions = client._transport.app.state.database.sessions  # type: ignore[attr-defined]
    async with sessions() as session:
        session.add(Project(id="proj_a", workspace_id=LOCAL_WORKSPACE_ID, title="A", type="api"))
        await session.flush()
        session.add(Run(id="run_a", project_id="proj_a", request="r", state="QUEUED"))
        await session.commit()
    return "run_a"


PROJECT = {"title": "Nouveau", "type": "excel"}
LIMITS = {"max_llm_calls": 50, "max_agent_steps": 60, "max_repair_attempts": 2}


async def test_a_viewer_reads_but_changes_nothing(as_role, seeded: str) -> None:  # type: ignore[no-untyped-def]
    client = await as_role("viewer")

    assert (await client.get("/api/v1/projects")).status_code == 200
    assert (await client.get(f"/api/v1/runs/{seeded}")).status_code == 200
    created = await client.post("/api/v1/projects", json=PROJECT)
    assert created.status_code == 403
    error = created.json()["error"]
    assert error["code"] == "forbidden" and "lecteur" in error["message"].lower()
    assert (await client.post(f"/api/v1/runs/{seeded}/cancel")).status_code == 403
    assert (await client.put("/api/v1/settings/run-limits", json=LIMITS)).status_code == 403


async def test_a_reviewer_decides_approvals_but_builds_nothing(as_role, seeded: str) -> None:  # type: ignore[no-untyped-def]
    client = await as_role("reviewer")

    assert (await client.post("/api/v1/projects", json=PROJECT)).status_code == 403
    # Allowed to decide: the missing approval is then a plain 404, not a 403.
    reject = await client.post(f"/api/v1/runs/{seeded}/approvals/apr_missing/reject")
    assert reject.status_code == 404
    assert (await client.get("/api/v1/audit")).status_code == 200


async def test_a_developer_builds_but_does_not_configure(as_role, seeded: str) -> None:  # type: ignore[no-untyped-def]
    client = await as_role("developer")

    assert (await client.post("/api/v1/projects", json=PROJECT)).status_code == 201
    assert (await client.post(f"/api/v1/runs/{seeded}/cancel")).status_code == 200
    assert (await client.put("/api/v1/settings/run-limits", json=LIMITS)).status_code == 403
    assert (await client.put("/api/v1/routing", json={"routes": {}})).status_code == 403
    assert (await client.delete("/api/v1/providers/anthropic/configuration")).status_code == 403
    assert (await client.get("/api/v1/audit")).status_code == 403


async def test_an_admin_configures(as_role) -> None:  # type: ignore[no-untyped-def]
    client = await as_role("admin")

    assert (await client.put("/api/v1/settings/run-limits", json=LIMITS)).status_code == 200


async def test_a_stranger_sees_nothing_and_does_nothing(as_role, seeded: str) -> None:  # type: ignore[no-untyped-def]
    client = await as_role(None)

    assert (await client.get("/api/v1/projects")).json()["items"] == []
    assert (await client.get(f"/api/v1/runs/{seeded}")).status_code == 404
    assert (await client.post("/api/v1/projects", json=PROJECT)).status_code == 403


async def test_rights_hold_per_workspace(as_role, client: AsyncClient) -> None:  # type: ignore[no-untyped-def]
    """Owner of the local workspace, only a viewer of another: the other's runs can be
    read there but not cancelled, and that refusal does not reveal more than a 404."""
    sessions = client._transport.app.state.database.sessions  # type: ignore[attr-defined]
    async with sessions() as session:
        session.add(User(id="usr_boss", local_identity="boss", display_name="Boss"))
        await session.flush()
        session.add(Workspace(id="wks_b", name="B", owner_id="usr_boss"))
        await session.flush()
        session.add(Project(id="proj_b", workspace_id="wks_b", title="B", type="api"))
        await session.flush()
        session.add(Run(id="run_b", project_id="proj_b", request="r", state="QUEUED"))
        await session.commit()
    client = await as_role("owner")
    async with sessions() as session:
        session.add(Membership(workspace_id="wks_b", user_id="usr_owner", role="viewer"))
        await session.commit()

    assert (await client.get("/api/v1/runs/run_b")).status_code == 200
    assert (await client.post("/api/v1/runs/run_b/cancel")).status_code == 404


async def test_me_states_each_role_and_what_it_allows(as_role) -> None:  # type: ignore[no-untyped-def]
    client = await as_role("reviewer")

    me = (await client.get("/api/v1/me")).json()
    (workspace,) = me["workspaces"]
    assert me["user_id"] == "usr_reviewer"
    assert workspace["id"] == LOCAL_WORKSPACE_ID and workspace["role"] == "reviewer"
    assert workspace["role_label"] == "Relecteur"
    assert set(workspace["permissions"]) == {"read", "approve", "audit"}


async def test_the_local_user_is_owner_and_may_do_everything(client: AsyncClient) -> None:
    me = (await client.get("/api/v1/me")).json()

    (workspace,) = me["workspaces"]
    assert workspace["role"] == "owner"
    assert set(workspace["permissions"]) == {"read", "approve", "audit", "build", "configure"}
