"""Contracts of reusable factory recipes (task 5.5, spec F38)."""

from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.projects import ProjectType


class SavedRecipeIn(BaseModel):
    """Saved from a delivered run (`run_id`), or written by hand (`project_type` + `request`)."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=5000)
    run_id: str | None = Field(default=None, max_length=64)
    project_type: ProjectType | None = None
    request: str | None = Field(default=None, min_length=1, max_length=20_000)

    @model_validator(mode="after")
    def _one_source(self) -> Self:
        by_hand = self.project_type is not None or self.request is not None
        if self.run_id is not None and by_hand:
            raise ValueError("Une recette vient d'un run livré ou d'une demande, pas des deux.")
        if self.run_id is None and (self.project_type is None or self.request is None):
            raise ValueError("Indiquez un run livré, ou un type de projet et une demande.")
        return self


class SavedRecipeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str
    project_type: str
    template_id: str | None
    request: str
    source_run_id: str | None
    created_by: str | None
    created_at: datetime
    uses: int
    last_used_at: datetime | None


class RecipeLaunch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # The new project's title; the recipe's name when absent.
    title: str | None = Field(default=None, min_length=1, max_length=200)
