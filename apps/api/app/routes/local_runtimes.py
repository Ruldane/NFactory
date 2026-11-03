"""Local coding tools (codex, claude, gh) detected by the bridge on the user's machine."""

from fastapi import APIRouter, Response

from app.context import Bridge, CanConfigure, Context, Providers, Session
from app.schemas.local_runtimes import LocalRuntimesOut, PairingIn
from app.services import audit, local_runtimes

router = APIRouter(prefix="/local-runtimes", tags=["local-runtimes"])


@router.get("")
async def list_local_runtimes(
    session: Session, ctx: Context, bridge: Bridge, deps: Providers
) -> LocalRuntimesOut:
    """Bridge state and the tools it detected. Never fails: an absent bridge is a state."""
    return await local_runtimes.local_runtimes(session, ctx, bridge, deps.store)


@router.post("/pairing")
async def pair(
    data: PairingIn, session: Session, ctx: CanConfigure, bridge: Bridge, deps: Providers
) -> LocalRuntimesOut:
    """Trade the code shown by the bridge for a token, kept encrypted on the server."""
    view = await local_runtimes.pair(session, ctx, bridge, deps.store, data.code)
    audit.record(session, ctx, "bridge.pair", "local-bridge")  # never the code or the token
    await session.commit()
    return view


@router.delete("/pairing", status_code=204)
async def unpair(session: Session, ctx: CanConfigure, bridge: Bridge, deps: Providers) -> Response:
    await local_runtimes.unpair(session, ctx, bridge, deps.store)
    audit.record(session, ctx, "bridge.unpair", "local-bridge")
    await session.commit()
    return Response(status_code=204)
