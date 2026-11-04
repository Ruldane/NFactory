"""Project use cases. Every query is scoped to the caller's workspaces.

A project outside the caller's workspaces raises not_found, exactly like a missing one.
"""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError, not_found
from app.schemas.common import Page
from app.schemas.projects import (
    ProjectCreate,
    ProjectDetail,
    ProjectOut,
    ProjectUpdate,
    RunSummary,
)
from app.services.identity import RequestContext
from nfactory_core.models import Project, Run
from nfactory_core.states import TERMINAL_STATES


async def list_projects(
    session: AsyncSession,
    ctx: RequestContext,
    *,
    project_type: str | None,
    limit: int,
    offset: int,
) -> Page[ProjectOut]:
    query = select(Project).where(Project.workspace_id.in_(ctx.workspace_ids))
    if project_type:
        query = query.where(Project.type == project_type)
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = await session.scalars(
        query.order_by(Project.created_at.desc()).limit(limit).offset(offset)
    )
    return Page(
        items=[ProjectOut.model_validate(p) for p in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


async def create_project(
    session: AsyncSession, ctx: RequestContext, data: ProjectCreate
) -> ProjectOut:
    project = Project(workspace_id=ctx.default_workspace_id, **data.model_dump())
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return ProjectOut.model_validate(project)


async def get_project(session: AsyncSession, ctx: RequestContext, project_id: str) -> ProjectDetail:
    project = await _owned(session, ctx, project_id)
    latest = await session.scalar(
        select(Run).where(Run.project_id == project.id).order_by(Run.created_at.desc()).limit(1)
    )
    return ProjectDetail(
        **ProjectOut.model_validate(project).model_dump(),
        latest_run=RunSummary.model_validate(latest) if latest else None,
    )


async def update_project(
    session: AsyncSession, ctx: RequestContext, project_id: str, data: ProjectUpdate
) -> ProjectOut:
    project = await _owned(session, ctx, project_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await session.commit()
    await session.refresh(project)
    return ProjectOut.model_validate(project)


async def _owned(session: AsyncSession, ctx: RequestContext, project_id: str) -> Project:
    project = await session.scalar(
        select(Project).where(Project.id == project_id, Project.workspace_id.in_(ctx.workspace_ids))
    )
    if project is None:
        raise not_found("Projet")
    return project


async def delete_project(session: AsyncSession, ctx: RequestContext, project_id: str) -> int:
    """Delete the project and, through the database's cascades, its runs, deliverables,
    documents and vectors (ADR-0015). Returns the number of runs; the caller commits.
    The worker's sweep then removes the files no run points to."""
    project = await _owned(session, ctx, project_id)
    states = list(await session.scalars(select(Run.state).where(Run.project_id == project.id)))
    finished = {state.value for state in TERMINAL_STATES}
    if any(state not in finished for state in states):
        raise AppError(
            409,
            "project_busy",
            "Un run de ce projet est encore actif : annulez-le ou attendez sa fin.",
        )
    await session.execute(delete(Project).where(Project.id == project.id))
    return len(states)
