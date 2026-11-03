"""Reviewer agent: comments on verified check results. It never decides that tests
passed: the runner already did."""

from typing import Literal

from pydantic import BaseModel, Field

from nfactory_worker.agents.base import Agent


class Finding(BaseModel):
    severity: Literal["info", "warning", "blocker"]
    message: str


class Review(BaseModel):
    verdict: Literal["approve", "changes_requested"]
    findings: list[Finding] = Field(default_factory=list)


REVIEWER = Agent(
    name="reviewer",
    prompt_version="3",
    instructions="""
You review a generated deliverable from the verified results of its checks.
Request changes when any check failed. Report known limits as warnings.
You also get the secret scan summary, the list of files and the history of automatic
repairs: list each repaired file as a point for a human to re-read. The check results
are the only proof that tests passed; never state otherwise.
When INPUT.changes is present, this run changes a delivered project: read its diff,
and flag as a point any change that goes beyond what the request asked.
""",
    output_model=Review,
)
