from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.bootstrap import prepare_data
from app.main import create_app
from app.queue import MemoryQueue
from app.wakeups import PollingWakeups
from nfactory_core.config import Settings

# Unreachable on purpose: readiness tests check that a dead Redis is reported.
UNREACHABLE_REDIS = "redis://127.0.0.1:1/0"


@dataclass
class Storage:
    workspaces: Path
    artifacts: Path


@pytest.fixture
def storage(tmp_path: Path) -> Storage:
    return Storage(workspaces=tmp_path / "workspaces", artifacts=tmp_path / "artifacts")


@pytest.fixture
def queue() -> MemoryQueue:
    return MemoryQueue()


# Fake DNS for provider tests: every host is public, except the obviously internal one.
def fake_resolver(host: str) -> list[str]:
    return ["10.0.0.8"] if host.endswith(".corp") else ["93.184.216.34"]


async def _client(
    database_url: str,
    storage: Storage,
    queue: MemoryQueue,
    *,
    demo: bool,
    resolver: object = None,
    **overrides: object,
) -> AsyncIterator[AsyncClient]:
    settings = Settings(
        database_url=database_url,
        redis_url=UNREACHABLE_REDIS,
        workspace_root=str(storage.workspaces),
        artifact_root=str(storage.artifacts),
        **overrides,  # type: ignore[arg-type]
    )
    extra = {"resolver": resolver} if resolver is not None else {}
    app = create_app(settings, queue=queue, wakeups=PollingWakeups(), **extra)  # type: ignore[arg-type]
    await prepare_data(app.state.database.sessions, demo=demo)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as http:
            yield http


@pytest.fixture
async def client(
    migrated_database_url: str, storage: Storage, queue: MemoryQueue
) -> AsyncIterator[AsyncClient]:
    """API client on a migrated database holding only the local identity."""
    async for http in _client(migrated_database_url, storage, queue, demo=False):
        yield http


@pytest.fixture
async def demo_client(
    migrated_database_url: str, storage: Storage, queue: MemoryQueue
) -> AsyncIterator[AsyncClient]:
    """API client on a database holding the demo dataset."""
    async for http in _client(migrated_database_url, storage, queue, demo=True):
        yield http


@pytest.fixture
async def no_model_client(
    migrated_database_url: str, storage: Storage, queue: MemoryQueue
) -> AsyncIterator[AsyncClient]:
    """Demo mode off and no provider connected yet (phase 2)."""
    async for http in _client(
        migrated_database_url, storage, queue, demo=False, nfactory_demo_mode=False
    ):
        yield http


@pytest.fixture
async def provider_client(
    migrated_database_url: str, storage: Storage, queue: MemoryQueue
) -> AsyncIterator[AsyncClient]:
    """Demo mode on, a known secret key and a fake DNS: for provider and routing tests."""
    async for http in _client(
        migrated_database_url,
        storage,
        queue,
        demo=False,
        resolver=fake_resolver,
        nfactory_secret_key="api-tests-master-key-0123456789abcdef",
    ):
        yield http


SSO_SETTINGS: dict[str, object] = {
    "nfactory_auth_mode": "oidc",
    "nfactory_oidc_client_id": "nfactory-test.apps.googleusercontent.com",
    "nfactory_oidc_client_secret": "s3cret-client",
    "nfactory_oidc_redirect_url": "http://127.0.0.1:3000/api/v1/auth/callback",
    "nfactory_oidc_allowed_domains": "example.fr",
    "nfactory_oidc_allowed_emails": "grace@gmail.com",
    "nfactory_oidc_owner_emails": "ada@example.fr",
    "nfactory_privacy_contact": "dpo@example.fr",
}


@pytest.fixture
async def sso_client(
    migrated_database_url: str, storage: Storage, queue: MemoryQueue
) -> AsyncIterator[AsyncClient]:
    """SSO mode (ADR-0013) against Google's issuer, which the tests simulate with respx."""
    async for http in _client(migrated_database_url, storage, queue, demo=False, **SSO_SETTINGS):
        yield http
