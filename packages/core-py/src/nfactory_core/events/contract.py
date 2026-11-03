"""Versioned event contract (spec §10.3). Payloads are redacted on creation."""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from nfactory_core.events.redaction import redact
from nfactory_core.ids import new_id

SCHEMA_VERSION = "1"

EventType = Literal[
    "run.created",
    "run.started",
    "run.state_changed",
    "run.completed",
    "run.failed",
    "run.cancelled",
    "step.started",
    "step.completed",
    "step.failed",
    "step.skipped",
    "agent.started",
    "agent.progress",
    "tool.invoked",
    "provider.failed",
    "knowledge.retrieved",
    "approval.requested",
    "approval.resolved",
    "artifact.created",
    "test.passed",
    "test.failed",
    "repair.started",
    "repair.applied",
    "repair.abandoned",
    "security.scanned",
    "changes.computed",
]


class Event(BaseModel):
    schema_version: str = SCHEMA_VERSION
    event_id: str = Field(default_factory=lambda: new_id("evt"))
    run_id: str
    step_id: str | None = None
    type: EventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("payload")
    @classmethod
    def _redact_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        redacted: dict[str, Any] = redact(value)
        return redacted
