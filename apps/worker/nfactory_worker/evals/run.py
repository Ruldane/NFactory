"""Run one eval case through the real pipeline: demo engine, real recipe, real runner.

The reporter keeps what the database would keep: step outputs and event payloads go
through `redact` first, so a secret check measures what NFactory really stores.
"""

import os
import secrets
import shutil
import time
import uuid
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from nfactory_core.catalog import recipe_for_type
from nfactory_core.events.redaction import redact
from nfactory_worker.agents import Engines, demo_llm
from nfactory_worker.artifacts import LocalArtifactStore
from nfactory_worker.evals.cases import Case
from nfactory_worker.pipeline import (
    MemoryControl,
    MemoryKnowledge,
    MemoryReporter,
    ParentRun,
    PipelineDeps,
    RunInput,
    RunResult,
    execute_run,
)
from nfactory_worker.recipes import get_recipe
from nfactory_worker.runner import LocalRunner, Runner

# Tools a project type's checks need beyond Python.
_TOOLS = {"powershell": "pwsh", "webapp": "node"}
SECRET_SLOT = "{secret}"  # noqa: S105 - a placeholder, never a secret


class StoredReporter(MemoryReporter):
    """A MemoryReporter that keeps only what the database would: redacted copies."""

    async def step_succeeded(self, step: str, output: dict[str, Any]) -> None:
        await super().step_succeeded(step, redact(output))

    async def step_failed(
        self, step: str, error: str, output: dict[str, Any] | None = None
    ) -> None:
        await super().step_failed(step, error, redact(output) if output else None)

    async def emit(self, type: str, payload: dict[str, Any], step: str | None = None) -> None:
        await super().emit(type, redact(payload), step)


@dataclass
class EvalEnv:
    base: Path  # artifacts/ (and workspaces/ by default) go under it
    runner: Runner
    tools: frozenset[str] | None = None  # None: detected from the runner
    max_repairs: int = 3
    workspace_root: Path | None = None  # the sandbox's shared volume, when it runs there
    engines: Engines | None = None  # None: the demo engine (evals/engines.py opens others)

    @property
    def workspaces(self) -> Path:
        return self.workspace_root or self.base / "workspaces"

    def available_tools(self) -> frozenset[str]:
        if self.tools is not None:
            return self.tools
        if not isinstance(self.runner, LocalRunner):
            return frozenset({"python", *_TOOLS.values()})  # the sandbox image has them all
        found = {tool for tool in _TOOLS.values() if shutil.which(tool)}
        if "node" in found and not _local_web_deps():
            found.discard("node")  # generated frontends link the offline toolchain
        return frozenset({"python", *found})


@dataclass
class CaseRun:
    case: Case
    outcome: str = "SKIPPED"
    error: str | None = None
    duration_s: float = 0.0
    cost_usd: float | None = None
    reporter: StoredReporter = field(default_factory=StoredReporter)
    workspace: Path | None = None
    artifacts_dir: Path | None = None
    secret: str | None = None
    skipped: str | None = None
    parent_workspace: Path | None = None

    def cleanup(self) -> None:
        """Delete this case's workspaces (they may sit on the sandbox's shared volume)."""
        for path in (self.workspace, self.parent_workspace):
            if path is not None and path.name.startswith("run_eval_"):
                shutil.rmtree(path, ignore_errors=True)

    def metrics(self) -> dict[str, Any]:
        report = self.reporter.outputs.get("tests", {}).get("report") or {}
        events = self.reporter.events
        return {
            "outcome": self.outcome,
            "duration_s": round(self.duration_s, 3),
            "cost_usd": self.cost_usd,
            "llm_calls": sum(1 for kind, _p, _s in events if kind == "agent.progress"),
            "input_tokens": _tokens(events, "input_tokens"),
            "output_tokens": _tokens(events, "output_tokens"),
            "repairs": sum(1 for kind, _p, _s in events if kind == "repair.applied"),
            "tests": {
                "passed": int(report.get("passed", 0)),
                "failed": int(report.get("failed", 0)) + int(report.get("errors", 0)),
            },
            "findings": sum(
                int(p.get("findings", 0)) for kind, p, _s in events if kind == "security.scanned"
            ),
            "diff_lines": self.diff_lines(),
        }

    def diff_lines(self) -> int | None:
        diff = next(
            (a for a in self.reporter.artifacts if a.filename == "modifications.diff"), None
        )
        if diff is None:
            return None
        text = Path(diff.path).read_text(encoding="utf-8", errors="replace")
        return sum(
            1 for line in text.splitlines() if line[:1] in "+-" and line[:3] not in ("+++", "---")
        )


