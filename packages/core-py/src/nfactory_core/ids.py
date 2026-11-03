"""Prefixed text IDs (`run_…`, `proj_…`), readable in logs and in the UI."""

from uuid import uuid4


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:20]}"
