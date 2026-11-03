"""The trace of a run (task 5.2): the same tree the worker exports to OpenTelemetry,
rebuilt from the database so the dashboard needs no collector."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

SpanKind = Literal["run", "step", "agent", "check"]
SpanStatus = Literal["ok", "error", "running", "pending", "skipped"]


class TraceSpan(BaseModel):
    id: str
    parent_id: str | None
    kind: SpanKind
    name: str
    start: datetime | None
    end: datetime | None
    duration_s: float | None
    status: SpanStatus
    agent_role: str | None = None
    provider: str | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None  # None: unknown, never a fake 0
    calls: int | None = None  # a step: its model calls
    exit_code: int | None = None  # a check


class RunTrace(BaseModel):
    run_id: str
    trace_id: str | None
    cost_usd: float | None
    spans: list[TraceSpan]  # run, then each step in order, each followed by its calls
