"""OpenTelemetry spans of a run (task 5.2): run → steps → agent calls and checks, all under
the run's own trace id, with no payload content."""

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from nfactory_core.telemetry import tracer_provider
from nfactory_worker.pipeline.memory import MemoryReporter
from nfactory_worker.telemetry import TracingReporter

TRACE = "0123456789abcdef0123456789abcdef"


@pytest.fixture
def exporter() -> InMemorySpanExporter:
    return InMemorySpanExporter()


@pytest.fixture
def inner() -> MemoryReporter:
    return MemoryReporter()


@pytest.fixture
def reporter(exporter: InMemorySpanExporter, inner: MemoryReporter) -> TracingReporter:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return TracingReporter(inner, provider.get_tracer("test"), run_id="run_1", trace_id=TRACE)


async def a_failed_run(reporter: TracingReporter) -> None:
    with reporter.run_span() as run:
        await reporter.step_started("plan")
        await reporter.emit(
            "agent.progress",
            {
                "agent": "planner",
                "provider": "anthropic",
                "model": "m1",
                "input_tokens": 120,
                "output_tokens": 30,
                "duration_s": 1.5,
                "cost_usd": 0.01,
                "prompt": "secret brief text",
            },
            "plan",
        )
        await reporter.step_succeeded("plan", {"plan": "x"})
        await reporter.step_started("checks")
        await reporter.emit(
            "tool.invoked",
            {
                "check": "pytest",
                "argv": ["python", "-m", "pytest"],
                "exit_code": 1,
                "duration_s": 0.2,
            },
            "checks",
        )
        await reporter.step_failed("checks", "1 test en échec")
        await reporter.step_skipped("docs", "run en échec")
        run.outcome("FAILED")


def by_name(exporter: InMemorySpanExporter):  # type: ignore[no-untyped-def]
    return {span.name: span for span in exporter.get_finished_spans()}


async def test_every_span_of_a_run_shares_the_runs_trace_id(
    reporter: TracingReporter, exporter: InMemorySpanExporter
) -> None:
    await a_failed_run(reporter)

    spans = by_name(exporter)
    assert set(spans) == {
        "run",
        "step plan",
        "agent planner",
        "step checks",
        "check pytest",
        "step docs",
    }
    assert {format(s.context.trace_id, "032x") for s in spans.values()} == {TRACE}


async def test_spans_nest_run_then_step_then_call(
    reporter: TracingReporter, exporter: InMemorySpanExporter
) -> None:
    await a_failed_run(reporter)

    spans = by_name(exporter)
    run, plan = spans["run"], spans["step plan"]
    assert plan.parent.span_id == run.context.span_id
    assert spans["agent planner"].parent.span_id == plan.context.span_id
    assert spans["check pytest"].parent.span_id == spans["step checks"].context.span_id


async def test_an_agent_call_carries_its_model_tokens_cost_and_duration(
    reporter: TracingReporter, exporter: InMemorySpanExporter
) -> None:
    await a_failed_run(reporter)

    call = by_name(exporter)["agent planner"]
    assert call.attributes["gen_ai.provider.name"] == "anthropic"
    assert call.attributes["gen_ai.request.model"] == "m1"
    assert call.attributes["gen_ai.usage.input_tokens"] == 120
    assert call.attributes["nfactory.cost_usd"] == pytest.approx(0.01)
    assert (call.end_time - call.start_time) / 1e9 == pytest.approx(1.5, abs=0.05)
    # Only measured fields leave the worker, never a prompt or an output.
    assert "secret brief text" not in str(dict(call.attributes))


async def test_failures_are_marked_as_errors(
    reporter: TracingReporter, exporter: InMemorySpanExporter
) -> None:
    await a_failed_run(reporter)

    spans = by_name(exporter)
    assert spans["check pytest"].status.status_code is StatusCode.ERROR
    assert spans["step checks"].status.status_code is StatusCode.ERROR
    assert spans["step plan"].status.status_code is StatusCode.UNSET
    assert spans["step docs"].attributes["nfactory.step.state"] == "SKIPPED"
    assert spans["run"].attributes["nfactory.outcome"] == "FAILED"
    assert spans["run"].attributes["nfactory.run_id"] == "run_1"


async def test_the_wrapped_reporter_still_gets_every_call(
    reporter: TracingReporter, inner: MemoryReporter
) -> None:
    await a_failed_run(reporter)

    assert inner.started == ["plan", "checks"]
    assert inner.succeeded == ["plan"]
    assert inner.failed == {"checks": "1 test en échec"}
    assert inner.skipped == {"docs": "run en échec"}
    assert [kind for kind, _, _ in inner.events] == ["agent.progress", "tool.invoked"]


def test_spans_are_exported_only_when_a_collector_is_configured() -> None:
    assert tracer_provider(None, "nfactory-worker") is None
    assert tracer_provider("http://127.0.0.1:4318", "nfactory-worker") is not None
