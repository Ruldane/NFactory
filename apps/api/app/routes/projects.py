from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.context import CanBuild, CanConfigure, Context, Session
from app.schemas.common import Page
from app.schemas.projects import (
    ProjectCreate,
    ProjectDetail,
    ProjectOut,
    ProjectType,
    ProjectUpdate,
)
from app.services import audit, projects

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("")
async def list_projects(
    session: Session,
    ctx: Context,
    type: ProjectType | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ProjectOut]:
    return await projects.list_projects(session, ctx, project_type=type, limit=limit, offset=offset)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(session: Session, ctx: CanBuild, data: ProjectCreate) -> ProjectOut:
    return await projects.create_project(session, ctx, data)


@router.get("/{project_id}")
async def get_project(session: Session, ctx: Context, project_id: str) -> ProjectDetail:
    return await projects.get_project(session, ctx, project_id)


@router.patch("/{project_id}")
async def update_project(
    session: Session, ctx: CanBuild, project_id: str, data: ProjectUpdate
) -> ProjectOut:
    return await projects.update_project(session, ctx, project_id, data)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(session: Session, ctx: CanConfigure, project_id: str) -> Response:
    """Delete the project and everything it holds; refused while one of its runs is active."""
    runs = await projects.delete_project(session, ctx, project_id)
    audit.record(session, ctx, "project.deleted", project_id, details={"runs": runs})
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
