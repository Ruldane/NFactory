"""A run's trace from the database (task 5.2): `run` → stored steps → agent calls and
checks. A call's event is written when it ends; it started `duration_s` earlier.

Interface: run_trace.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.trace import RunTrace, SpanStatus, TraceSpan
from app.services.identity import RequestContext
from app.services.runs import owned_run
from nfactory_core.models import EventRecord, Run, RunStep

_CALLS = ("agent.progress", "tool.invoked")
_STEP_STATUS: dict[str, SpanStatus] = {
    "SUCCEEDED": "ok",
    "FAILED": "error",
    "RUNNING": "running",
    "SKIPPED": "skipped",
}

_RUN_STATUS: dict[str, SpanStatus] = {
    "COMPLETED": "ok",
    "FAILED": "error",
    "CANCELLED": "skipped",
    "DRAFT": "pending",
    "QUEUED": "pending",
}


async def run_trace(session: AsyncSession, ctx: RequestContext, run_id: str) -> RunTrace:
    run = await owned_run(session, ctx, run_id)
    steps = list(
        await session.scalars(
            select(RunStep).where(RunStep.run_id == run.id).order_by(RunStep.position)
        )
    )
    events = list(
        await session.scalars(
            select(EventRecord)
            .where(EventRecord.run_id == run.id, EventRecord.type.in_(_CALLS))
            .order_by(EventRecord.seq)
        )
    )
    calls: dict[str | None, list[TraceSpan]] = {}
    for event in events:
        calls.setdefault(event.step_id, []).append(_call_span(event))

    spans = [_run_span(run)]
    for step in steps:
        children = calls.get(step.id, [])
        spans.append(_step_span(step, run.id, children))
        spans.extend(children)
    return RunTrace(
        run_id=run.id, trace_id=run.trace_id, cost_usd=run.cost_estimate_usd, spans=spans
    )


def _run_span(run: Run) -> TraceSpan:
    status = _RUN_STATUS.get(run.state, "running")
    return TraceSpan(
        id=run.id,
        parent_id=None,
        kind="run",
        name="run",
        start=run.started_at,
        end=run.finished_at,
        duration_s=_seconds(run.started_at, run.finished_at),
        status=status,
        cost_usd=run.cost_estimate_usd,
    )


def _step_span(step: RunStep, run_id: str, children: list[TraceSpan]) -> TraceSpan:
    agents = [c for c in children if c.kind == "agent"]
    costs = [c.cost_usd for c in agents]
    return TraceSpan(
        id=step.id,
        parent_id=run_id,
        kind="step",
        name=step.name,
        agent_role=step.agent_role,
        start=step.started_at,
        end=step.ended_at,
        duration_s=_seconds(step.started_at, step.ended_at),
        status=_STEP_STATUS.get(step.state, "pending"),
        calls=len(agents),
        cost_usd=None if not costs or None in costs else sum(c or 0.0 for c in costs),
    )


def _call_span(event: EventRecord) -> TraceSpan:
    payload = event.payload_redacted or {}
    end = _aware(event.created_at)
    duration = _number(payload.get("duration_s"))
    start = end - timedelta(seconds=duration) if duration is not None else None
    if event.type == "tool.invoked":
        exit_code = _number(payload.get("exit_code"))
        failed = exit_code != 0 or bool(payload.get("timed_out"))
        return TraceSpan(
            id=event.id,
            parent_id=event.step_id,
            kind="check",
            name=str(payload.get("check", "?"))[:80],
            start=start,
            end=end,
            duration_s=duration,
            status="error" if failed else "ok",
            exit_code=int(exit_code) if exit_code is not None else None,
        )
    tokens_in, tokens_out = (
        _number(payload.get("input_tokens")),
        _number(payload.get("output_tokens")),
    )
    return TraceSpan(
        id=event.id,
        parent_id=event.step_id,
        kind="agent",
        name=str(payload.get("agent", "?"))[:80],
        start=start,
        end=end,
        duration_s=duration,
        status="ok",
        provider=_text(payload.get("provider")),
        model=_text(payload.get("model")),
        input_tokens=int(tokens_in) if tokens_in is not None else None,
        output_tokens=int(tokens_out) if tokens_out is not None else None,
        cost_usd=_number(payload.get("cost_usd")),
    )


def _number(value: Any) -> float | None:
    """A measured number, or None (an old event may hold "***REDACTED***")."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _text(value: Any) -> str | None:
    return str(value)[:120] if isinstance(value, str) and value else None


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _seconds(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return (_aware(end) - _aware(start)).total_seconds()
