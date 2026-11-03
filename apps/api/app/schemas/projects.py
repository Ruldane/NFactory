"""Project request/response contracts."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from nfactory_core.catalog import PROJECT_TYPES


def _known_type(value: str) -> str:
    if value not in PROJECT_TYPES:
        raise ValueError(f"unknown project type, expected one of: {', '.join(PROJECT_TYPES)}")
    return value


# Every catalog type can hold a project; whether it can be built yet is checked per run.
ProjectType = Annotated[str, AfterValidator(_known_type)]
ProjectStatus = Literal["active", "archived"]


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    type: ProjectType
    description: str = Field(default="", max_length=5000)
    template_id: str | None = Field(default=None, max_length=100)


class ProjectUpdate(BaseModel):
    # extra="forbid": only these fields may change; anything else is a 422.
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: ProjectStatus | None = None


class RunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    state: str
    error: str | None
    is_demo: bool
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    description: str
    type: str
    template_id: str | None
    status: str
    is_demo: bool
    created_at: datetime
    updated_at: datetime


class ProjectDetail(ProjectOut):
    latest_run: RunSummary | None
