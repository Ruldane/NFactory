"""SSE wake-ups: the worker's Redis signal wakes the stream; a dead Redis degrades to polling."""

import asyncio
import time

import pytest
from redis.asyncio import Redis

from app.wakeups import MemoryWakeups, RedisWakeups
from nfactory_core.config import Settings
from nfactory_core.events import run_channel

DEAD_REDIS = "redis://127.0.0.1:1/0"


async def _timed_wait(wakeups: object, run_id: str, signal: object) -> float:
    async with wakeups.subscribe(run_id) as wakeup:  # type: ignore[attr-defined]
        started = time.perf_counter()
        task = asyncio.create_task(signal())  # type: ignore[operator]
        await wakeup.wait()
        await task
        return time.perf_counter() - started


@pytest.mark.integration
async def test_redis_signal_wakes_the_stream_at_once() -> None:
    url = Settings().redis_url
    wakeups = RedisWakeups(url, timeout=10.0)
    publisher = Redis.from_url(url)

    async def signal() -> None:
        await asyncio.sleep(0.1)
        await publisher.publish(run_channel("run_wake"), "1")

    try:
        elapsed = await _timed_wait(wakeups, "run_wake", signal)
    finally:
        await publisher.aclose()
        await wakeups.close()

    assert elapsed < 2.0  # far below the 10 s safety re-poll


@pytest.mark.integration
async def test_signal_for_another_run_does_not_wake_the_stream() -> None:
    url = Settings().redis_url
    wakeups = RedisWakeups(url, timeout=0.5)
    publisher = Redis.from_url(url)

    async def signal() -> None:
        await publisher.publish(run_channel("run_other"), "1")

    try:
        elapsed = await _timed_wait(wakeups, "run_mine", signal)
    finally:
        await publisher.aclose()
        await wakeups.close()

    assert elapsed >= 0.4  # waited for its own safety re-poll


async def test_dead_redis_falls_back_to_polling() -> None:
    wakeups = RedisWakeups(DEAD_REDIS, timeout=10.0, poll_seconds=0.05)

    async def nothing() -> None:
        return None

    elapsed = await _timed_wait(wakeups, "run_x", nothing)
    await wakeups.close()

    assert elapsed < 5.0  # polled instead of raising or hanging


async def test_memory_wakeups_signal_only_the_named_run() -> None:
    wakeups = MemoryWakeups(timeout=5.0)

    async def signal() -> None:
        await asyncio.sleep(0.05)
        wakeups.signal("run_a")

    assert await _timed_wait(wakeups, "run_a", signal) < 1.0
