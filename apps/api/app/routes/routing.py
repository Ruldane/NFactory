"""Role routing: which engine answers for which agent in new runs."""

from fastapi import APIRouter

from app.context import Context, Session
from app.schemas.providers import RoutingOut
from app.services import routing
from nfactory_core.routing import RoutingConfig

router = APIRouter(prefix="/routing", tags=["providers"])


@router.get("")
async def get_routing(session: Session, ctx: Context) -> RoutingOut:
    return await routing.routing_view(session, ctx)


@router.put("")
async def put_routing(config: RoutingConfig, session: Session, ctx: Context) -> RoutingOut:
    """Saved for new runs; a launched run keeps the engines it started with."""
    return await routing.save_routing(session, ctx, config)