def _tokens(events: list[tuple[str, dict[str, Any], str | None]], key: str) -> int | None:
    """Tokens of the run's agent calls; None when a call reported none (not measured)."""
    calls = [p for kind, p, _s in events if kind == "agent.progress"]
    if any(not isinstance(p.get(key), int) for p in calls):
        return None
    return sum(int(p[key]) for p in calls)


async def run_case(case: Case, env: EvalEnv) -> CaseRun:
    run = CaseRun(case=case)
    needed = _TOOLS.get(case.project_type)
    if needed and needed not in env.available_tools():
        run.skipped = f"{needed} absent de ce poste (lancer les évals dans le sandbox)"
        return run

    secret = _fake_secret() if SECRET_SLOT in case.request else None
    run.secret = secret
    recipe = recipe_for_type(case.project_type).kind
    parent: ParentRun | None = None
    parent_cost: float | None = None
    started = time.monotonic()
    if case.parent_request:
        first = StoredReporter()
        parent_input = _input(case, recipe, case.parent_request)
        delivered = await execute_run(_deps(env, first, case), parent_input)
        run.parent_workspace = env.workspaces / parent_input.run_id
        parent_cost = delivered.cost_usd
        if delivered.outcome != "COMPLETED":
            run.outcome, run.error = "FAILED", f"projet de départ non livré : {delivered.error}"
            run.duration_s, run.cost_usd = time.monotonic() - started, parent_cost
            return run
        # The parent's request holds no secret slot, so its stored brief is the real one.
        brief = dict(first.outputs["requirements"]["brief"])
        parent = ParentRun(run_id=parent_input.run_id, brief=brief)
    request = case.request.replace(SECRET_SLOT, secret) if secret else case.request
    run_input = replace(_input(case, recipe, request), parent=parent)
    result: RunResult = await execute_run(_deps(env, run.reporter, case), run_input)
    run.duration_s = time.monotonic() - started
    run.outcome, run.error = result.outcome, result.error
    # A change request costs its parent plus itself; unknown if either is unknown.
    run.cost_usd = _add(result.cost_usd, parent_cost) if parent else result.cost_usd
    run.workspace = env.workspaces / run_input.run_id
    run.artifacts_dir = env.base / "artifacts" / run_input.run_id
    return run


def _local_web_deps() -> bool:
    """The offline frontend toolchain (apps/sandbox/web-deps), as the recipe tests use it."""
    if os.environ.get("NFACTORY_WEB_DEPS"):
        return True
    local = Path(__file__).resolve().parents[3] / "sandbox" / "web-deps" / "node_modules"
    if local.is_dir():
        os.environ["NFACTORY_WEB_DEPS"] = str(local)
        return True
    return False


def _deps(env: EvalEnv, reporter: StoredReporter, case: Case) -> PipelineDeps:
    return PipelineDeps(
        engines=env.engines or Engines.single(demo_llm()),
        runner=env.runner,
        workspace_root=env.workspaces,
        artifacts=LocalArtifactStore(env.base / "artifacts"),
        reporter=reporter,
        control=MemoryControl(reporter),
        recipes=get_recipe,
        max_repairs=env.max_repairs,
        retry_delay_s=0,
        knowledge=MemoryKnowledge(list(case.knowledge)) if case.knowledge else None,
    )


def _input(case: Case, recipe: str, request: str) -> RunInput:
    run_id = f"run_eval_{uuid.uuid4().hex[:12]}"
    return RunInput(
        run_id=run_id,
        project_id=f"proj_eval_{case.id.replace('-', '_')}",
        project_type=case.project_type,
        recipe_kind=recipe,
        title=case.title,
        request=request,
        trace_id=uuid.uuid4().hex,
    )


def _add(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else a + b


def _fake_secret() -> str:
    """A key shaped like a real Anthropic key, made up for this run only, so the
    dataset itself never holds one."""
    return "sk-ant-api03-" + secrets.token_urlsafe(30).replace("-", "a").replace("_", "b")
