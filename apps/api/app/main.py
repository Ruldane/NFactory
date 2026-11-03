"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Database
from app.errors import install_error_handlers
from app.queue import ArqQueue, JobQueue
from app.routes import (
    agent_tasks,
    artifacts,
    dashboard,
    health,
    knowledge,
    local_runtimes,
    projects,
    providers,
    recipes,
    routing,
    runs,
)
from app.routes import settings as settings_routes
from app.services.local_runtimes import BridgeClient, HttpBridge
from app.services.previews import PreviewControl, SupervisorPreviews
from app.services.providers import ProviderDeps
from app.wakeups import RedisWakeups, Wakeups
from nfactory_core.config import Settings, get_settings
from nfactory_core.providers.ssrf import Resolver, system_resolver
from nfactory_core.secrets import SecretStore

API_PREFIX = "/api/v1"


def _previews(settings: Settings) -> PreviewControl | None:
    """Previews need the sandbox supervisor; without it (local dev) they are off."""
    if not settings.nfactory_sandbox_url:
        return None
    token = settings.nfactory_sandbox_token.get_secret_value()
    return SupervisorPreviews(settings.nfactory_sandbox_url, token)


def create_app(
    settings: Settings | None = None,
    queue: JobQueue | None = None,
    wakeups: Wakeups | None = None,
    resolver: Resolver = system_resolver,
    previews: PreviewControl | None = None,
    bridge: BridgeClient | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    database = Database(settings.database_url)
    job_queue = queue or ArqQueue(settings.redis_url)
    run_wakeups = wakeups or RedisWakeups(settings.redis_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await job_queue.close()
        await run_wakeups.close()
        await database.dispose()

    app = FastAPI(title="NFactory API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.database = database
    app.state.queue = job_queue
    app.state.wakeups = run_wakeups
    app.state.previews = previews or _previews(settings)
    app.state.bridge = bridge or HttpBridge(settings.nfactory_bridge_url)
    app.state.provider_deps = ProviderDeps(
        store=SecretStore(settings.nfactory_secret_key.get_secret_value()),
        resolver=resolver,
        allowed_private_hosts=frozenset(settings.nfactory_allowed_private_llm_hosts),
        ollama_base_url=settings.ollama_base_url,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Content-Type", "Last-Event-ID", "Idempotency-Key"],
    )
    install_error_handlers(app)

    api = APIRouter(prefix=API_PREFIX)
    routers = (health, dashboard, projects, recipes, runs, artifacts, settings_routes)
    for module in (*routers, providers, routing, knowledge, local_runtimes, agent_tasks):
        api.include_router(module.router)
    app.include_router(api)
    return app
