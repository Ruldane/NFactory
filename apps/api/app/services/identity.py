"""Local-mode identity: one local user owning one workspace.

Team mode (phase 5) replaces this with real authentication; callers only depend on
`RequestContext`, so the seam stays the same.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nfactory_core.models import Membership, User, Workspace

LOCAL_USER_ID = "usr_local"
LOCAL_WORKSPACE_ID = "wks_local"


@dataclass(frozen=True)
class RequestContext:
    user_id: str
    workspace_ids: frozenset[str]
    default_workspace_id: str
    roles: Mapping[str, str] = field(default_factory=dict)  # workspace id -> role


async def ensure_local_identity(session: AsyncSession) -> None:
    """Create the local user and workspace if missing. Idempotent."""
    await session.merge(User(id=LOCAL_USER_ID, local_identity="local", display_name="Moi (local)"))
    await session.flush()
    await session.merge(Workspace(id=LOCAL_WORKSPACE_ID, name="Mon espace", owner_id=LOCAL_USER_ID))
    await session.flush()
    await session.merge(
        Membership(workspace_id=LOCAL_WORKSPACE_ID, user_id=LOCAL_USER_ID, role="owner")
    )
    await session.commit()


async def local_context(session: AsyncSession) -> RequestContext:
    return await context_for(session, LOCAL_USER_ID)


async def context_for(session: AsyncSession, user_id: str) -> RequestContext:
    """The user's workspaces and their role in each, from their memberships."""
    rows = (
        await session.execute(
            select(Membership.workspace_id, Membership.role).where(Membership.user_id == user_id)
        )
    ).all()
    roles = {workspace_id: role for workspace_id, role in rows}
    default = LOCAL_WORKSPACE_ID if LOCAL_WORKSPACE_ID in roles or not roles else min(roles)
    return RequestContext(
        user_id=user_id,
        workspace_ids=frozenset(roles),
        default_workspace_id=default,
        roles=roles,
    )
