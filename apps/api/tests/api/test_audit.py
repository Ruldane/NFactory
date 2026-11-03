"""The audit log (task 5.4, spec §15): sensitive actions are recorded with who, what and
the decision; details are redacted; each member reads only their workspaces' entries."""

import pytest
from httpx import AsyncClient

from app.services.identity import LOCAL_WORKSPACE_ID
from nfactory_core.models import Approval, AuditLog, Project, Run, Workspace
from nfactory_core.models.identity import User

pytestmark = pytest.mark.integration

LIMITS = {"max_llm_calls": 50, "max_agent_steps": 60, "max_repair_attempts": 2}


def sessions_of(client: AsyncClient):  # type: ignore[no-untyped-def]
    return client._transport.app.state.database.sessions  # type: ignore[attr-defined]


async def test_a_settings_change_is_audited(client: AsyncClient) -> None:
    assert (await client.put("/api/v1/settings/run-limits", json=LIMITS)).status_code == 200

    (entry,) = (await client.get("/api/v1/audit")).json()["items"]
    assert entry["action"] == "settings.run_limits"
    assert entry["actor_id"] == "usr_local" and entry["actor_name"] == "Moi (local)"
    assert entry["target"] == LOCAL_WORKSPACE_ID and entry["decision"] == "applied"
    assert entry["details"]["max_llm_calls"] == 50


async def test_cancel_and_reject_are_audited_newest_first(client: AsyncClient) -> None:
    async with sessions_of(client)() as session:
        session.add(Project(id="proj_a", workspace_id=LOCAL_WORKSPACE_ID, title="A", type="api"))
        await session.flush()
        session.add(Run(id="run_q", project_id="proj_a", request="r", state="QUEUED"))
        session.add(Run(id="run_p", project_id="proj_a", request="r", state="APPROVAL_PENDING"))
        await session.flush()
        session.add(
            Approval(id="apr_1", run_id="run_p", action_type="provider_fallback", summary="s")
        )
        await session.commit()

    assert (await client.post("/api/v1/runs/run_q/cancel")).status_code == 200
    assert (await client.post("/api/v1/runs/run_p/approvals/apr_1/reject")).status_code == 200

    items = (await client.get("/api/v1/audit")).json()["items"]
    assert [(i["action"], i["target"], i["decision"]) for i in items] == [
        ("approval.decided", "apr_1", "rejected"),
        ("run.cancel", "run_q", "applied"),
    ]


async def test_a_provider_key_never_reaches_the_audit(provider_client: AsyncClient) -> None:
    key = "sk-ant-api03-" + "q" * 40
    saved = await provider_client.put(
        "/api/v1/providers/anthropic_api/configuration", json={"api_key": key}
    )
    assert saved.status_code == 200, saved.text

    response = await provider_client.get("/api/v1/audit")
    assert key not in response.text
    (entry,) = response.json()["items"]
    assert (entry["action"], entry["target"]) == ("provider.configure", "anthropic_api")


async def test_entries_of_another_workspace_stay_hidden(client: AsyncClient) -> None:
    async with sessions_of(client)() as session:
        session.add(User(id="usr_x", local_identity="x", display_name="X"))
        await session.flush()
        session.add(Workspace(id="wks_x", name="X", owner_id="usr_x"))
        await session.flush()
        session.add(
            AuditLog(workspace_id="wks_x", actor_id="usr_x", action="run.cancel", target="run_x")
        )
        await session.commit()

    assert (await client.get("/api/v1/audit")).json()["items"] == []


async def test_the_log_pages_backwards(client: AsyncClient) -> None:
    for calls in (10, 20, 30):
        limits = {**LIMITS, "max_llm_calls": calls}
        await client.put("/api/v1/settings/run-limits", json=limits)

    first = (await client.get("/api/v1/audit", params={"limit": 2})).json()
    assert [i["details"]["max_llm_calls"] for i in first["items"]] == [30, 20]
    rest = (
        await client.get("/api/v1/audit", params={"limit": 2, "before": first["next_before"]})
    ).json()
    assert [i["details"]["max_llm_calls"] for i in rest["items"]] == [10]
    assert rest["next_before"] is None
