"""FastAPI dependencies shared by routes."""

from collections.abc import Awaitable, Callable
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import get_session
from app.errors import AppError
from app.queue import JobQueue
from app.services import auth
from app.services.access import Permission, permitted
from app.services.identity import LOCAL_USER_ID, RequestContext, context_for
from app.services.local_runtimes import BridgeClient
from app.services.previews import PreviewControl
from app.services.providers import ProviderDeps
from app.wakeups import Wakeups
from nfactory_core.config import Settings

Session = Annotated[AsyncSession, Depends(get_session)]


_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


async def get_user_id(request: Request, session: Session) -> str:
    """Who is calling. Local mode has one user. SSO mode (ADR-0013) reads the session
    cookie; no valid session is a 401. Tests override this to act as another member."""
    settings: Settings = request.app.state.settings
    if settings.nfactory_auth_mode == "local":
        return LOCAL_USER_ID
    user_id = await auth.user_for(session, request.cookies.get(auth.COOKIE))
    if user_id is None:
        raise AppError(401, "not_authenticated", "Connectez-vous pour continuer.")
    return user_id


def dashboard_origin(settings: Settings) -> str:
    parts = urlsplit(settings.nfactory_oidc_redirect_url)
    return f"{parts.scheme}://{parts.netloc}"


def check_origin(request: Request) -> None:
    """SSO mode: a change must come from the dashboard's own origin (CSRF)."""
    settings: Settings = request.app.state.settings
    if settings.nfactory_auth_mode == "local" or request.method in _SAFE_METHODS:
        return
    if request.headers.get("origin") != dashboard_origin(settings):
        raise AppError(403, "csrf_rejected", "Requête refusée : elle ne vient pas du dashboard.")


async def require_session(request: Request, _user_id: Annotated[str, Depends(get_user_id)]) -> None:
    """Router-wide guard: every API route but health and sign-in needs a session."""
    check_origin(request)


async def get_context(
    session: Session, user_id: Annotated[str, Depends(get_user_id)]
) -> RequestContext:
    return await context_for(session, user_id)


def _requires(permission: Permission) -> Callable[[RequestContext], Awaitable[RequestContext]]:
    async def dependency(ctx: Annotated[RequestContext, Depends(get_context)]) -> RequestContext:
        return permitted(ctx, permission)

    return dependency


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_sessions(request: Request) -> async_sessionmaker[AsyncSession]:
    """For use cases that need several short transactions (events must be visible at once)."""
    sessions: async_sessionmaker[AsyncSession] = request.app.state.database.sessions
    return sessions


def get_provider_deps(request: Request) -> ProviderDeps:
    deps: ProviderDeps = request.app.state.provider_deps
    return deps


def get_queue(request: Request) -> JobQueue:
    queue: JobQueue = request.app.state.queue
    return queue


def get_previews(request: Request) -> PreviewControl | None:
    control: PreviewControl | None = request.app.state.previews
    return control


def get_bridge(request: Request) -> BridgeClient:
    bridge: BridgeClient = request.app.state.bridge
    return bridge


def get_wakeups(request: Request) -> Wakeups:
    wakeups: Wakeups = request.app.state.wakeups
    return wakeups


Context = Annotated[RequestContext, Depends(get_context)]
# Narrowed contexts: the workspaces where the role grants the permission (task 5.4).
PERMISSION_DEPENDENCIES = {
    permission: _requires(permission) for permission in ("build", "approve", "configure", "audit")
}
CanBuild = Annotated[RequestContext, Depends(PERMISSION_DEPENDENCIES["build"])]
CanApprove = Annotated[RequestContext, Depends(PERMISSION_DEPENDENCIES["approve"])]
CanConfigure = Annotated[RequestContext, Depends(PERMISSION_DEPENDENCIES["configure"])]
CanAudit = Annotated[RequestContext, Depends(PERMISSION_DEPENDENCIES["audit"])]
AppSettings = Annotated[Settings, Depends(get_settings_dep)]
Sessions = Annotated[async_sessionmaker[AsyncSession], Depends(get_sessions)]
Queue = Annotated[JobQueue, Depends(get_queue)]
RunWakeups = Annotated[Wakeups, Depends(get_wakeups)]
Providers = Annotated[ProviderDeps, Depends(get_provider_deps)]
Previews = Annotated[PreviewControl | None, Depends(get_previews)]
Bridge = Annotated[BridgeClient, Depends(get_bridge)]
