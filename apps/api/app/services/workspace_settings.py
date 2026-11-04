"""Workspace settings: environment facts, the run limits and the retention policy the
user chose."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.settings import LIMIT_BOUNDS, Bounds, RunLimits, SettingsOut
from app.services.identity import RequestContext
from nfactory_core.config import Settings
from nfactory_core.models import Workspace
from nfactory_core.retention import (
    RETENTION_BOUNDS,
    RETENTION_KEY,
    RetentionPolicy,
    retention_policy,
)

_POLICY_KEY = "run_limits"


def default_limits(settings: Settings) -> RunLimits:
    return RunLimits(
        max_llm_calls=settings.max_llm_calls_per_run,
        max_agent_steps=settings.max_agent_steps,
        max_repair_attempts=settings.max_repair_attempts,
    )


async def run_limits(session: AsyncSession, workspace_id: str, settings: Settings) -> RunLimits:
    """The workspace's limits, or the server defaults where none were saved."""
    workspace = await session.get_one(Workspace, workspace_id)
    saved = (workspace.data_policy or {}).get(_POLICY_KEY) or {}
    return default_limits(settings).model_copy(
        update={key: value for key, value in saved.items() if key in RunLimits.model_fields}
    )


async def settings_view(
    session: AsyncSession, ctx: RequestContext, settings: Settings
) -> SettingsOut:
    workspace = await session.get_one(Workspace, ctx.default_workspace_id)
    return SettingsOut(
        mode=settings.nfactory_mode,
        demo_mode=settings.nfactory_demo_mode,
        sandbox="isolated" if settings.nfactory_sandbox_url else "local",
        run_limits=await run_limits(session, ctx.default_workspace_id, settings),
        limit_bounds={key: Bounds(min=low, max=high) for key, (low, high) in LIMIT_BOUNDS.items()},
        retention=retention_policy(workspace.data_policy),
        retention_bounds={
            key: Bounds(min=low, max=high) for key, (low, high) in RETENTION_BOUNDS.items()
        },
    )


async def save_run_limits(
    session: AsyncSession, ctx: RequestContext, settings: Settings, limits: RunLimits
) -> SettingsOut:
    workspace = await session.get_one(Workspace, ctx.default_workspace_id)
    # Reassign the dict: in-place changes to a JSON column are not tracked.
    workspace.data_policy = {**(workspace.data_policy or {}), _POLICY_KEY: limits.model_dump()}
    await session.commit()
    return await settings_view(session, ctx, settings)


async def save_retention(
    session: AsyncSession, ctx: RequestContext, settings: Settings, policy: RetentionPolicy
) -> SettingsOut:
    """The worker applies it at its next nightly pass (`apply_retention`)."""
    workspace = await session.get_one(Workspace, ctx.default_workspace_id)
    workspace.data_policy = {**(workspace.data_policy or {}), RETENTION_KEY: policy.model_dump()}
    await session.commit()
    return await settings_view(session, ctx, settings)
