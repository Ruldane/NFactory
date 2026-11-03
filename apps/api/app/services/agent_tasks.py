"""Coding-agent tasks on the user's machine, through the paired bridge (tasks 4.3, 4.4).

The bridge holds the list of repositories the user authorized and, in a worktree per
task, runs the user's own Codex or prepares a handoff the user runs in their own Claude
Code. The API only relays, with the token it keeps encrypted. Every answer is validated
again (schemas.agent_tasks) and redacted: a command line may carry a secret. Tasks live
in the bridge; the API stores only their sandbox checks (`agent_checks`), which the
worker runs.

Interface: repos, start, get, act (cancel / discard / collect), start_check, get_check.
"""

from typing import Any, Literal

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError
from app.queue import JobQueue, QueueUnavailableError
from app.schemas.agent_tasks import (
    AgentCheckOut,
    AgentTaskIn,
    AgentTaskOut,
    LocalRepo,
    LocalReposOut,
    drop_invalid_events,
)
from app.services.identity import RequestContext
from app.services.local_runtimes import (
    START_HINT,
    BridgeClient,
    BridgeRefused,
    BridgeUnauthorized,
    BridgeUnreachable,
    paired_token,
)
from nfactory_core.events.redaction import redact
from nfactory_core.models import AgentCheck
from nfactory_core.secrets import SecretStore

Action = Literal["cancel", "discard", "collect"]
_CHECKABLE = ("succeeded", "no_changes")


async def repos(
    session: AsyncSession, ctx: RequestContext, bridge: BridgeClient, store: SecretStore
) -> LocalReposOut:
    token = await _token(session, ctx, store)
    found = await _relay(bridge.repos(token))
    valid = []
    for item in found:
        try:
            valid.append(LocalRepo.model_validate(item))
        except ValidationError:
            continue  # an id the API would not accept back is not offered
    return LocalReposOut(repos=valid)


async def start(
    session: AsyncSession,
    ctx: RequestContext,
    bridge: BridgeClient,
    store: SecretStore,
    data: AgentTaskIn,
) -> AgentTaskOut:
    token = await _token(session, ctx, store)
    return _task(await _relay(bridge.start_task(token, data.model_dump())))


async def get(
    session: AsyncSession,
    ctx: RequestContext,
    bridge: BridgeClient,
    store: SecretStore,
    task_id: str,
) -> AgentTaskOut:
    token = await _token(session, ctx, store)
    return _task(await _relay(bridge.task(token, task_id)))


async def act(
    session: AsyncSession,
    ctx: RequestContext,
    bridge: BridgeClient,
    store: SecretStore,
    task_id: str,
    action: Action,
) -> AgentTaskOut:
    token = await _token(session, ctx, store)
    return _task(await _relay(bridge.task(token, task_id, action)))


async def start_check(
    session: AsyncSession,
    ctx: RequestContext,
    bridge: BridgeClient,
    store: SecretStore,
    queue: JobQueue,
    task_id: str,
) -> AgentCheckOut:
    """Queue a sandbox test of a finished task's change (the worker reads its files)."""
    task = await get(session, ctx, bridge, store, task_id)
    if task.status not in _CHECKABLE:
        raise AppError(
            409, "task_not_finished", "Attendez la fin de la tâche (ou importez ses changements)."
        )
    check = AgentCheck(
        workspace_id=ctx.default_workspace_id,
        task_id=task.id,
        repo_id=task.repo_id,
        runtime=task.runtime,
    )
    session.add(check)
    await session.commit()
    try:
        await queue.enqueue_agent_check(check.id)
    except QueueUnavailableError as exc:
        check.status, check.error = "error", "File de travail indisponible : relancez le test."
        await session.commit()
        raise AppError(503, "queue_unavailable", "File de travail indisponible.") from exc
    return AgentCheckOut.model_validate(check)


async def get_check(session: AsyncSession, ctx: RequestContext, check_id: str) -> AgentCheckOut:
    check = await session.scalar(
        select(AgentCheck).where(
            AgentCheck.id == check_id, AgentCheck.workspace_id == ctx.default_workspace_id
        )
    )
    if check is None:
        raise AppError(404, "not_found", "Test introuvable.")
    return AgentCheckOut.model_validate(check)


async def _token(session: AsyncSession, ctx: RequestContext, store: SecretStore) -> str:
    token = await paired_token(session, ctx, store)
    if token is None:
        raise AppError(409, "bridge_unpaired", "Associez d'abord le pont local (page Moteurs IA).")
    return token


async def _relay(call: Any) -> Any:
    try:
        return await call
    except BridgeUnreachable as exc:
        raise AppError(503, "bridge_unreachable", START_HINT) from exc
    except BridgeUnauthorized as exc:
        raise AppError(
            409, "bridge_token_rejected", "Le pont ne reconnaît plus NFactory : réassociez-le."
        ) from exc
    except BridgeRefused as exc:
        raise AppError(exc.status, exc.code, str(exc)) from exc


def _scrub(value: Any) -> Any:
    """Redact secret-looking text values. Keys stay: `input_tokens` is a count, not a token."""
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return redact(value) if isinstance(value, str) else value


def _task(raw: dict[str, Any]) -> AgentTaskOut:
    try:
        return AgentTaskOut.model_validate(_scrub(drop_invalid_events(raw)))
    except ValidationError as exc:
        raise AppError(502, "bridge_invalid_answer", "Réponse du pont local inattendue.") from exc
