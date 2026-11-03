"""Planner agent: brief -> execution plan (spec §5.1 ExecutionPlan)."""

from typing import Literal

from pydantic import BaseModel, Field

from nfactory_worker.agents.base import Agent


class WorkItem(BaseModel):
    id: str
    title: str
    description: str
    depends_on: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str]
    risk: Literal["low", "medium", "high"]


class ExecutionPlan(BaseModel):
    project_kind: str  # a catalog project_type
    summary: str
    tasks: list[WorkItem] = Field(min_length=1)
    requested_tools: list[str] = Field(default_factory=list)
    requires_approval: bool = False


PLANNER = Agent(
    name="planner",
    prompt_version="1",
    instructions="""
You plan how to build the brief with the given recipe. Produce ordered tasks with
verifiable acceptance criteria. Set requires_approval to true only for sensitive
actions (privileged commands, external publication, deletion of data).
""",
    output_model=ExecutionPlan,
)
