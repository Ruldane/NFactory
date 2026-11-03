"""Server-sent events parsing, including the provider quirks from the docs."""

from collections.abc import AsyncIterator, Iterable

from nfactory_core.providers.sse import SseEvent, iter_sse


async def _lines(lines: Iterable[str]) -> AsyncIterator[str]:
    for line in lines:
        yield line


async def _parse(lines: Iterable[str]) -> list[SseEvent]:
    return [event async for event in iter_sse(_lines(lines))]


async def test_data_lines_end_at_a_blank_line() -> None:
    events = await _parse(['data: {"a":1}', "", 'data: {"a":2}', "", "data: [DONE]", ""])
    assert [e.data for e in events] == ['{"a":1}', '{"a":2}', "[DONE]"]
    assert all(e.event == "message" for e in events)


async def test_comments_and_keep_alive_blank_lines_are_skipped() -> None:
    # DeepSeek sends ": keep-alive" comments and bare blank lines while queued.
    events = await _parse([": keep-alive", "", "", ": keep-alive", 'data: {"x":1}', ""])
    assert [e.data for e in events] == ['{"x":1}']


async def test_named_events_are_kept() -> None:
    # Anthropic names every event and sends no [DONE].
    events = await _parse(
        [
            "event: message_start",
            'data: {"type":"message_start"}',
            "",
            "event: ping",
            "data: {}",
            "",
        ]
    )
    assert [(e.event, e.data) for e in events] == [
        ("message_start", '{"type":"message_start"}'),
        ("ping", "{}"),
    ]


async def test_multi_line_data_is_joined_and_a_last_event_without_blank_line_counts() -> None:
    events = await _parse(["data: first", "data: second"])
    assert [e.data for e in events] == ["first\nsecond"]
