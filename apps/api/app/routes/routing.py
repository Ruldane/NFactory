"""Role routing: which engine answers for which agent in new runs."""

from fastapi import APIRouter

from app.context import CanConfigure, Context, Session
from app.schemas.providers import RoutingOut
from app.services import audit, routing
from nfactory_core.routing import RoutingConfig

router = APIRouter(prefix="/routing", tags=["providers"])


@router.get("")
async def get_routing(session: Session, ctx: Context) -> RoutingOut:
    return await routing.routing_view(session, ctx)


@router.put("")
async def put_routing(config: RoutingConfig, session: Session, ctx: CanConfigure) -> RoutingOut:
    """Saved for new runs; a launched run keeps the engines it started with."""
    view = await routing.save_routing(session, ctx, config)
    details = config.model_dump(mode="json")
    audit.record(session, ctx, "routing.update", ctx.default_workspace_id, details=details)
    await session.commit()
    return view
