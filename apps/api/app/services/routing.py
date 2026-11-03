"""Workspace routing (task 2.8): saved in `data_policy`, frozen into each run at launch."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError
from app.schemas.providers import RoleOut, RoutingOut
from app.services import model_catalog
from app.services.identity import RequestContext
from nfactory_core.config import Settings
from nfactory_core.connections import connection_facts, workspace_connections
from nfactory_core.models import Workspace
from nfactory_core.routing import (
    ROLE_LABELS,
    ROLES,
    RoutingConfig,
    RoutingError,
    demo_routing,
    freeze_routing,
)

_POLICY_KEY = "routing"


async def routing_config(session: AsyncSession, workspace_id: str) -> RoutingConfig:
    workspace = await session.get_one(Workspace, workspace_id)
    saved = (workspace.data_policy or {}).get(_POLICY_KEY)
    return RoutingConfig.model_validate(saved) if isinstance(saved, dict) else RoutingConfig()


async def routing_view(session: AsyncSession, ctx: RequestContext) -> RoutingOut:
    return RoutingOut(
        routing=await routing_config(session, ctx.default_workspace_id),
        roles=[RoleOut(id=role, label=ROLE_LABELS[role]) for role in ROLES],
    )


async def save_routing(
    session: AsyncSession, ctx: RequestContext, config: RoutingConfig
) -> RoutingOut:
    workspace = await session.get_one(Workspace, ctx.default_workspace_id)
    # Reassign the dict: in-place changes to a JSON column are not tracked.
    workspace.data_policy = {**(workspace.data_policy or {}), _POLICY_KEY: config.model_dump()}
    await session.commit()
    return await routing_view(session, ctx)


async def launch_engines(
    session: AsyncSession, workspace_id: str, settings: Settings
) -> dict[str, Any]:
    """The run's `provider_config`, or a refusal saying what to fix (never a silent pick)."""
    config = await routing_config(session, workspace_id)
    if not config.configured:
        if settings.nfactory_demo_mode:
            return demo_routing()
        raise AppError(
            409,
            "no_model_configured",
            "Aucun moteur IA configuré : connectez un fournisseur dans Moteurs IA et "
            "choisissez un moteur par défaut, ou activez le mode démo.",
        )
    facts = connection_facts(await workspace_connections(session, workspace_id))
    prices: dict[tuple[str, str], dict[str, float] | None] = {}
    for role in ROLES:
        route = config.route_for(role)
        if route is not None and (route.provider, route.model) not in prices:
            prices[(route.provider, route.model)] = await model_catalog.price_of(
                session, route.provider, route.model
            )
    try:
        return freeze_routing(config, facts, lambda p, m: prices.get((p, m)))
    except RoutingError as exc:
        raise AppError(409, exc.code, exc.message) from None
