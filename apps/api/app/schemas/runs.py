"""Run, recipe and artifact contracts."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from nfactory_core.routing import Route


class RunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request: str = Field(min_length=1, max_length=20_000)
    # A change request on a delivered run of the same project (scenario E, §3.5).
    parent_run_id: str | None = Field(default=None, max_length=64)


class StepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    position: int
    name: str
    agent_role: str
    state: str
    attempts: int
    output: dict[str, Any]
    started_at: datetime | None
    ended_at: datetime | None
    error: str | None


class ApprovalOut(BaseModel):
    """A decision the run waits for (an engine failed, spec §6.3)."""

    model_config = ConfigDict(from_attributes=True)
    id: str
    action_type: str
    summary: str
    details: dict[str, Any]
    status: str
    created_at: datetime


class ApprovalDecision(BaseModel):
    """No engine: retry the same one. Both fields: switch to that engine."""

    model_config = ConfigDict(extra="forbid")
    provider: str | None = None
    model: str | None = None

    @model_validator(mode="after")
    def _both_or_none(self) -> "ApprovalDecision":
        if (self.provider is None) != (self.model is None):
            raise ValueError("indiquez le fournisseur et le modèle, ou aucun des deux")
        if self.provider is not None:
            Route(provider=self.provider, model=self.model or "")
        return self

    @property
    def replacement(self) -> Route | None:
        if self.provider is None or self.model is None:
            return None
        return Route(provider=self.provider, model=self.model)


class RunProject(BaseModel):
    id: str
    title: str
    type: str


class RunDetail(BaseModel):
    id: str
    project: RunProject
    recipe: str | None
    model: str | None  # "demo" when the offline demo model answers
    engines: dict[str, dict[str, str]]  # role -> {provider, model}, frozen at launch
    request: str
    parent_run_id: str | None = None  # set for a change request on a delivered run
    state: str
    error: str | None
    cost_estimate_usd: float | None
    budget: dict[str, int]
    trace_id: str | None
    is_demo: bool
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    steps: list[StepOut]
    pending_approval: ApprovalOut | None = None


class RecipeOut(BaseModel):
    kind: str
    project_type: str
    label: str
    description: str
    deliverable: str
    outputs: list[str]
    phase: int
    available: bool


class PreviewOut(BaseModel):
    """A run's live preview: `url` is the gateway page to frame, None when stopped."""

    running: bool
    url: str | None = None
    expires_in_s: int | None = None


class FileList(BaseModel):
    files: list[str]


class FileContent(BaseModel):
    path: str
    content: str | None  # None for binary files (xlsx, docx, ...): download them instead
    binary: bool
    size: int


class ArtifactOut(BaseModel):
    id: str
    filename: str
    mime: str
    size: int
    checksum: str
    created_at: datetime
    download_url: str
