"""Server-Sent Events for one run, read from the `events` table.

Between reads the stream waits on a `Wakeup`: the worker's Redis signal, or a plain
poll interval when Redis is unavailable.

`seq` is the SSE id, so a client that reconnects with Last-Event-ID gets exactly the
events it missed. The stream ends once the run is finished and its log is drained.
"""

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.wakeups import Wakeup, Wakeups
from nfactory_core.models import EventRecord, Run
from nfactory_core.states import TERMINAL_STATES, RunState

BATCH = 200
# A finished run whose final event never came (worker killed): stop after this many
# empty reads rather than streaming forever.
QUIET_POLLS_AFTER_END = 3
_FINAL_EVENTS = {"run.completed", "run.failed", "run.cancelled"}


def parse_last_event_id(value: str | None) -> int:
    try:
        return max(int(value or 0), 0)
    except ValueError:
        return 0


async def stream_run(
    sessions: async_sessionmaker[AsyncSession],
    wakeups: Wakeups,
    run_id: str,
    after: int,
    disconnected: Callable[[], Awaitable[bool]],
) -> AsyncIterator[dict[str, Any]]:
    """`run_events`, subscribed to the run's wake-ups for the life of the stream."""
    async with wakeups.subscribe(run_id) as wakeup:
        async for message in run_events(sessions, run_id, after, disconnected, wakeup):
            yield message


async def run_events(
    sessions: async_sessionmaker[AsyncSession],
    run_id: str,
    after: int,
    disconnected: Callable[[], Awaitable[bool]],
    wakeup: Wakeup,
) -> AsyncIterator[dict[str, Any]]:
    last = after
    quiet = 0
    while not await disconnected():
        async with sessions() as session:
            rows = list(
                await session.scalars(
                    select(EventRecord)
                    .where(EventRecord.run_id == run_id, EventRecord.seq > last)
                    .order_by(EventRecord.seq)
                    .limit(BATCH)
                )
            )
            state = await session.scalar(select(Run.state).where(Run.id == run_id))
        for row in rows:
            last = row.seq
            yield _message(row)
        if any(row.type in _FINAL_EVENTS for row in rows) and len(rows) < BATCH:
            return
        if rows:
            quiet = 0
            continue
        if state is None or RunState(state) in TERMINAL_STATES:
            quiet += 1
            if quiet >= QUIET_POLLS_AFTER_END:
                return
        await wakeup.wait()


def _message(row: EventRecord) -> dict[str, Any]:
    data = {
        "seq": row.seq,
        "type": row.type,
        "step_id": row.step_id,
        "created_at": row.created_at.isoformat(),
        "payload": row.payload_redacted,
    }
    return {"id": str(row.seq), "event": row.type, "data": json.dumps(data, ensure_ascii=False)}
