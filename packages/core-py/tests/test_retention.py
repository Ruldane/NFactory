"""Retention policy of a workspace (ADR-0015): absent or unreadable means keep everything."""

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from nfactory_core.retention import RETENTION_BOUNDS, RetentionPolicy, cutoff, retention_policy


def test_no_saved_policy_keeps_everything() -> None:
    assert retention_policy({}) == RetentionPolicy(runs_days=None, audit_days=None)
    assert retention_policy(None) == RetentionPolicy()


def test_a_saved_policy_is_read_back() -> None:
    saved = {"run_limits": {}, "retention": {"runs_days": 90, "audit_days": 365}}

    assert retention_policy(saved) == RetentionPolicy(runs_days=90, audit_days=365)


def test_an_unreadable_saved_policy_keeps_everything() -> None:
    assert retention_policy({"retention": {"runs_days": 1}}) == RetentionPolicy()
    assert retention_policy({"retention": "90"}) == RetentionPolicy()


@pytest.mark.parametrize(
    "values",
    [{"runs_days": 6}, {"runs_days": 3651}, {"audit_days": 29}, {"other": 1}],
)
def test_out_of_bounds_or_unknown_values_are_refused(values: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        RetentionPolicy.model_validate(values)


def test_bounds_are_published_for_the_ui() -> None:
    assert RETENTION_BOUNDS == {"runs_days": (7, 3650), "audit_days": (30, 3650)}


def test_cutoff_is_none_when_kept_forever() -> None:
    now = datetime(2026, 11, 4, tzinfo=UTC)

    assert cutoff(now, None) is None
    assert cutoff(now, 30) == now - timedelta(days=30)
