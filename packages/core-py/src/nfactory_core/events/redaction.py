"""Secret redaction, applied before anything is stored or broadcast (spec §14.1, §15)."""

import re
from typing import Any

REDACTED = "***REDACTED***"

_SENSITIVE_KEY = re.compile(
    r"(api[_-]?key|token|secret|password|authorization|cookie)", re.IGNORECASE
)
_SECRET_VALUES = [
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{16,}"),
]


def redact(value: Any) -> Any:
    """Return a copy where sensitive keys and secret-looking values are replaced by
    REDACTED. The input is never mutated."""
    if isinstance(value, dict):
        return {
            k: REDACTED if _SENSITIVE_KEY.search(str(k)) else redact(v) for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        for pattern in _SECRET_VALUES:
            value = pattern.sub(REDACTED, value)
    return value
