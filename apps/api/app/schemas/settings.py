"""Workspace settings contracts."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from nfactory_core.retention import RetentionPolicy

# A full run takes about 20 graph steps when every repair attempt is used.
LIMIT_BOUNDS: dict[str, tuple[int, int]] = {
    "max_llm_calls": (1, 500),
    "max_agent_steps": (20, 500),
    "max_repair_attempts": (0, 10),
}


def _bounded(key: str) -> Any:
    low, high = LIMIT_BOUNDS[key]
    return Field(ge=low, le=high)


class RunLimits(BaseModel):
    """Frozen into each run at launch (`runs.budget`); the worker enforces them."""

    model_config = ConfigDict(extra="forbid")
    max_llm_calls: int = _bounded("max_llm_calls")
    max_agent_steps: int = _bounded("max_agent_steps")
    max_repair_attempts: int = _bounded("max_repair_attempts")


class Bounds(BaseModel):
    min: int
    max: int


class SettingsOut(BaseModel):
    mode: str
    demo_mode: bool
    sandbox: Literal["isolated", "local"]  # local = checks run as plain subprocesses (dev)
    run_limits: RunLimits
    limit_bounds: dict[str, Bounds]
    retention: RetentionPolicy  # ADR-0015: None keeps forever
    retention_bounds: dict[str, Bounds]
