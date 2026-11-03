from typing import Annotated, Literal

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.context import CanAudit, Context, Session
from app.schemas.access import ApprovalItem, AuditPage, MeOut, WorkspaceAccess
from app.schemas.common import Items
from app.services.access import ROLE_LABELS, permissions_of
from app.services.approvals import list_approvals
from app.services.audit import audit_page
from nfactory_core.models import Workspace
from nfactory_core.models.identity import User

router = APIRouter(tags=["access"])


@router.get("/me")
async def me(session: Session, ctx: Context) -> MeOut:
    """The caller, their role in each workspace, and what that role allows."""
    user = await session.get(User, ctx.user_id)
    workspaces = list(
        await session.scalars(
            select(Workspace).where(Workspace.id.in_(ctx.workspace_ids)).order_by(Workspace.name)
        )
    )
    return MeOut(
        user_id=ctx.user_id,
        display_name=user.display_name if user else ctx.user_id,
        workspaces=[
            WorkspaceAccess(
                id=w.id,
                name=w.name,
                role=ctx.roles[w.id],
                role_label=ROLE_LABELS.get(ctx.roles[w.id], ctx.roles[w.id]),
                permissions=sorted(permissions_of(ctx.roles[w.id])),
            )
            for w in workspaces
        ],
    )


@router.get("/audit")
async def get_audit(
    session: Session,
    ctx: CanAudit,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    before: Annotated[int | None, Query(ge=1)] = None,
) -> AuditPage:
    """Sensitive actions of the workspaces the caller may audit, newest first."""
    return await audit_page(session, ctx, limit=limit, before=before)


@router.get("/approvals")
async def get_approvals(
    session: Session, ctx: Context, status: Literal["pending", "all"] = "pending"
) -> Items[ApprovalItem]:
    """The approval center: decisions waiting in the caller's workspaces."""
    return Items(items=await list_approvals(session, ctx, status))
