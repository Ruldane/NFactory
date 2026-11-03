"""Coding-agent tasks on the user's machine, through the paired bridge (tasks 4.3, 4.4).

The bridge holds the list of repositories the user authorized and, in a worktree per
task, runs the user's own Codex or prepares a handoff the user runs in their own Claude
Code. The API only relays, with the token it keeps encrypted. Every answer is validated
again (schemas.agent_tasks) and redacted: a command line may carry a secret. Tasks live
in the bridge; the API stores only their sandbox checks (`agent_checks`), which the
worker runs.

Publishing (task 4.6) needs the user's approval: the API records it in the audit log,
writes the draft PR's body (changed files, the sandbox verdict, the limits) and relays.

Interface: repos, start, get, act (cancel / discard / collect), start_check, get_check,
publish, publication.
"""

from typing import Any, Literal

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError
from app.queue import JobQueue, QueueUnavailableError
from app.schemas.agent_tasks import (
    AgentCheckOut,
    AgentPublishIn,
    AgentTaskIn,
    AgentTaskOut,
    LocalRepo,
    LocalReposOut,
    Publication,
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
from nfactory_core.models import AgentCheck, AuditLog
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


async def publish(
    session: AsyncSession,
    ctx: RequestContext,
    bridge: BridgeClient,
    store: SecretStore,
    task_id: str,
    data: AgentPublishIn,
) -> Publication:
    """Commit, push the task's branch and open a draft PR, after the user's approval."""
    task = await get(session, ctx, bridge, store, task_id)
    body = _pr_body(task, await _latest_check(session, ctx, task_id))
    token = await _token(session, ctx, store)
    answer = await _relay(
        bridge.publish(token, task_id, {"approve": True, "title": data.title, "body": body})
    )
    result = _publication(answer)
    session.add(
        AuditLog(
            workspace_id=ctx.default_workspace_id,
            actor_id=ctx.user_id,
            action="agent_task.publish",
            target=task_id,
            decision="approved",
            redacted_details={
                "repo": result.repo,
                "branch": task.branch,
                "state": result.state,
                "pr": result.pr.url if result.pr else None,
            },
        )
    )
    await session.commit()
    return result


async def publication(
    session: AsyncSession,
    ctx: RequestContext,
    bridge: BridgeClient,
    store: SecretStore,
    task_id: str,
) -> Publication:
    token = await _token(session, ctx, store)
    return _publication(await _relay(bridge.publication(token, task_id)))


async def _latest_check(
    session: AsyncSession, ctx: RequestContext, task_id: str
) -> AgentCheck | None:
    return await session.scalar(
        select(AgentCheck)
        .where(AgentCheck.task_id == task_id, AgentCheck.workspace_id == ctx.default_workspace_id)
        .order_by(AgentCheck.created_at.desc())
        .limit(1)
    )


_CHANGE_FR = {"added": "ajouté", "modified": "modifié", "deleted": "supprimé"}


def _pr_body(task: AgentTaskOut, check: AgentCheck | None) -> str:
    agent = "Codex (piloté par NFactory)" if task.runtime == "codex" else "Claude Code (relais)"
    files = "\n".join(f"- `{m.path}` ({_CHANGE_FR[m.change]})" for m in task.manifest[:200])
    if check is None or check.report is None:
        tests = "Non testé dans le sandbox de NFactory."
    else:
        r = check.report
        tests = (
            f"Sandbox NFactory ({check.status}) : {r.get('passed', 0)} réussis, "
            f"{int(r.get('failed', 0)) + int(r.get('errors', 0))} en échec "
            "(rapport JUnit, pas l'avis de l'agent)."
        )
    return (
        "PR **brouillon** préparée par NFactory, publiée après approbation de l'utilisateur.\n\n"
        f"**Agent :** {agent}\n**Branche :** `{task.branch}` (base `{task.base[:12]}`)\n\n"
        f"### Fichiers changés\n{files or '- aucun'}\n\n### Tests\n{tests}\n\n"
        "### Limites\n- Les dépendances du dépôt ne sont pas installées dans le sandbox.\n"
        "- Aucun merge automatique : la revue et la fusion restent humaines.\n"
    )


def _publication(raw: dict[str, Any]) -> Publication:
    try:
        return Publication.model_validate(raw)
    except ValidationError as exc:
        raise AppError(502, "bridge_invalid_answer", "Réponse du pont local inattendue.") from exc


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
