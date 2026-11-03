"""Debugger agent: failing checks -> diagnosis and optional file patches."""

from pydantic import BaseModel, Field

from nfactory_worker.agents.base import Agent


class FilePatch(BaseModel):
    path: str  # relative to the workspace; validated by Workspace before writing
    content: str  # full new file content


class DebugAnalysis(BaseModel):
    cause: str
    proposed_fix: str
    patches: list[FilePatch] = Field(default_factory=list, max_length=20)


DEBUGGER = Agent(
    name="debugger",
    prompt_version="1",
    instructions="""
You diagnose failing checks. Give the most likely cause and a fix. Provide patches
(full file contents) only when you are confident; otherwise return no patch.
""",
    output_model=DebugAnalysis,
)
