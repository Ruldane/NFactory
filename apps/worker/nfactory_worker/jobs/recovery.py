"""Recovery of runs whose worker died.

ARQ locks a job while it runs (`arq:in-progress:<job id>`) for the whole job timeout,
so after a hard kill the run would wait ~30 minutes before another try. Instead, a
worker holds a short lease while it processes a run; a RUNNING run with no live lease
is orphaned, and dropping ARQ's lock lets a worker pick the job up again at once. The
job then resumes from its last LangGraph checkpoint.
"""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from arq.constants import in_progress_key_prefix
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nfactory_core.models import Run
from nfactory_core.states import RunState

log = logging.getLogger("nfactory.worker")

ARQ_IN_PROGRESS = in_progress_key_prefix  # ARQ job id == run id (see app.queue)
LEASE_TTL_S = 30


def lease_key(run_id: str) -> str:
    return f"nfactory:run-lease:{run_id}"


@contextlib.asynccontextmanager
async def run_lease(redis: Redis, run_id: str, ttl_s: int = LEASE_TTL_S) -> AsyncIterator[None]:
    """Hold the run's lease, renewed every third of its TTL, for the block's duration."""
    key = lease_key(run_id)
    await redis.set(key, b"1", ex=ttl_s)

    async def renew() -> None:
        while True:
            await asyncio.sleep(ttl_s / 3)
            await redis.set(key, b"1", ex=ttl_s)

    renewal = asyncio.create_task(renew())
    try:
        yield
    finally:
        renewal.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await renewal
        await redis.delete(key)


async def recover_orphaned_runs(
    sessions: async_sessionmaker[AsyncSession], redis: Redis
) -> list[str]:
    """Release the ARQ lock of every RUNNING run that no live worker holds."""
    async with sessions() as session:
        running = list(await session.scalars(select(Run.id).where(Run.state == RunState.RUNNING)))
    released = []
    for run_id in running:
        if await redis.exists(lease_key(run_id)):
            continue
        if await redis.delete(ARQ_IN_PROGRESS + run_id):
            log.warning("Run %s was orphaned by a dead worker: released for another try.", run_id)
        released.append(run_id)
    return released
