"""A member's rights (GDPR art. 15, 17, 20; ADR-0015): get their data, have it erased.

Erasing removes the membership. A member with no other workspace left is anonymised:
the `users` row stays so audit entries and approvals keep a (now pseudonymous) reference.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.context import get_user_id
from app.services.identity import LOCAL_USER_ID, LOCAL_WORKSPACE_ID
from nfactory_core.models import AuditLog, Membership, Project, Run, Workspace
from nfactory_core.models.auth import AuthSession
from nfactory_core.models.identity import User
from nfactory_core.models.runs import Approval

pytestmark = pytest.mark.integration

ADA = "usr_ada"
SUBJECT = "https://accounts.google.com|1234567890"
LATER = datetime.now(UTC) + timedelta(days=7)


@pytest.fixture
def sessions(client: AsyncClient):  # type: ignore[no-untyped-def]
    return client._transport.app.state.database.sessions  # type: ignore[attr-defined]


@pytest.fixture
async def ada(client: AsyncClient, sessions) -> AsyncIterator[str]:  # type: ignore[no-untyped-def]
    """A developer of the local workspace, signed in, with an audit trail and an approval."""
    async with sessions() as session:
        session.add(
            User(id=ADA, email="ada@example.fr", oidc_subject=SUBJECT, display_name="Ada L.")
        )
        await session.flush()
        session.add(Membership(workspace_id=LOCAL_WORKSPACE_ID, user_id=ADA, role="developer"))
        session.add(AuthSession(user_id=ADA, token_hash="f" * 64, expires_at=LATER))
        session.add(Project(id="proj_a", workspace_id=LOCAL_WORKSPACE_ID, title="A", type="api"))
        await session.flush()
        session.add(Run(id="run_a", project_id="proj_a", request="r", state="COMPLETED"))
        await session.flush()
        session.add(Approval(run_id="run_a", action_type="plan", summary="Plan", requester_id=ADA))
        session.add(
            AuditLog(
                workspace_id=LOCAL_WORKSPACE_ID, actor_id=ADA, action="run.cancel", target="run_a"
            )
        )
        await session.commit()
    yield ADA
    client._transport.app.dependency_overrides.clear()  # type: ignore[attr-defined]


def act_as(client: AsyncClient, user_id: str) -> None:
    client._transport.app.dependency_overrides[get_user_id] = lambda: user_id  # type: ignore[attr-defined]


async def test_an_admin_lists_the_members(client: AsyncClient, ada: str) -> None:
    response = await client.get("/api/v1/members")

    assert response.status_code == 200
    members = {m["user_id"]: m for m in response.json()["items"]}
    assert set(members) == {LOCAL_USER_ID, ADA}
    assert members[ADA]["email"] == "ada@example.fr"
    assert (members[ADA]["role"], members[ADA]["role_label"]) == ("developer", "Développeur")
    assert members[LOCAL_USER_ID]["is_owner"] is True and members[ADA]["is_owner"] is False


async def test_a_developer_cannot_list_or_erase_members(client: AsyncClient, ada: str) -> None:
    act_as(client, ada)

    assert (await client.get("/api/v1/members")).status_code == 403
    assert (await client.delete(f"/api/v1/members/{LOCAL_USER_ID}")).status_code == 403


async def test_a_member_downloads_their_own_data(client: AsyncClient, ada: str) -> None:
    act_as(client, ada)

    response = await client.get("/api/v1/me/export")

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert "nfactory-mes-donnees.json" in response.headers["content-disposition"]
    data = response.json()
    assert data["profile"]["email"] == "ada@example.fr"
    assert data["profile"]["sso_subject"] == SUBJECT
    assert data["memberships"] == [
        {"workspace_id": LOCAL_WORKSPACE_ID, "workspace_name": "Mon espace", "role": "developer"}
    ]
    (signed_in,) = data["sessions"]
    assert set(signed_in) == {"created_at", "expires_at", "revoked_at"}  # never the token hash
    assert [entry["action"] for entry in data["audit_entries"]] == ["run.cancel"]
    assert [a["summary"] for a in data["approvals"]] == ["Plan"]
    assert "f" * 64 not in response.text


async def test_the_export_is_audited(client: AsyncClient, ada: str, sessions) -> None:  # type: ignore[no-untyped-def]
    act_as(client, ada)
    await client.get("/api/v1/me/export")

    async with sessions() as session:
        actions = list(
            await session.scalars(select(AuditLog.action).where(AuditLog.actor_id == ADA))
        )
    assert "member.export" in actions


async def test_erasing_a_member_anonymises_them(client: AsyncClient, ada: str, sessions) -> None:  # type: ignore[no-untyped-def]
    response = await client.delete(f"/api/v1/members/{ada}")

    assert response.status_code == 200
    assert response.json() == {"user_id": ADA, "anonymised": True}
    async with sessions() as session:
        user = await session.get_one(User, ADA)
        assert (user.email, user.oidc_subject, user.local_identity) == (None, None, None)
        assert user.display_name == "Membre effacé"
        assert await session.scalar(select(Membership).where(Membership.user_id == ADA)) is None
        assert await session.scalar(select(AuthSession).where(AuthSession.user_id == ADA)) is None
        # The security trail stays, pointing at a now pseudonymous id.
        kept = await session.scalar(select(AuditLog).where(AuditLog.action == "run.cancel"))
        assert kept is not None and kept.actor_id == ADA
        erased = await session.scalar(select(AuditLog).where(AuditLog.action == "member.erased"))
        assert erased is not None and erased.target == ADA
        assert "ada@example.fr" not in str(erased.redacted_details)


async def test_a_member_of_another_workspace_keeps_their_identity(
    client: AsyncClient,
    ada: str,
    sessions,  # type: ignore[no-untyped-def]
) -> None:
    async with sessions() as session:
        session.add(Workspace(id="wks_other", name="Autre", owner_id=LOCAL_USER_ID))
        await session.flush()
        session.add(Membership(workspace_id="wks_other", user_id=ADA, role="viewer"))
        await session.commit()

    response = await client.delete(f"/api/v1/members/{ada}")

    assert response.json() == {"user_id": ADA, "anonymised": False}
    async with sessions() as session:
        user = await session.get_one(User, ADA)
        assert user.email == "ada@example.fr"
        roles = set(
            await session.scalars(select(Membership.workspace_id).where(Membership.user_id == ADA))
        )
    assert roles == {"wks_other"}


async def test_nobody_erases_themselves(client: AsyncClient) -> None:
    response = await client.delete(f"/api/v1/members/{LOCAL_USER_ID}")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "cannot_erase_self"


async def test_a_workspace_owner_is_not_erased(client: AsyncClient, ada: str, sessions) -> None:  # type: ignore[no-untyped-def]
    async with sessions() as session:
        session.add(Workspace(id="wks_ada", name="Celui d'Ada", owner_id=ADA))
        await session.commit()

    response = await client.delete(f"/api/v1/members/{ada}")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "owner_cannot_be_erased"


async def test_someone_outside_the_workspace_is_a_404(client: AsyncClient, sessions) -> None:  # type: ignore[no-untyped-def]
    async with sessions() as session:
        session.add(User(id="usr_far", local_identity="far", display_name="Loin"))
        await session.commit()

    for user_id in ("usr_far", "usr_missing"):
        response = await client.delete(f"/api/v1/members/{user_id}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"
