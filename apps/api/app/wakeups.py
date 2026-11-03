"""Wake-ups for run event streams.

The worker publishes on `run_channel(run_id)` after each stored event. A stream waits
for that signal instead of polling the database; the `events` table stays the source
of truth, so a lost signal only delays an event until the safety re-poll.
"""

import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Protocol

from redis.asyncio import Redis
from redis.asyncio.client import PubSub
from redis.exceptions import RedisError

from nfactory_core.events import run_channel

logger = logging.getLogger(__name__)

POLL_SECONDS = 0.5  # without Redis
SAFETY_SECONDS = 2.0  # with Redis: re-poll even without a signal


class Wakeup(Protocol):
    async def wait(self) -> None:
        """Return when the run may have new events (a signal, or the interval elapsed)."""


class Wakeups(Protocol):
    def subscribe(self, run_id: str) -> AbstractAsyncContextManager[Wakeup]: ...

    async def close(self) -> None: ...


class _Sleep:
    def __init__(self, seconds: float) -> None:
        self.seconds = seconds

    async def wait(self) -> None:
        await asyncio.sleep(self.seconds)


class PollingWakeups:
    """No signal at all: streams poll the database at a fixed interval."""

    def __init__(self, poll_seconds: float = POLL_SECONDS) -> None:
        self.poll_seconds = poll_seconds

    @asynccontextmanager
    async def subscribe(self, run_id: str) -> AsyncIterator[Wakeup]:
        yield _Sleep(self.poll_seconds)

    async def close(self) -> None:
        return None


class _RedisWakeup:
    def __init__(self, pubsub: PubSub, timeout: float, poll_seconds: float) -> None:
        self.pubsub: PubSub | None = pubsub
        self.timeout = timeout
        self.poll_seconds = poll_seconds

    async def wait(self) -> None:
        if self.pubsub is None:
            await asyncio.sleep(self.poll_seconds)
            return
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.timeout
        try:
            # None means a timeout *or* an ignored subscribe confirmation: keep waiting
            # until a real signal or the deadline.
            while (remaining := deadline - loop.time()) > 0:
                message = await self.pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=remaining
                )
                if message is not None:
                    break
            # Drain signals that piled up: one database read covers them all.
            while await self.pubsub.get_message(ignore_subscribe_messages=True) is not None:
                pass
        except (RedisError, OSError) as exc:
            logger.warning("Redis lost while streaming events, polling instead: %s", exc)
            self.pubsub = None


class RedisWakeups:
    """Subscribes each stream to its run's channel; degrades to polling if Redis fails."""

    def __init__(
        self,
        url: str,
        timeout: float = SAFETY_SECONDS,
        poll_seconds: float = POLL_SECONDS,
    ) -> None:
        self.redis = Redis.from_url(url, socket_connect_timeout=2, socket_timeout=None)
        self.timeout = timeout
        self.poll_seconds = poll_seconds

    @asynccontextmanager
    async def subscribe(self, run_id: str) -> AsyncIterator[Wakeup]:
        pubsub = self.redis.pubsub()
        try:
            # Subscribed before the stream's first read: no signal can fall in between.
            await pubsub.subscribe(run_channel(run_id))
        except (RedisError, OSError) as exc:
            logger.warning("Redis unavailable, event stream polls the database: %s", exc)
            await pubsub.aclose()
            yield _Sleep(self.poll_seconds)
            return
        try:
            yield _RedisWakeup(pubsub, self.timeout, self.poll_seconds)
        finally:
            await pubsub.aclose()

    async def close(self) -> None:
        await self.redis.aclose()


class MemoryWakeups:
    """In-process signals, for tests: `notify` plays the worker's publish."""

    def __init__(self, timeout: float = SAFETY_SECONDS) -> None:
        self.timeout = timeout
        self._events: dict[str, list[asyncio.Event]] = defaultdict(list)

    def signal(self, run_id: str) -> None:
        for event in self._events[run_id]:
            event.set()

    async def notify(self, run_id: str) -> None:
        self.signal(run_id)

    @asynccontextmanager
    async def subscribe(self, run_id: str) -> AsyncIterator[Wakeup]:
        event = asyncio.Event()
        self._events[run_id].append(event)
        try:
            yield _MemoryWakeup(event, self.timeout)
        finally:
            self._events[run_id].remove(event)

    async def close(self) -> None:
        return None


class _MemoryWakeup:
    def __init__(self, event: asyncio.Event, timeout: float) -> None:
        self.event = event
        self.timeout = timeout

    async def wait(self) -> None:
        try:
            await asyncio.wait_for(self.event.wait(), self.timeout)
        except TimeoutError:
            pass
        self.event.clear()
