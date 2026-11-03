"""Recipe interface: one implementation per project type (code or non-code).

A recipe turns a Brief into files plus the deterministic checks that prove the result
works. The pipeline only knows this interface, so new project types never touch it.
"""

from dataclasses import dataclass
from typing import Literal, Protocol

from nfactory_worker.brief import Brief

Stage = Literal["static", "build", "tests"]
STAGE_ORDER: tuple[Stage, ...] = ("static", "build", "tests")


@dataclass(frozen=True)
class Check:
    name: str  # French label shown in the UI
    stage: Stage
    argv: tuple[str, ...]
    timeout_s: int = 120
    junit_path: str | None = None  # set when the check writes a JUnit report


@dataclass(frozen=True)
class Preview:
    """How to run the generated app for a live preview in the sandbox (spec §3.1)."""

    argv: tuple[str, ...]  # run from the workspace root, allow-listed like checks
    port: int  # the app listens on 0.0.0.0:<port> inside its container


@dataclass(frozen=True)
class RenderedProject:
    files: dict[str, str | bytes]
    checks: tuple[Check, ...]
    # Files produced by the build checks and published as separate artifacts.
    deliverables: tuple[str, ...] = ()
    preview: Preview | None = None  # None: this deliverable has nothing to preview

    def checks_for(self, stage: Stage) -> tuple[Check, ...]:
        return tuple(check for check in self.checks if check.stage == stage)

    def ordered_checks(self) -> tuple[Check, ...]:
        return tuple(check for stage in STAGE_ORDER for check in self.checks_for(stage))


class Recipe(Protocol):
    kind: str
    version: str

    def render(self, brief: Brief) -> RenderedProject: ...
