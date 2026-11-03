"""Repository-wide pytest setup. Integration tests run against a real, throwaway
PostgreSQL database."""

import asyncio
import os
import sys
import uuid
from collections.abc import AsyncIterator, Iterator

import psycopg
import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.migrations_runner import upgrade_to_head

# Psycopg's async mode cannot run on Windows' default ProactorEventLoop.
# Containers run Linux, so this only matters for tests run directly on a Windows host.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

ADMIN_URL = os.environ.get(
    "NFACTORY_TEST_ADMIN_URL",
    "postgresql+psycopg://nfactory:nfactory_dev_only@127.0.0.1:55432/postgres",
)


def _libpq(url: str) -> str:
    return make_url(url).set(drivername="postgresql").render_as_string(hide_password=False)


def _admin_connect() -> psycopg.Connection:
    try:
        return psycopg.connect(_libpq(ADMIN_URL), autocommit=True, connect_timeout=3)
    except psycopg.OperationalError:
        pytest.skip("PostgreSQL not reachable: start it with scripts/check or docker compose")


@pytest.fixture
def empty_database_url() -> Iterator[str]:
    """A brand-new empty database, dropped after the test."""
    name = f"nfactory_test_{uuid.uuid4().hex[:8]}"
    with _admin_connect() as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    url = make_url(ADMIN_URL).set(database=name).render_as_string(hide_password=False)
    try:
        yield url
    finally:
        with _admin_connect() as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@pytest.fixture
def migrated_database_url(empty_database_url: str) -> str:
    upgrade_to_head(empty_database_url)
    return empty_database_url


@pytest.fixture
async def db_session(migrated_database_url: str) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(migrated_database_url)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()
