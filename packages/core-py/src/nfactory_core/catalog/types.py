"""Catalog entry type. Pure data shared by the API (listing) and the worker (generation)."""

from dataclasses import dataclass
from typing import Literal

Deliverable = Literal["code", "non-code"]

# Recipes whose phase is <= CURRENT_PHASE are implemented and tested.
CURRENT_PHASE = 3


@dataclass(frozen=True)
class RecipeInfo:
    kind: str  # recipe id, e.g. "python-api"
    project_type: str  # value stored in projects.type
    label: str  # French UI label
    description: str  # French UI description
    deliverable: Deliverable
    outputs: tuple[str, ...]  # what the user gets, in French
    phase: int  # implementation phase in IMPLEMENTATION_STATUS.md

    @property
    def available(self) -> bool:
        return self.phase <= CURRENT_PHASE
