"""The audit log (task 5.4, spec §15): who did which sensitive action, on what, with
which decision. Details pass through `redact` before they are stored; reads are scoped
to the workspaces the caller may audit, newest first.

Interface: record, record_for_run, audit_page.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.access import AuditEntry, AuditPage
from app.services.identity import RequestContext
from nfactory_core.events.redaction import redact
from nfactory_core.models import AuditLog, Project, Run
from nfactory_core.models.identity import User


def record(
    session: AsyncSession,
    ctx: RequestContext,
    action: str,
    target: str,
    *,
    workspace_id: str | None = None,
    decision: str = "applied",
    details: dict[str, Any] | None = None,
) -> None:
    """Add an entry to the session; it is written with the action's own commit."""
    session.add(
        AuditLog(
            workspace_id=workspace_id or ctx.default_workspace_id,
            actor_id=ctx.user_id,
            action=action,
            target=target[:200],
            decision=decision,
            redacted_details=redact(details or {}),
        )
    )


def record_anonymous(
    session: AsyncSession,
    action: str,
    target: str,
    *,
    workspace_id: str,
    decision: str,
    details: dict[str, Any] | None = None,
) -> None:
    """An entry with no member behind it, such as a refused sign-in."""
    session.add(
        AuditLog(
            workspace_id=workspace_id,
            actor_id=None,
            action=action,
            target=target[:200],
            decision=decision,
            redacted_details=redact(details or {}),
        )
    )


async def audit_page(
    session: AsyncSession, ctx: RequestContext, *, limit: int, before: int | None
) -> AuditPage:
    query = (
        select(AuditLog, User.display_name)
        .outerjoin(User, User.id == AuditLog.actor_id)
        .where(AuditLog.workspace_id.in_(ctx.workspace_ids))
        .order_by(AuditLog.id.desc())
        .limit(limit + 1)
    )
    if before is not None:
        query = query.where(AuditLog.id < before)
    rows = (await session.execute(query)).all()
    page = rows[:limit]
    items = [
        AuditEntry(
            id=entry.id,
            timestamp=entry.timestamp,
            actor_id=entry.actor_id,
            actor_name=name,
            action=entry.action,
            target=entry.target,
            decision=entry.decision,
            details=entry.redacted_details or {},
        )
        for entry, name in page
    ]
    more = len(rows) > limit
    return AuditPage(items=items, next_before=items[-1].id if more and items else None)


async def record_for_run(
    sessions: async_sessionmaker[AsyncSession],
    ctx: RequestContext,
    action: str,
    run_id: str,
    *,
    target: str | None = None,
    decision: str = "applied",
    details: dict[str, Any] | None = None,
) -> None:
    """Record an action on a run, in the run's own workspace, in its own transaction."""
    async with sessions() as session:
        workspace_id = await session.scalar(
            select(Project.workspace_id)
            .join(Run, Run.project_id == Project.id)
            .where(Run.id == run_id)
        )
        record(
            session,
            ctx,
            action,
            target or run_id,
            workspace_id=workspace_id,
            decision=decision,
            details=details,
        )
        await session.commit()
