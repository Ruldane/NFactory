"""The user's decision on a paused run (task 2.8).

When an engine fails and the routing says "ask_user", the worker pauses the run with a
`provider_fallback` approval. Approving queues the run again, on the same engine (a
retry, e.g. after a top-up) or on a replacement the user chose; rejecting fails it.
The run resumes from its checkpoint: the steps already done are kept.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.errors import AppError, not_found
from app.queue import JobQueue, QueueUnavailableError
from app.schemas.runs import ApprovalDecision, RunDetail
from app.services import model_catalog
from app.services.identity import RequestContext
from app.services.runs import fail_unqueued, mark_steps, owned_run, run_detail
from nfactory_core.connections import connection_facts, workspace_connections
from nfactory_core.events import record_event
from nfactory_core.models import Approval, Project, Run
from nfactory_core.providers import label
from nfactory_core.routing import Route, policy_violation
from nfactory_core.states import RunState, StepState, transition


async def approve(
    sessions: async_sessionmaker[AsyncSession],
    ctx: RequestContext,
    queue: JobQueue,
    run_id: str,
    approval_id: str,
    decision: ApprovalDecision,
) -> RunDetail:
    async with sessions() as session:
        run, approval = await _paused(session, ctx, run_id, approval_id)
        failed = (approval.details.get("provider"), approval.details.get("model"))
        config = dict(run.provider_config or {})
        if decision.replacement is not None:
            new = await _replacement_route(session, run, config, decision.replacement)
            config["routes"] = {
                role: (new if (r.get("provider"), r.get("model")) == failed else r)
                for role, r in (config.get("routes") or {}).items()
            }
        run.provider_config = config
        run.state = transition(RunState.APPROVAL_PENDING, RunState.QUEUED).value
        chosen = decision.replacement or Route(provider=str(failed[0]), model=str(failed[1]))
        _decide(approval, ctx, "approved", chosen)
        await session.commit()
    await record_event(
        sessions,
        run_id,
        "approval.resolved",
        {"approval_id": approval_id, "decision": "approved"} | chosen.model_dump(),
    )
    try:
        await queue.enqueue(run_id)
    except QueueUnavailableError:
        await fail_unqueued(sessions, run_id)
        raise AppError(
            503,
            "queue_unavailable",
            "La file d'attente est indisponible : le run n'a pas pu reprendre.",
        ) from None
    async with sessions() as session:
        return await run_detail(session, await session.get_one(Run, run_id))


async def reject(
    sessions: async_sessionmaker[AsyncSession],
    ctx: RequestContext,
    run_id: str,
    approval_id: str,
) -> RunDetail:
    async with sessions() as session:
        run, approval = await _paused(session, ctx, run_id, approval_id)
        error = f"{approval.summary} Remplacement du moteur refusé : run arrêté."
        run.state = transition(RunState.APPROVAL_PENDING, RunState.FAILED).value
        run.error = error
        run.finished_at = datetime.now(UTC)
        await mark_steps(session, run_id, {StepState.PENDING}, StepState.SKIPPED)
        _decide(approval, ctx, "rejected", None)
        await session.commit()
    payload = {"approval_id": approval_id, "decision": "rejected"}
    await record_event(sessions, run_id, "approval.resolved", payload)
    await record_event(sessions, run_id, "run.failed", {"state": "FAILED", "error": error})
    async with sessions() as session:
        return await run_detail(session, await session.get_one(Run, run_id))


async def _paused(
    session: AsyncSession, ctx: RequestContext, run_id: str, approval_id: str
) -> tuple[Run, Approval]:
    run = await owned_run(session, ctx, run_id, lock=True)
    approval = await session.scalar(
        select(Approval)
        .where(Approval.id == approval_id, Approval.run_id == run.id)
        .with_for_update()
    )
    if approval is None or approval.action_type != "provider_fallback":
        raise not_found("Demande de décision")
    if approval.status != "pending":
        raise AppError(409, "approval_resolved", "Cette décision a déjà été prise.")
    if run.state != RunState.APPROVAL_PENDING.value:
        raise AppError(409, "run_not_paused", "Ce run n'attend pas de décision.")
    return run, approval


async def _replacement_route(
    session: AsyncSession, run: Run, config: dict[str, object], route: Route
) -> dict[str, object]:
    """The same checks as a launch: connected, and local when the run is local-only."""
    project = await session.get_one(Project, run.project_id)
    facts = connection_facts(await workspace_connections(session, project.workspace_id))
    fact = facts.get(route.provider)
    if fact is None or fact.status != "connected":
        raise AppError(
            409,
            "provider_not_ready",
            f"{label(route.provider)} n'est pas connecté : testez la connexion dans Moteurs IA.",
        )
    violation = policy_violation(
        fact,
        local_only=bool(config.get("local_only")),
        eu_only=bool(config.get("eu_only")),
    )
    if violation is not None:
        raise AppError(409, violation.code, violation.message)
    return {
        "provider": route.provider,
        "model": route.model,
        "pricing": await model_catalog.price_of(session, route.provider, route.model),
    }


def _decide(approval: Approval, ctx: RequestContext, status: str, chosen: Route | None) -> None:
    approval.status = status
    approval.approver_id = ctx.user_id
    approval.decided_at = datetime.now(UTC)
    decision = {"status": status} | (chosen.model_dump() if chosen else {})
    approval.details = {**(approval.details or {}), "decision": decision}
