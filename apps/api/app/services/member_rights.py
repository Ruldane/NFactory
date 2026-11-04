"""A member's rights (GDPR art. 15, 17, 20; ADR-0015).

- `members`: the members of the caller's workspace.
- `export_data`: everything NFactory links to a member.
- `erase`: remove a member from the caller's workspace. A member left with no workspace
  is anonymised: the `users` row stays, so audit entries and approvals keep a reference
  that no longer identifies anyone. Their sessions go.

Interface: members, export_data, erase.
"""

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError, not_found
from app.schemas.members import (
    ErasureOut,
    ExportApproval,
    ExportAuditEntry,
    ExportMembership,
    ExportProfile,
    ExportSession,
    MemberExport,
    MemberOut,
)
from app.services.access import ROLE_LABELS
from app.services.identity import RequestContext
from nfactory_core.models import AuditLog, Membership, Workspace
from nfactory_core.models.auth import AuthSession
from nfactory_core.models.base import utcnow
from nfactory_core.models.identity import User
from nfactory_core.models.runs import Approval

ERASED_NAME = "Membre effacé"


async def members(session: AsyncSession, ctx: RequestContext) -> list[MemberOut]:
    workspace_id = ctx.default_workspace_id
    owners = set(await session.scalars(select(Workspace.owner_id)))
    rows = (
        await session.execute(
            select(User, Membership.role)
            .join(Membership, Membership.user_id == User.id)
            .where(Membership.workspace_id == workspace_id)
            .order_by(User.display_name, User.id)
        )
    ).all()
    return [
        MemberOut(
            user_id=user.id,
            display_name=user.display_name,
            email=user.email,
            role=role,
            role_label=ROLE_LABELS.get(role, role),
            is_owner=user.id in owners,
            created_at=user.created_at,
        )
        for user, role in rows
    ]


async def export_data(session: AsyncSession, user_id: str) -> MemberExport:
    user = await session.get_one(User, user_id)
    memberships = (
        await session.execute(
            select(Membership.workspace_id, Workspace.name, Membership.role)
            .join(Workspace, Workspace.id == Membership.workspace_id)
            .where(Membership.user_id == user_id)
            .order_by(Workspace.name)
        )
    ).all()
    sign_ins = await session.scalars(
        select(AuthSession).where(AuthSession.user_id == user_id).order_by(AuthSession.created_at)
    )
    entries = await session.scalars(
        select(AuditLog).where(AuditLog.actor_id == user_id).order_by(AuditLog.id)
    )
    approvals = await session.scalars(
        select(Approval)
        .where(or_(Approval.requester_id == user_id, Approval.approver_id == user_id))
        .order_by(Approval.created_at)
    )
    return MemberExport(
        generated_at=utcnow(),
        profile=ExportProfile(
            user_id=user.id,
            display_name=user.display_name,
            email=user.email,
            sso_subject=user.oidc_subject,
            created_at=user.created_at,
        ),
        memberships=[
            ExportMembership(workspace_id=w, workspace_name=name, role=role)
            for w, name, role in memberships
        ],
        sessions=[
            ExportSession(created_at=s.created_at, expires_at=s.expires_at, revoked_at=s.revoked_at)
            for s in sign_ins
        ],
        audit_entries=[
            ExportAuditEntry(
                timestamp=e.timestamp,
                workspace_id=e.workspace_id,
                action=e.action,
                target=e.target,
                decision=e.decision,
                details=e.redacted_details or {},
            )
            for e in entries
        ],
        approvals=[
            ExportApproval(
                run_id=a.run_id,
                action_type=a.action_type,
                summary=a.summary,
                status=a.status,
                requested=a.requester_id == user_id,
                decided=a.approver_id == user_id,
                created_at=a.created_at,
                decided_at=a.decided_at,
            )
            for a in approvals
        ],
    )


async def erase(session: AsyncSession, ctx: RequestContext, user_id: str) -> ErasureOut:
    """Remove `user_id` from the caller's workspace; the caller commits."""
    workspace_id = ctx.default_workspace_id
    membership = await session.get(Membership, (workspace_id, user_id))
    if membership is None:
        raise not_found("Membre")
    if user_id == ctx.user_id:
        raise AppError(
            409, "cannot_erase_self", "Vous ne pouvez pas effacer votre propre compte ici."
        )
    if await session.scalar(select(Workspace.id).where(Workspace.owner_id == user_id).limit(1)):
        raise AppError(
            409,
            "owner_cannot_be_erased",
            "Ce membre est propriétaire d'un espace de travail : transférez-le d'abord.",
        )
    await session.delete(membership)
    await session.flush()
    remaining = await session.scalar(
        select(Membership.workspace_id).where(Membership.user_id == user_id).limit(1)
    )
    if remaining is not None:
        return ErasureOut(user_id=user_id, anonymised=False)
    user = await session.get_one(User, user_id)
    user.email = None
    user.oidc_subject = None
    user.local_identity = None
    user.display_name = ERASED_NAME
    await session.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
    return ErasureOut(user_id=user_id, anonymised=True)
