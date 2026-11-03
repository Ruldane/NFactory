"""The approval center (task 5.4): every decision waiting in the workspace, in one list."""

import pytest
from httpx import AsyncClient

from app.services.identity import LOCAL_WORKSPACE_ID
from nfactory_core.models import Approval, Project, Run, Workspace
from nfactory_core.models.identity import User

pytestmark = pytest.mark.integration


@pytest.fixture
async def approvals(client: AsyncClient) -> AsyncClient:
    sessions = client._transport.app.state.database.sessions  # type: ignore[attr-defined]
    async with sessions() as session:
        session.add(User(id="usr_x", local_identity="x", display_name="X"))
        await session.flush()
        session.add(Workspace(id="wks_x", name="X", owner_id="usr_x"))
        await session.flush()
        session.add(
            Project(id="proj_a", workspace_id=LOCAL_WORKSPACE_ID, title="Annuaire", type="api")
        )
        session.add(Project(id="proj_x", workspace_id="wks_x", title="Autre", type="api"))
        await session.flush()
        session.add(Run(id="run_a", project_id="proj_a", request="r", state="APPROVAL_PENDING"))
        session.add(Run(id="run_b", project_id="proj_a", request="r", state="FAILED"))
        session.add(Run(id="run_x", project_id="proj_x", request="r", state="APPROVAL_PENDING"))
        await session.flush()
        session.add(
            Approval(
                id="apr_a",
                run_id="run_a",
                action_type="provider_fallback",
                summary="Le moteur Anthropic a échoué (quota).",
                details={"provider": "anthropic", "model": "m1"},
            )
        )
        session.add(
            Approval(
                id="apr_b", run_id="run_b", action_type="provider_fallback", summary="s",
                status="rejected",
            )
        )  # fmt: skip
        session.add(
            Approval(id="apr_x", run_id="run_x", action_type="provider_fallback", summary="s")
        )
        await session.commit()
    return client


async def test_pending_approvals_of_the_workspace_are_listed(approvals: AsyncClient) -> None:
    response = await approvals.get("/api/v1/approvals")

    assert response.status_code == 200
    (item,) = response.json()["items"]
    assert item["id"] == "apr_a" and item["status"] == "pending"
    assert item["run_id"] == "run_a" and item["project_title"] == "Annuaire"
    assert item["action_type"] == "provider_fallback"
    assert item["action_label"] == "Changement de moteur"
    assert item["summary"].startswith("Le moteur Anthropic")


async def test_decided_approvals_are_listed_on_request(approvals: AsyncClient) -> None:
    items = (await approvals.get("/api/v1/approvals", params={"status": "all"})).json()["items"]

    assert {i["id"] for i in items} == {"apr_a", "apr_b"}  # never the other workspace's


async def test_an_unknown_status_filter_is_refused(approvals: AsyncClient) -> None:
    assert (await approvals.get("/api/v1/approvals", params={"status": "nope"})).status_code == 422
