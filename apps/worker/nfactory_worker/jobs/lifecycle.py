"""Run lifecycle around the pipeline: claim the run, then record its final state or
its pause for a user decision."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nfactory_core.events import Notifier, record_event
from nfactory_core.models import Approval, Project, Run, RunStep
from nfactory_core.roster import new_step_rows
from nfactory_core.states import TERMINAL_STATES, RunState, StepState, transition
from nfactory_worker.jobs.reporting import Sessions
from nfactory_worker.pipeline import ParentRun, RunResult

_FINAL = {
    "COMPLETED": (RunState.COMPLETED, "run.completed"),
    "FAILED": (RunState.FAILED, "run.failed"),
    "CANCELLED": (RunState.CANCELLED, "run.cancelled"),
}


@dataclass(frozen=True)
class ClaimedRun:
    run_id: str
    project_id: str
    project_type: str
    template_id: str | None
    title: str
    request: str
    is_demo: bool
    trace_id: str
    budget: dict[str, Any]
    workspace_id: str
    provider_config: dict[str, Any]
    parent: ParentRun | None = None  # a change request on a delivered run


async def claim(sessions: Sessions, run_id: str, notify: Notifier | None) -> ClaimedRun | None:
    """Move the run to RUNNING and make sure its step rows exist.

    Returns None when there is nothing to do (finished or cancelled before start).
    A run already RUNNING is a resumed run (worker restart) and is claimed again.
    """
    async with sessions() as session:
        run = await session.get(Run, run_id, with_for_update=True)
        if run is None or RunState(run.state) in TERMINAL_STATES:
            return None
        project = await session.get_one(Project, run.project_id)
        resumed = run.state == RunState.RUNNING.value
        if not resumed:
            run.state = transition(RunState(run.state), RunState.RUNNING).value
            run.started_at = run.started_at or datetime.now(UTC)
        await _ensure_steps(session, run_id, project.type)
        await session.commit()
        claimed = ClaimedRun(
            run_id=run.id,
            project_id=project.id,
            project_type=project.type,
            template_id=project.template_id,
            title=project.title,
            request=run.request,
            is_demo=run.is_demo,
            # Runs created before trace ids existed fall back to their own id.
            trace_id=run.trace_id or run.id,
            budget=dict(run.budget or {}),
            workspace_id=project.workspace_id,
            provider_config=dict(run.provider_config or {}),
            parent=await _parent(session, run.parent_run_id),
        )
    event = "run.state_changed" if resumed else "run.started"
    await record_event(
        sessions, run_id, event, {"state": "RUNNING", "resumed": resumed}, None, notify
    )
    return claimed


async def _parent(session: AsyncSession, parent_run_id: str | None) -> ParentRun | None:
    """The delivered brief a child run starts from (its parent's requirements output)."""
    if parent_run_id is None:
        return None
    output = await session.scalar(
        select(RunStep.output).where(
            RunStep.run_id == parent_run_id, RunStep.name == "requirements"
        )
    )
    brief = (output or {}).get("brief")
    return ParentRun(parent_run_id, dict(brief) if isinstance(brief, dict) else {})


async def finish(
    sessions: Sessions,
    run_id: str,
    result: RunResult,
    cost_usd: float | None,
    notify: Notifier | None,
) -> RunState:
    target, event_type = _FINAL[result.outcome]
    async with sessions() as session:
        run = await session.get_one(Run, run_id, with_for_update=True)
        current = RunState(run.state)
        # The user may have cancelled meanwhile: their decision wins.
        final = current if current in TERMINAL_STATES else transition(current, target)
        run.state = final.value
        run.finished_at = datetime.now(UTC)
        run.cost_estimate_usd = cost_usd
        if final is RunState.FAILED:
            run.error = result.error
        leftover = StepState.CANCELLED if final is RunState.CANCELLED else StepState.SKIPPED
        steps = await session.scalars(
            select(RunStep).where(
                RunStep.run_id == run_id,
                RunStep.state.in_([StepState.PENDING.value, StepState.RUNNING.value]),
            )
        )
        for step in steps:
            step.state = leftover.value
        await session.commit()
    # Report the state actually stored (e.g. a user cancellation), not the pipeline's.
    event_type = _FINAL.get(final.value, (final, event_type))[1]
    payload = {"state": final.value} | ({"error": result.error} if final is RunState.FAILED else {})
    await record_event(sessions, run_id, event_type, payload, None, notify)
    return final


async def pause_for_engine(
    sessions: Sessions, run_id: str, result: RunResult, notify: Notifier | None
) -> RunState:
    """An engine failed and the routing says to ask: wait for the user's decision.

    The run keeps its checkpoint; once approved it is queued again and resumes at the
    step that failed. The user may also have cancelled meanwhile: that wins.
    """
    details = dict(result.pause or {})
    async with sessions() as session:
        run = await session.get_one(Run, run_id, with_for_update=True)
        current = RunState(run.state)
        if current in TERMINAL_STATES:
            return current
        run.state = transition(current, RunState.APPROVAL_PENDING).value
        steps = await session.scalars(
            select(RunStep).where(
                RunStep.run_id == run_id, RunStep.state == StepState.RUNNING.value
            )
        )
        for step in steps:
            step.state = StepState.PENDING.value
        approval = Approval(
            run_id=run_id,
            action_type="provider_fallback",
            summary=result.error or "Le moteur IA a échoué.",
            details=details,
        )
        session.add(approval)
        await session.commit()
        approval_id = approval.id
    payload = {"state": RunState.APPROVAL_PENDING.value, "approval_id": approval_id} | details
    await record_event(sessions, run_id, "approval.requested", payload, None, notify)
    return RunState.APPROVAL_PENDING


async def _ensure_steps(session: AsyncSession, run_id: str, project_type: str) -> None:
    existing = set(await session.scalars(select(RunStep.name).where(RunStep.run_id == run_id)))
    session.add_all(row for row in new_step_rows(run_id, project_type) if row.name not in existing)
