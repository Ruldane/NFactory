"""Local coding tools seen through the bridge (tasks 4.1, 4.2)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RuntimeStatus = Literal["not_installed", "installed", "needs_login", "connected"]
BridgeStatus = Literal["unreachable", "unpaired", "paired", "token_rejected"]


class PairingIn(BaseModel):
    # The code the bridge printed, e.g. ABCD-EFGH: checked before it reaches the bridge.
    code: str = Field(pattern=r"^\s*[A-Za-z0-9]{4}[- ]?[A-Za-z0-9]{4}\s*$")


class LocalRuntime(BaseModel):
    """What the bridge reports for one tool. Bounded: the bridge is another process."""

    model_config = ConfigDict(extra="ignore")

    kind: Literal["codex", "claude", "gh"]
    label: str = Field(max_length=60)
    status: RuntimeStatus
    version: str | None = Field(default=None, max_length=40)
    login: Literal["chatgpt", "api_key"] | None = None
    login_command: str | None = Field(default=None, max_length=60)
    modes: dict[str, Literal["available", "blocked_by_policy"]] = Field(default_factory=dict)
    detail: str = Field(default="", max_length=200)


class BridgeState(BaseModel):
    status: BridgeStatus
    message: str
    version: str | None = None


class LocalRuntimesOut(BaseModel):
    bridge: BridgeState
    runtimes: list[LocalRuntime]
