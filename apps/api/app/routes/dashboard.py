from fastapi import APIRouter

from app.context import Context, Session
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard import build_summary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
async def summary(session: Session, ctx: Context) -> DashboardSummary:
    return await build_summary(session, ctx)
