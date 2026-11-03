"""Persist events to the `events` table. The payload is redacted by `Event` itself."""

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nfactory_core.events.contract import Event
from nfactory_core.models import EventRecord

Notifier = Callable[[str], Awaitable[None]]  # called with the run id after each event


def run_channel(run_id: str) -> str:
    """Redis channel the worker signals after storing an event of this run."""
    return f"nfactory:run:{run_id}"


async def record_event(
    sessions: async_sessionmaker[AsyncSession],
    run_id: str,
    type: str,
    payload: dict[str, Any],
    step_id: str | None = None,
    notify: Notifier | None = None,
) -> None:
    event = Event(run_id=run_id, step_id=step_id, type=type, payload=payload)
    async with sessions() as session:
        session.add(
            EventRecord(
                id=event.event_id,
                run_id=run_id,
                step_id=step_id,
                type=event.type,
                schema_version=event.schema_version,
                payload_redacted=event.payload,
                created_at=event.timestamp,
            )
        )
        await session.commit()
    if notify is not None:
        await notify(run_id)
