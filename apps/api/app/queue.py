"""Job queue seam: the API enqueues runs and indexing, the worker consumes them.

Interface: JobQueue (protocol), ArqQueue (Redis, production), MemoryQueue (tests),
QueueUnavailableError.
"""

from typing import Protocol

from arq import ArqRedis, create_pool
from arq.connections import RedisSettings

from nfactory_core.pipeline import INDEX_JOB, RUN_JOB, RUN_QUEUE


class QueueUnavailableError(RuntimeError):
    pass


class JobQueue(Protocol):
    async def enqueue(self, run_id: str) -> None: ...

    async def enqueue_indexing(self, workspace_id: str) -> None: ...

    async def close(self) -> None: ...


class ArqQueue:
    def __init__(self, redis_url: str) -> None:
        self._settings = RedisSettings.from_dsn(redis_url)
        self._settings.conn_timeout = 2
        self._settings.conn_retries = 1
        self._pool: ArqRedis | None = None

    async def enqueue(self, run_id: str) -> None:
        # _job_id = run id: enqueuing the same run twice is a no-op.
        await self._send(RUN_JOB, run_id, run_id)

    async def enqueue_indexing(self, workspace_id: str) -> None:
        # One pending indexing job per workspace; it embeds every pending chunk.
        await self._send(INDEX_JOB, workspace_id, f"index:{workspace_id}")

    async def _send(self, job: str, arg: str, job_id: str) -> None:
        try:
            if self._pool is None:
                self._pool = await create_pool(self._settings, default_queue_name=RUN_QUEUE)
            await self._pool.enqueue_job(job, arg, _job_id=job_id)
        except (OSError, ConnectionError) as exc:
            raise QueueUnavailableError(type(exc).__name__) from exc
        except Exception as exc:  # redis raises its own error hierarchy
            if type(exc).__module__.startswith("redis"):
                raise QueueUnavailableError(type(exc).__name__) from exc
            raise

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.aclose()
            self._pool = None


class MemoryQueue:
    def __init__(self) -> None:
        self.enqueued: list[str] = []
        self.indexing: list[str] = []
        self.broken = False

    async def enqueue(self, run_id: str) -> None:
        if self.broken:
            raise QueueUnavailableError("broken on purpose")
        self.enqueued.append(run_id)

    async def enqueue_indexing(self, workspace_id: str) -> None:
        if self.broken:
            raise QueueUnavailableError("broken on purpose")
        self.indexing.append(workspace_id)

    async def close(self) -> None:
        return None
