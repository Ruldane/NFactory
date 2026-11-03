"""A worker killed mid-run must not leave its run locked until ARQ's long timeout.

While a run is processed, the worker keeps a short-lived lease. A RUNNING run with no
live lease is orphaned: recovery drops ARQ's in-progress lock so the job is picked up
again at once and resumes from its last checkpoint.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.services.identity import LOCAL_WORKSPACE_ID, ensure_local_identity
from nfactory_core.config import Settings
from nfactory_core.models import Project, Run
from nfactory_worker.jobs.recovery import (
    ARQ_IN_PROGRESS,
    lease_key,
    recover_orphaned_runs,
    run_lease,
)

pytestmark = pytest.mark.integration

Sessions = async_sessionmaker[AsyncSession]


@pytest.fixture
async def sessions(migrated_database_url: str) -> AsyncIterator[Sessions]:
    engine = create_async_engine(migrated_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await ensure_local_identity(session)
        await session.commit()
    yield factory
    await engine.dispose()


@pytest.fixture
async def redis() -> AsyncIterator[Redis]:
    client = Redis.from_url(Settings().redis_url)
    yield client
    await client.aclose()


async def new_run(sessions: Sessions, state: str) -> str:
    async with sessions() as session:
        project = Project(workspace_id=LOCAL_WORKSPACE_ID, title="Projet", type="api")
        session.add(project)
        await session.flush()
        run = Run(
            id=f"run_{uuid.uuid4().hex[:20]}", project_id=project.id, request="API", state=state
        )
        session.add(run)
        await session.commit()
        return run.id


async def test_orphaned_running_run_is_released_at_once(sessions: Sessions, redis: Redis) -> None:
    run_id = await new_run(sessions, "RUNNING")
    await redis.set(ARQ_IN_PROGRESS + run_id, b"1", px=1_800_000)  # the killed worker's lock

    released = await recover_orphaned_runs(sessions, redis)

    assert run_id in released
    assert not await redis.exists(ARQ_IN_PROGRESS + run_id)


async def test_run_with_a_live_lease_is_left_alone(sessions: Sessions, redis: Redis) -> None:
    run_id = await new_run(sessions, "RUNNING")
    await redis.set(ARQ_IN_PROGRESS + run_id, b"1", px=1_800_000)

    async with run_lease(redis, run_id, ttl_s=5):
        released = await recover_orphaned_runs(sessions, redis)

    assert run_id not in released
    assert await redis.exists(ARQ_IN_PROGRESS + run_id)
    await redis.delete(ARQ_IN_PROGRESS + run_id)


async def test_finished_runs_are_not_touched(sessions: Sessions, redis: Redis) -> None:
    run_id = await new_run(sessions, "COMPLETED")

    assert run_id not in await recover_orphaned_runs(sessions, redis)


async def test_lease_is_renewed_while_held_and_dropped_after(redis: Redis) -> None:
    run_id = f"run_{uuid.uuid4().hex[:20]}"

    async with run_lease(redis, run_id, ttl_s=1):
        await asyncio.sleep(1.5)  # longer than the TTL: only renewal keeps it alive
        assert await redis.exists(lease_key(run_id))

    assert not await redis.exists(lease_key(run_id))
