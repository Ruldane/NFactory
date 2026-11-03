"""Overview KPIs (spec §9.3), computed from the database for the caller's workspaces."""

from sqlalchemy import ColumnElement, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.schemas.dashboard import DashboardSummary, RecentRun, RunCounts, StepBrief
from app.services.identity import RequestContext
from nfactory_core.models import Approval, Project, Run
from nfactory_core.states import TERMINAL_STATES, RunState

RECENT_RUNS_LIMIT = 5


async def build_summary(session: AsyncSession, ctx: RequestContext) -> DashboardSummary:
    project_in_scope = Project.workspace_id.in_(ctx.workspace_ids)
    run_in_scope = Run.project_id.in_(select(Project.id).where(project_in_scope))

    counts = await _run_counts(session, run_in_scope)
    finished = counts.completed + counts.partial + counts.failed + counts.cancelled

    avg_duration = await session.scalar(
        select(func.avg(func.extract("epoch", Run.finished_at - Run.started_at))).where(
            run_in_scope, Run.finished_at.is_not(None), Run.started_at.is_not(None)
        )
    )
    cost = await session.scalar(select(func.sum(Run.cost_estimate_usd)).where(run_in_scope))
    approvals = await session.scalar(
        select(func.count())
        .select_from(Approval)
        .join(Run, Approval.run_id == Run.id)
        .where(run_in_scope, Approval.status == "pending")
    )
    recent = await session.execute(
        select(Run, Project.title)
        .options(selectinload(Run.steps))  # one extra query, ordered by position
        .join(Project, Run.project_id == Project.id)
        .where(project_in_scope)
        .order_by(Run.created_at.desc())
        .limit(RECENT_RUNS_LIMIT)
    )
    has_demo = await session.scalar(
        select(exists().where(project_in_scope, Project.is_demo.is_(True)))
    )

    return DashboardSummary(
        demo_data=bool(has_demo),
        projects=await session.scalar(select(func.count()).where(project_in_scope)) or 0,
        runs=counts,
        success_rate=counts.completed / finished if finished else None,
        avg_duration_seconds=float(avg_duration) if avg_duration is not None else None,
        cost_estimate_usd=float(cost) if cost is not None else None,
        approvals_pending=approvals or 0,
        recent_runs=[
            RecentRun(
                id=run.id,
                project_id=run.project_id,
                project_title=title,
                state=run.state,
                is_demo=run.is_demo,
                created_at=run.created_at,
                finished_at=run.finished_at,
                steps=[
                    StepBrief(
                        name=s.name, agent_role=s.agent_role, state=s.state, attempts=s.attempts
                    )
                    for s in run.steps
                ],
            )
            for run, title in recent
        ],
    )


async def _run_counts(session: AsyncSession, run_in_scope: ColumnElement[bool]) -> RunCounts:
    rows = await session.execute(
        select(Run.state, func.count()).where(run_in_scope).group_by(Run.state)
    )
    by_state = {state: n for state, n in rows}
    total = sum(by_state.values())
    terminal = sum(n for state, n in by_state.items() if state in TERMINAL_STATES)
    return RunCounts(
        total=total,
        active=total - terminal,
        completed=by_state.get(RunState.COMPLETED, 0),
        partial=by_state.get(RunState.PARTIAL, 0),
        failed=by_state.get(RunState.FAILED, 0),
        cancelled=by_state.get(RunState.CANCELLED, 0),
    )
