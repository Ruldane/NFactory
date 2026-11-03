"""Architect agent: brief + recipe -> components and design decisions."""

from pydantic import BaseModel, Field

from nfactory_worker.agents.base import Agent


class Component(BaseModel):
    name: str
    responsibility: str


class ArchitectureNote(BaseModel):
    components: list[Component] = Field(min_length=1)
    decisions: list[str] = Field(default_factory=list)


ARCHITECT = Agent(
    name="architect",
    prompt_version="1",
    instructions="""
You describe the structure of the deliverable produced by the recipe: its components,
each with one responsibility, and the key decisions with their reason.
""",
    output_model=ArchitectureNote,
)
