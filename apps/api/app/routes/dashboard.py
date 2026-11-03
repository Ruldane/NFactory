from typing import Annotated

from fastapi import APIRouter, Query

from app.context import Context, Session
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard import build_summary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
async def summary(
    session: Session,
    ctx: Context,
    days: Annotated[int | None, Query(ge=1, le=365)] = None,
    project_type: Annotated[str | None, Query(pattern=r"^[a-z][a-z0-9_]{0,29}$")] = None,
) -> DashboardSummary:
    """Overview KPIs for the last `days` days and one project type, both optional."""
    return await build_summary(session, ctx, days=days, project_type=project_type)
