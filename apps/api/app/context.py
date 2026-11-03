"""FastAPI dependencies shared by routes."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import get_session
from app.queue import JobQueue
from app.services.identity import RequestContext, local_context
from app.services.local_runtimes import BridgeClient
from app.services.previews import PreviewControl
from app.services.providers import ProviderDeps
from app.wakeups import Wakeups
from nfactory_core.config import Settings

Session = Annotated[AsyncSession, Depends(get_session)]


async def get_context(session: Session) -> RequestContext:
    return await local_context(session)


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
AppSettings = Annotated[Settings, Depends(get_settings_dep)]
Sessions = Annotated[async_sessionmaker[AsyncSession], Depends(get_sessions)]
Queue = Annotated[JobQueue, Depends(get_queue)]
RunWakeups = Annotated[Wakeups, Depends(get_wakeups)]
Providers = Annotated[ProviderDeps, Depends(get_provider_deps)]
Previews = Annotated[PreviewControl | None, Depends(get_previews)]
Bridge = Annotated[BridgeClient, Depends(get_bridge)]
