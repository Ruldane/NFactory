"""The SSE generator sends a new event as soon as the run is signalled, not at the next poll."""

import asyncio
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.services.identity import LOCAL_WORKSPACE_ID, ensure_local_identity
from app.services.run_events import run_events
from app.wakeups import MemoryWakeups
from nfactory_core.events import record_event
from nfactory_core.models import Project, Run

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


async def _running_run(sessions: Sessions) -> str:
    async with sessions() as session:
        project = Project(workspace_id=LOCAL_WORKSPACE_ID, title="Projet", type="api")
        session.add(project)
        await session.flush()
        run = Run(project_id=project.id, request="API", state="RUNNING")
        session.add(run)
        await session.commit()
        return run.id


async def _never() -> bool:
    return False


async def test_signalled_event_is_sent_without_waiting_for_the_poll(sessions: Sessions) -> None:
    run_id = await _running_run(sessions)
    wakeups = MemoryWakeups(timeout=30.0)  # a missed signal would block for 30 s
    await record_event(sessions, run_id, "run.started", {"state": "RUNNING"})

    async with wakeups.subscribe(run_id) as wakeup:
        stream = run_events(sessions, run_id, 0, _never, wakeup)
        first = await asyncio.wait_for(anext(stream), 2.0)
        assert first["event"] == "run.started"

        next_event = asyncio.create_task(anext(stream))
        await asyncio.sleep(0.1)  # the stream is now waiting for a wake-up
        await record_event(sessions, run_id, "step.started", {}, None, wakeups.notify)

        second = await asyncio.wait_for(next_event, 2.0)
        assert second["event"] == "step.started"
        await stream.aclose()
