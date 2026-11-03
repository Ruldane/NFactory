"""Local-mode identity: one local user owning one workspace.

Team mode (phase 5) replaces this with real authentication; callers only depend on
`RequestContext`, so the seam stays the same.
"""

from dataclasses import dataclass

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
    workspace_ids = frozenset(
        await session.scalars(
            select(Membership.workspace_id).where(Membership.user_id == LOCAL_USER_ID)
        )
    )
    return RequestContext(
        user_id=LOCAL_USER_ID,
        workspace_ids=workspace_ids,
        default_workspace_id=LOCAL_WORKSPACE_ID,
    )
