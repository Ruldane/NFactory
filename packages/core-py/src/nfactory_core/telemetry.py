"""OpenTelemetry setup shared by the API and the worker (spec §14.1, task 5.2).

Spans are exported over OTLP/HTTP only when a collector is configured
(`OTEL_EXPORTER_OTLP_ENDPOINT`, e.g. the optional `telemetry` Compose profile); otherwise
nothing is exported and the database event log stays the only trace. A run's spans use
the run's own `trace_id`, so a trace in Jaeger and the run in the dashboard match.

Interface: tracer_provider, run_context.
"""

import secrets

from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags


def tracer_provider(endpoint: str | None, service: str) -> TracerProvider | None:
    """A provider exporting to the collector at `endpoint`, or None without one."""
    if not endpoint:
        return None
    provider = TracerProvider(resource=Resource.create({"service.name": service}))
    exporter = OTLPSpanExporter(endpoint=f"{endpoint.rstrip('/')}/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    return provider


def run_context(trace_id: str) -> Context:
    """A parent context carrying the run's trace id (32 hex characters), so every span
    started under it belongs to the run's trace."""
    parent = SpanContext(
        trace_id=int(trace_id, 16),
        span_id=int.from_bytes(secrets.token_bytes(8), "big") or 1,
        is_remote=True,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )
    return trace.set_span_in_context(NonRecordingSpan(parent))
