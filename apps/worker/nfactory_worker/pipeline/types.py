"""Pipeline inputs, outputs, dependencies and the graph state."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypedDict

from nfactory_worker.agents import Engines
from nfactory_worker.artifacts import ArtifactStore
from nfactory_worker.pipeline.ports import Knowledge, Reporter, RunControl
from nfactory_worker.recipes import Recipe
from nfactory_worker.runner import Runner

# APPROVAL_PENDING: an engine failed and the routing asks the user what to do.
Outcome = Literal["COMPLETED", "FAILED", "CANCELLED", "APPROVAL_PENDING"]


@dataclass(frozen=True)
class ParentRun:
    """The delivered run a change request starts from (scenario E, §3.5)."""

    run_id: str
    brief: dict[str, Any]


@dataclass(frozen=True)
class RunInput:
    run_id: str
    project_id: str
    project_type: str
    recipe_kind: str
    title: str
    request: str
    trace_id: str = ""  # follows the run through every agent call and event
    parent: ParentRun | None = None  # set for a change request on a delivered run


@dataclass(frozen=True)
class RunResult:
    outcome: Outcome
    error: str | None = None
    cost_usd: float | None = None  # None when one engine had no known price
    pause: dict[str, Any] | None = None  # the failed engine, when APPROVAL_PENDING


@dataclass(frozen=True)
class PipelineDeps:
    engines: Engines
    runner: Runner
    workspace_root: Path
    artifacts: ArtifactStore
    reporter: Reporter
    control: RunControl
    recipes: Callable[[str], Recipe]
    max_repairs: int = 3
    max_llm_calls: int = 80  # agent calls per run (the run's budget)
    max_steps: int = 100  # graph steps per invocation (MAX_AGENT_STEPS)
    retry_delay_s: float = 2.0  # first pause before retrying a temporary provider error
    knowledge: Knowledge | None = None  # the project's knowledge base, if it has one


class FactoryState(TypedDict, total=False):
    """Checkpointed between steps, so every value must be JSON-serialisable."""

    run_id: str
    project_id: str
    project_type: str
    recipe_kind: str
    title: str
    request: str
    trace_id: str
    llm_calls: int  # agent calls so far, checked against PipelineDeps.max_llm_calls
    cost_usd: float | None  # sum of known call costs; None once a price is unknown
    brief: dict[str, Any]
    checks: list[dict[str, Any]]  # the recipe's checks
    deliverables: list[str]
    preview: dict[str, Any] | None  # how to run the app for a live preview (recipe)
    results: dict[str, list[dict[str, Any]]]  # latest results per step ("checks", "tests")
    failed_step: str | None  # set while a repair is pending
    failures: list[str]
    repairs: int
    repair_log: list[dict[str, Any]]  # one entry per applied patch (timeline, reviewer)
    parent_run_id: str | None  # child run: the delivered run it changes
    parent_brief: dict[str, Any] | None
    changes: dict[str, Any] | None  # child run: what changed since the parent (summary)
    changes_patch: str  # child run: the unified diff, saved as an artifact
    outcome: str
    error: str | None
