"""OpenTelemetry spans of a run (task 5.2), from the events the pipeline already reports.

`TracingReporter` wraps any `Reporter`: it passes every call through, and turns them into
spans under the run's trace id: `run` → `step <name>` → `agent <role>` / `check <name>`.
A span carries measured fields only (provider, model, tokens, cost, duration, exit code),
never a prompt, an output or a command's text.

Interface: TracingReporter (run_span, plus the Reporter methods).
"""

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.trace import Span, Status, StatusCode, Tracer

from nfactory_core.telemetry import run_context
from nfactory_worker.artifacts import StoredArtifact
from nfactory_worker.pipeline.ports import Reporter

_NS = 1_000_000_000
Attrs = Callable[[dict[str, Any]], tuple[dict[str, Any], bool]]


class RunSpan:
    def __init__(self, span: Span) -> None:
        self._span = span

    def outcome(self, value: str) -> None:
        self._span.set_attribute("nfactory.outcome", value)
        if value == "FAILED":
            self._span.set_status(Status(StatusCode.ERROR))


class TracingReporter:
    def __init__(self, inner: Reporter, tracer: Tracer, *, run_id: str, trace_id: str) -> None:
        self._inner = inner
        self._tracer = tracer
        self._run_id = run_id
        self._trace_id = trace_id
        self._run: Span | None = None
        self._steps: dict[str, Span] = {}

    @contextmanager
    def run_span(self) -> Iterator[RunSpan]:
        span = self._tracer.start_span(
            "run",
            context=run_context(self._trace_id),
            attributes={"nfactory.run_id": self._run_id},
        )
        self._run = span
        try:
            yield RunSpan(span)
        finally:
            for open_step in self._steps.values():  # a step left open by an error
                open_step.end()
            self._steps.clear()
            span.end()
            self._run = None

    async def step_started(self, step: str) -> None:
        await self._inner.step_started(step)
        self._steps[step] = self._tracer.start_span(
            f"step {step}", context=self._parent(None), attributes=self._step_attrs(step)
        )

    async def step_succeeded(self, step: str, output: dict[str, Any]) -> None:
        await self._inner.step_succeeded(step, output)
        self._end_step(step, "SUCCEEDED")

    async def step_failed(
        self, step: str, error: str, output: dict[str, Any] | None = None
    ) -> None:
        await self._inner.step_failed(step, error, output)
        self._end_step(step, "FAILED", error=True)

    async def step_skipped(self, step: str, reason: str) -> None:
        await self._inner.step_skipped(step, reason)
        span = self._steps.pop(step, None) or self._tracer.start_span(
            f"step {step}", context=self._parent(None), attributes=self._step_attrs(step)
        )
        span.set_attribute("nfactory.step.state", "SKIPPED")
        span.end()

    async def emit(self, type: str, payload: dict[str, Any], step: str | None = None) -> None:
        await self._inner.emit(type, payload, step)
        if type == "agent.progress":
            self._finished_span(f"agent {payload.get('agent', '?')}", step, payload, _call_attrs)
        elif type == "tool.invoked":
            self._finished_span(f"check {payload.get('check', '?')}", step, payload, _check_attrs)
        elif type == "provider.failed" and step in self._steps:
            self._steps[step].add_event(
                "provider.failed",
                {"gen_ai.provider.name": str(payload.get("provider", "")),
                 "error.type": str(payload.get("kind", ""))},
            )  # fmt: skip

    async def artifact_saved(self, artifact: StoredArtifact) -> None:
        await self._inner.artifact_saved(artifact)

    def _parent(self, step: str | None) -> Context:
        span = self._steps.get(step) if step else None
        span = span or self._run
        return trace.set_span_in_context(span) if span else run_context(self._trace_id)

    def _step_attrs(self, step: str) -> dict[str, str]:
        return {"nfactory.run_id": self._run_id, "nfactory.step": step}

    def _end_step(self, step: str, state: str, *, error: bool = False) -> None:
        span = self._steps.pop(step, None)
        if span is None:  # resumed after a restart: its start was in another process
            return
        span.set_attribute("nfactory.step.state", state)
        if error:
            span.set_status(Status(StatusCode.ERROR))
        span.end()

    def _finished_span(
        self, name: str, step: str | None, payload: dict[str, Any], attrs: Attrs
    ) -> None:
        """A call that already happened: the span ends now and lasted `duration_s`."""
        end = time.time_ns()
        duration = payload.get("duration_s")
        seconds = float(duration) if isinstance(duration, int | float) else 0.0
        attributes, failed = attrs(payload)
        span = self._tracer.start_span(
            name,
            context=self._parent(step),
            start_time=end - int(seconds * _NS),
            attributes={"nfactory.run_id": self._run_id, **attributes},
        )
        if failed:
            span.set_status(Status(StatusCode.ERROR))
        span.end(end_time=end)


def _numbers(payload: dict[str, Any], keys: dict[str, str]) -> dict[str, float | int]:
    return {
        attr: payload[key]
        for key, attr in keys.items()
        if isinstance(payload.get(key), int | float) and not isinstance(payload.get(key), bool)
    }


def _call_attrs(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    attrs: dict[str, Any] = {
        "gen_ai.agent.name": str(payload.get("agent", "")),
        "gen_ai.provider.name": str(payload.get("provider", "")),
        "gen_ai.request.model": str(payload.get("model", "")),
    }
    attrs |= _numbers(
        payload,
        {
            "input_tokens": "gen_ai.usage.input_tokens",
            "output_tokens": "gen_ai.usage.output_tokens",
            "cost_usd": "nfactory.cost_usd",
        },
    )
    return attrs, False


def _check_attrs(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    attrs: dict[str, Any] = {"nfactory.check": str(payload.get("check", ""))}
    attrs |= _numbers(payload, {"exit_code": "process.exit.code"})
    failed = payload.get("exit_code") != 0 or bool(payload.get("timed_out"))
    return attrs, failed
