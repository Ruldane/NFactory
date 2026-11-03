"""Coding-agent tasks on the user's machine through the bridge (tasks 4.3, 4.4): the
user's Codex, or a handoff to the user's own Claude Code, then a check in the sandbox.

Everything here comes back from another process: each field is bounded and anything
unknown is dropped. The start request needs `consent: true`, the user's explicit go."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

REPO_ID = r"^[a-z0-9][a-z0-9-]{0,49}$"
TASK_ID = r"^t_[0-9a-f]{12}$"
TaskStatus = Literal[
    "preparing",
    "running",
    "awaiting_user",
    "succeeded",
    "no_changes",
    "failed",
    "cancelled",
    "discarded",
]
Runtime = Literal["codex", "claude"]  # claude: handoff only, the user runs it (spec §6.5)
CheckStatus = Literal["queued", "running", "passed", "failed", "not_tested", "error"]


GITHUB_SLUG = r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}$"
PublicationState = Literal["local_commit_created", "pushed", "pr_created", "merged"]


class LocalRepo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(pattern=REPO_ID)
    name: str = Field(max_length=100)
    github: str | None = Field(default=None, pattern=GITHUB_SLUG)  # allowed push target


class LocalReposOut(BaseModel):
    repos: list[LocalRepo]


class AgentTaskIn(BaseModel):
    runtime: Runtime
    repo_id: str = Field(pattern=REPO_ID)
    task: str = Field(min_length=1, max_length=4_000)
    consent: Literal[True]  # the user agreed to run their own agent on this repository


class AgentEvent(BaseModel):
    """One event of the agent, as the bridge summarized it."""

    model_config = ConfigDict(extra="ignore")

    type: Literal[
        "started", "message", "command", "file_change", "completed", "failed", "error", "warning"
    ]
    text: str | None = Field(default=None, max_length=2_100)
    message: str | None = Field(default=None, max_length=600)
    command: str | None = Field(default=None, max_length=400)
    status: str | None = Field(default=None, max_length=30)
    exit_code: int | None = None
    changes: list[dict[str, str]] | None = Field(default=None, max_length=200)
    usage: dict[str, int] | None = None


class ManifestEntry(BaseModel):
    path: str = Field(max_length=400)
    change: Literal["added", "modified", "deleted"]


class PullRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    number: int
    url: str = Field(pattern=r"^https://github\.com/", max_length=300)
    state: str = Field(max_length=20)
    draft: bool
    head: str = Field(max_length=40)
    merged: bool


class Publication(BaseModel):
    """Publication facts as the bridge read them back from git and GitHub (spec §13)."""

    model_config = ConfigDict(extra="ignore")

    repo: str = Field(pattern=GITHUB_SLUG)
    commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    state: PublicationState | None
    pushed: bool
    pr: PullRequest | None
    verified_at: float


class AgentPublishIn(BaseModel):
    approve: Literal[True]  # the user approved this push and draft PR, separately from launch
    title: str = Field(min_length=1, max_length=200)


class AgentTaskOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(pattern=TASK_ID)
    runtime: Runtime
    repo_id: str = Field(pattern=REPO_ID)
    branch: str = Field(max_length=120)
    base: str = Field(max_length=64)
    status: TaskStatus
    events: list[AgentEvent] = Field(default_factory=list, max_length=500)
    manifest: list[ManifestEntry] = Field(default_factory=list, max_length=2_000)
    diff: str = Field(default="", max_length=400_000)
    diff_truncated: bool = False
    error: str = Field(default="", max_length=1_100)
    created_at: float
    publication: Publication | None = None


class AgentCheckOut(BaseModel):
    """A sandbox check of a task's change; `report` holds the JUnit counts and failures."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    repo_id: str
    runtime: str
    status: CheckStatus
    report: dict[str, Any] | None
    error: str
    created_at: datetime
    finished_at: datetime | None


def drop_invalid_events(raw: dict[str, Any]) -> dict[str, Any]:
    """An event of an unknown kind is left out rather than failing the whole task."""
    events = raw.get("events")
    if not isinstance(events, list):
        return raw
    kept = []
    for event in events:
        try:
            kept.append(AgentEvent.model_validate(event).model_dump(exclude_none=True))
        except ValueError:
            continue
    return {**raw, "events": kept}
