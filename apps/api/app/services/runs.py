"""Run use cases: launch, read, cancel. Every lookup is scoped to the caller's workspaces."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.errors import AppError, not_found
from app.queue import JobQueue, QueueUnavailableError
from app.schemas.runs import ApprovalOut, RunCreate, RunDetail, RunProject, StepOut
from app.services.identity import RequestContext
from app.services.routing import launch_engines
from app.services.workspace_settings import run_limits
from nfactory_core.catalog import RecipeInfo, UnknownProjectTypeError, resolve_recipe
from nfactory_core.config import Settings
from nfactory_core.events import record_event
from nfactory_core.models import Approval, Project, Run, RunStep
from nfactory_core.roster import new_step_rows
from nfactory_core.routing import engines
from nfactory_core.states import TERMINAL_STATES, RunState, StepState, transition

MAX_IDEMPOTENCY_KEY = 64


@dataclass(frozen=True)
class Launched:
    run: RunDetail
    created: bool  # False when an Idempotency-Key replay returned an existing run


async def launch_run(
    sessions: async_sessionmaker[AsyncSession],
    ctx: RequestContext,
    settings: Settings,
    queue: JobQueue,
    project_id: str,
    data: RunCreate,
    idempotency_key: str | None,
    *,
    key_scope: str | None = None,
) -> Launched:
    """`key_scope` replaces the project as the key's scope (a recipe replay makes a new
    project each time, so its key belongs to the recipe)."""
    async with sessions() as session:
        project = await _owned_project(session, ctx, project_id)
        key = scoped_key(key_scope or project.id, idempotency_key)
        if key is not None:
            existing = await session.scalar(select(Run).where(Run.idempotency_key == key))
            if existing is not None:
                return Launched(await run_detail(session, existing), created=False)
        recipe = _buildable_recipe(project)
        parent_id = await _delivered_parent(session, project.id, data.parent_run_id)
        provider_config = await launch_engines(session, project.workspace_id, settings)
        run = Run(
            project_id=project.id,
            parent_run_id=parent_id,
            request=data.request,
            state=transition(RunState.DRAFT, RunState.QUEUED).value,
            idempotency_key=key,
            budget=(await run_limits(session, project.workspace_id, settings)).model_dump(),
            trace_id=uuid.uuid4().hex,
            provider_config=provider_config,
            is_demo=provider_config["mode"] == "demo",
        )
        session.add(run)
        await session.flush()
        session.add_all(new_step_rows(run.id, project.type))
        await session.commit()
        run_id = run.id

    await record_event(sessions, run_id, "run.created", {"state": "QUEUED", "recipe": recipe.kind})
    try:
        await queue.enqueue(run_id)
    except QueueUnavailableError:
        await fail_unqueued(sessions, run_id)
        raise AppError(
            503,
            "queue_unavailable",
            "La file d'attente est indisponible : le run n'a pas pu démarrer. "
            "Vérifiez que Redis et le worker tournent.",
        ) from None
    async with sessions() as session:
        return Launched(await run_detail(session, await session.get_one(Run, run_id)), created=True)


async def get_run(session: AsyncSession, ctx: RequestContext, run_id: str) -> RunDetail:
    return await run_detail(session, await owned_run(session, ctx, run_id))


async def cancel_run(
    sessions: async_sessionmaker[AsyncSession], ctx: RequestContext, run_id: str
) -> RunDetail:
    async with sessions() as session:
        run = await owned_run(session, ctx, run_id, lock=True)
        current = RunState(run.state)
        if current in TERMINAL_STATES:
            raise AppError(409, "run_finished", "Ce run est déjà terminé.")
        # A running run is stopped by the worker before its next step; it then records
        # run.cancelled itself. A run that never started is final right now.
        started = current is RunState.RUNNING
        run.state = transition(current, RunState.CANCELLED).value
        run.finished_at = datetime.now(UTC)
        await mark_steps(session, run_id, {StepState.PENDING}, StepState.CANCELLED)
        await session.commit()
    if started:
        payload = {"state": "CANCELLED", "requested_by": "user"}
        await record_event(sessions, run_id, "run.state_changed", payload)
    else:
        await record_event(sessions, run_id, "run.cancelled", {"state": "CANCELLED"})
    async with sessions() as session:
        return await run_detail(session, await session.get_one(Run, run_id))


async def owned_run(
    session: AsyncSession, ctx: RequestContext, run_id: str, *, lock: bool = False
) -> Run:
    query = (
        select(Run)
        .join(Project, Project.id == Run.project_id)
        .where(Run.id == run_id, Project.workspace_id.in_(ctx.workspace_ids))
    )
    if lock:
        query = query.with_for_update(of=Run)
    run = await session.scalar(query)
    if run is None:
        raise not_found("Run")
    return run


def _buildable_recipe(project: Project) -> RecipeInfo:
    try:
        recipe = resolve_recipe(project.type, project.template_id)
    except UnknownProjectTypeError:
        raise AppError(
            409, "recipe_unavailable", "Aucune recette ne sait construire ce type de projet."
        ) from None
    if not recipe.available:
        raise AppError(
            409,
            "recipe_unavailable",
            f"Le type « {recipe.label} » n'est pas encore disponible : il arrive en "
            f"phase {recipe.phase}.",
            {"kind": recipe.kind, "phase": recipe.phase},
        )
    return recipe


def scoped_key(scope: str, key: str | None) -> str | None:
    if key is None:
        return None
    if not 1 <= len(key) <= MAX_IDEMPOTENCY_KEY:
        raise AppError(
            400,
            "invalid_idempotency_key",
            f"Idempotency-Key doit faire entre 1 et {MAX_IDEMPOTENCY_KEY} caractères.",
        )
    return f"{scope}:{key}"


async def fail_unqueued(sessions: async_sessionmaker[AsyncSession], run_id: str) -> None:
    error = "File d'attente indisponible : le run n'a pas pu démarrer."
    async with sessions() as session:
        run = await session.get_one(Run, run_id, with_for_update=True)
        run.state = transition(RunState(run.state), RunState.FAILED).value
        run.error = error
        run.finished_at = datetime.now(UTC)
        await mark_steps(session, run_id, {StepState.PENDING}, StepState.SKIPPED)
        await session.commit()
    await record_event(sessions, run_id, "run.failed", {"state": "FAILED", "error": error})


async def mark_steps(
    session: AsyncSession, run_id: str, current: set[StepState], target: StepState
) -> None:
    steps = await session.scalars(
        select(RunStep).where(
            RunStep.run_id == run_id, RunStep.state.in_([s.value for s in current])
        )
    )
    for step in steps:
        step.state = target.value


async def _owned_project(session: AsyncSession, ctx: RequestContext, project_id: str) -> Project:
    project = await session.scalar(
        select(Project).where(Project.id == project_id, Project.workspace_id.in_(ctx.workspace_ids))
    )
    if project is None:
        raise not_found("Projet")
    return project


async def _delivered_parent(
    session: AsyncSession, project_id: str, parent_run_id: str | None
) -> str | None:
    """A child run starts from a delivered run of the same project."""
    if parent_run_id is None:
        return None
    parent = await session.scalar(
        select(Run).where(Run.id == parent_run_id, Run.project_id == project_id)
    )
    if parent is None:
        raise not_found("Run parent")
    if parent.state != RunState.COMPLETED.value:
        raise AppError(
            409,
            "parent_not_completed",
            "Seul un run livré (terminé avec succès) peut recevoir une évolution.",
        )
    return parent.id


async def run_detail(session: AsyncSession, run: Run) -> RunDetail:
    project = await session.get_one(Project, run.project_id)
    steps = await session.scalars(
        select(RunStep).where(RunStep.run_id == run.id).order_by(RunStep.position)
    )
    pending = await session.scalar(
        select(Approval)
        .where(Approval.run_id == run.id, Approval.status == "pending")
        .order_by(Approval.created_at.desc())
        .limit(1)
    )
    try:
        recipe: str | None = resolve_recipe(project.type, project.template_id).kind
    except UnknownProjectTypeError:
        recipe = None
    return RunDetail(
        id=run.id,
        project=RunProject(id=project.id, title=project.title, type=project.type),
        recipe=recipe,
        model="demo"
        if engines(run.provider_config).get("planner", {}).get("provider") == "demo"
        else None,
        engines=engines(run.provider_config),
        request=run.request,
        parent_run_id=run.parent_run_id,
        state=run.state,
        error=run.error,
        cost_estimate_usd=run.cost_estimate_usd,
        budget=run.budget or {},
        trace_id=run.trace_id,
        is_demo=run.is_demo,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        steps=[StepOut.model_validate(step) for step in steps],
        pending_approval=(
            ApprovalOut.model_validate(pending)
            if pending and run.state == RunState.APPROVAL_PENDING.value
            else None
        ),
    )
