import pytest
from pydantic import ValidationError

from nfactory_core.events import SCHEMA_VERSION, Event


def test_event_has_versioned_schema_and_generated_ids() -> None:
    event = Event(run_id="run_1", type="step.completed", payload={"agent": "builder"})
    assert event.schema_version == SCHEMA_VERSION == "1"
    assert event.event_id.startswith("evt_")
    assert event.timestamp.tzinfo is not None


def test_unknown_event_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Event(run_id="run_1", type="step.teleported")  # type: ignore[arg-type]


def test_event_payload_is_redacted_on_creation() -> None:
    event = Event(run_id="run_1", type="tool.invoked", payload={"api_key": "secret"})
    assert event.payload == {"api_key": "***REDACTED***"}


def test_provider_and_approval_events_are_part_of_the_contract() -> None:
    from typing import get_args

    from nfactory_core.events.contract import EventType

    assert {"provider.failed", "approval.requested", "approval.resolved"} <= set(
        get_args(EventType)
    )


def test_dashboard_listens_to_every_event_type() -> None:
    import re
    from pathlib import Path
    from typing import get_args

    from nfactory_core.events.contract import EventType

    source = Path(__file__).parents[3] / "apps/dashboard/lib/run-events.ts"
    block = source.read_text(encoding="utf-8").split("EVENT_TYPES = [", 1)[1].split("]", 1)[0]
    assert set(re.findall(r'"([a-z_.]+)"', block)) == set(get_args(EventType))
