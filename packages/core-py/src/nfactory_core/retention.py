"""Retention policy of a workspace (ADR-0015), kept in `workspaces.data_policy`.

No value means keep forever, and so does a saved value that no longer validates: when
in doubt, nothing is deleted. The worker applies the policy (`apply_retention` job).

Interface: RETENTION_KEY, RETENTION_BOUNDS, RetentionPolicy, retention_policy, cutoff.
"""

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

RETENTION_KEY = "retention"
RETENTION_BOUNDS: dict[str, tuple[int, int]] = {
    "runs_days": (7, 3650),
    "audit_days": (30, 3650),  # the CNIL suggests keeping logs 6 months to a year
}


def _days(key: str) -> Any:
    low, high = RETENTION_BOUNDS[key]
    return Field(default=None, ge=low, le=high)


class RetentionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    runs_days: int | None = _days("runs_days")  # finished runs, with their deliverables
    audit_days: int | None = _days("audit_days")


def retention_policy(data_policy: Mapping[str, Any] | None) -> RetentionPolicy:
    saved = (data_policy or {}).get(RETENTION_KEY)
    if not saved:
        return RetentionPolicy()
    try:
        return RetentionPolicy.model_validate(saved)
    except ValidationError:
        return RetentionPolicy()


def cutoff(now: datetime, days: int | None) -> datetime | None:
    """Rows older than this are expired; None keeps them all."""
    return None if days is None else now - timedelta(days=days)
