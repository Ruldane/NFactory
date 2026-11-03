"""Repair loop (spec §5.2): failing checks -> debugger -> patch -> re-run, at most
`max_repairs` times. Without a patch, or past the limit, the failed step fails.

Every applied patch is traced (`repair.applied`, `repair_log`): attempt, failure,
diagnosis and files. The verification steps show the trace in the timeline.
"""

from typing import Any

from nfactory_worker.agents import DEBUGGER
from nfactory_worker.pipeline.nodes.common import (
    BudgetExceededError,
    Update,
    call_agent,
    workspace_of,
)
from nfactory_worker.pipeline.types import FactoryState, PipelineDeps

_FAILURE_CHARS = 600


async def debug(state: FactoryState, deps: PipelineDeps) -> Update:
    step = state.get("failed_step") or "tests"
    failures = state.get("failures", [])
    repairs = state.get("repairs", 0)
    log = state.get("repair_log", [])

    if repairs >= deps.max_repairs:
        error = f"Échec après {repairs} tentative(s) de correction : {_first(failures)}"
        return await _give_up(deps, state, step, error, "limite de tentatives atteinte")

    await deps.reporter.emit("repair.started", {"attempt": repairs + 1, "step": step}, step)
    workspace = workspace_of(deps, state)
    payload = {"failures": failures, "files": workspace.files()[:200]}
    try:
        call = await call_agent(deps, state, step, DEBUGGER, payload)
    except BudgetExceededError as exc:
        return await _give_up(deps, state, step, f"{_first(failures)}\n{exc}", "budget épuisé")
    analysis = call.output
    if not analysis.patches:
        error = f"{_first(failures)}\nDiagnostic : {analysis.cause}"
        return await _give_up(deps, state, step, error, "aucun correctif proposé")

    # Validates every path before writing anything (UnsafePathError fails the run).
    try:
        workspace.write_files({patch.path: patch.content for patch in analysis.patches})
    except ValueError as exc:
        return await _give_up(deps, state, step, f"Correctif refusé : {exc}", "correctif refusé")
    files = [patch.path for patch in analysis.patches]
    trace = {
        "attempt": repairs + 1,
        "step": step,
        "failure": _first(failures)[:_FAILURE_CHARS],
        "cause": analysis.cause,
        "files": files,
    }
    progress = call.agent | {"patched": files, "cause": analysis.cause}
    await deps.reporter.emit("agent.progress", progress, step)
    await deps.reporter.emit("repair.applied", trace, step)
    return {
        **call.counted,
        "repairs": repairs + 1,
        "repair_log": [*log, trace],
        "failed_step": None,
        "failures": [],
    }


async def _give_up(
    deps: PipelineDeps, state: FactoryState, step: str, error: str, reason: str
) -> Update:
    log: list[dict[str, Any]] = state.get("repair_log", [])
    attempt = state.get("repairs", 0) + 1
    abandoned = {"attempt": attempt, "step": step, "reason": reason}
    await deps.reporter.emit("repair.abandoned", abandoned, step)
    await deps.reporter.step_failed(step, error, {"repairs": log} if log else None)
    return {"outcome": "FAILED", "error": error}


def _first(failures: list[str]) -> str:
    return failures[0] if failures else "cause inconnue"
