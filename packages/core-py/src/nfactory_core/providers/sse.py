"""Minimal server-sent events parser (WHATWG framing) for provider streams."""

from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(frozen=True)
class SseEvent:
    event: str
    data: str


async def iter_sse(lines: AsyncIterator[str]) -> AsyncIterator[SseEvent]:
    """Yield one event per blank-line-terminated block. Comments (": ...") and blocks
    without data (keep-alives) are skipped."""
    name = "message"
    data: list[str] = []
    async for raw in lines:
        line = raw.rstrip("\r")
        if not line:
            if data:
                yield SseEvent(name, "\n".join(data))
            name, data = "message", []
            continue
        if line.startswith(":"):
            continue
        field, _, value = line.partition(":")
        value = value.removeprefix(" ")
        if field == "data":
            data.append(value)
        elif field == "event":
            name = value
    if data:
        yield SseEvent(name, "\n".join(data))
