"""The approval center (task 5.4): the decisions waiting in the caller's workspaces.
Deciding stays on the run (`/runs/{id}/approvals/{id}/approve|reject`).

Interface: list_approvals.
"""

from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.access import ApprovalItem
from app.services.identity import RequestContext
from nfactory_core.models import Approval, Project, Run

ACTION_LABELS = {
    "provider_fallback": "Changement de moteur",
    "plan": "Validation du plan",
    "github_push": "Publication GitHub",
    "privileged_exec": "Exécution privilégiée",
}


async def list_approvals(
    session: AsyncSession, ctx: RequestContext, status: Literal["pending", "all"]
) -> list[ApprovalItem]:
    query = (
        select(Approval, Run.state, Project.id, Project.title)
        .join(Run, Run.id == Approval.run_id)
        .join(Project, Project.id == Run.project_id)
        .where(Project.workspace_id.in_(ctx.workspace_ids))
        .order_by(Approval.created_at.desc())
        .limit(200)
    )
    if status == "pending":
        query = query.where(Approval.status == "pending")
    rows = (await session.execute(query)).all()
    return [
        ApprovalItem(
            id=approval.id,
            status=approval.status,
            action_type=approval.action_type,
            action_label=ACTION_LABELS.get(approval.action_type, approval.action_type),
            summary=approval.summary,
            run_id=approval.run_id,
            run_state=run_state,
            project_id=project_id,
            project_title=title,
            created_at=approval.created_at,
            decided_at=approval.decided_at,
        )
        for approval, run_state, project_id, title in rows
    ]
