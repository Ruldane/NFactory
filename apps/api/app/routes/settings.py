from fastapi import APIRouter

from app.context import AppSettings, CanConfigure, Context, Session
from app.schemas.settings import RunLimits, SettingsOut
from app.services import audit, workspace_settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
async def get_settings(session: Session, ctx: Context, settings: AppSettings) -> SettingsOut:
    return await workspace_settings.settings_view(session, ctx, settings)


@router.put("/run-limits")
async def put_run_limits(
    limits: RunLimits, session: Session, ctx: CanConfigure, settings: AppSettings
) -> SettingsOut:
    """Limits for new runs; a run keeps the limits it was launched with."""
    view = await workspace_settings.save_run_limits(session, ctx, settings, limits)
    details = limits.model_dump()
    audit.record(session, ctx, "settings.run_limits", ctx.default_workspace_id, details=details)
    await session.commit()
    return view
