"""Coding-agent tasks on the user's machine, relayed to the paired bridge (tasks 4.3, 4.4)."""

from typing import Annotated

from fastapi import APIRouter, Path

from app.context import Bridge, Context, Providers, Queue, Session
from app.schemas.agent_tasks import (
    TASK_ID,
    AgentCheckOut,
    AgentPublishIn,
    AgentTaskIn,
    AgentTaskOut,
    LocalReposOut,
    Publication,
)
from app.services import agent_tasks

router = APIRouter(prefix="/local-runtimes", tags=["local-runtimes"])
TaskId = Annotated[str, Path(pattern=TASK_ID)]
CheckId = Annotated[str, Path(pattern=r"^agc_[A-Za-z0-9]{1,28}$")]


@router.get("/repos")
async def list_repos(
    session: Session, ctx: Context, bridge: Bridge, deps: Providers
) -> LocalReposOut:
    """Repositories the user authorized on the bridge (`bridge.ps1 -Allow <folder>`)."""
    return await agent_tasks.repos(session, ctx, bridge, deps.store)


@router.post("/tasks", status_code=202)
async def start_task(
    data: AgentTaskIn, session: Session, ctx: Context, bridge: Bridge, deps: Providers
) -> AgentTaskOut:
    """With the user's explicit consent: run their Codex on an authorized repository, or
    prepare a handoff (`runtime: "claude"`) they run in their own Claude Code."""
    return await agent_tasks.start(session, ctx, bridge, deps.store, data)


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: TaskId, session: Session, ctx: Context, bridge: Bridge, deps: Providers
) -> AgentTaskOut:
    return await agent_tasks.get(session, ctx, bridge, deps.store, task_id)


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: TaskId, session: Session, ctx: Context, bridge: Bridge, deps: Providers
) -> AgentTaskOut:
    return await agent_tasks.act(session, ctx, bridge, deps.store, task_id, "cancel")


@router.post("/tasks/{task_id}/discard")
async def discard_task(
    task_id: TaskId, session: Session, ctx: Context, bridge: Bridge, deps: Providers
) -> AgentTaskOut:
    """Remove the task's worktree and branch on the user's machine."""
    return await agent_tasks.act(session, ctx, bridge, deps.store, task_id, "discard")


@router.post("/tasks/{task_id}/collect")
async def collect_task(
    task_id: TaskId, session: Session, ctx: Context, bridge: Bridge, deps: Providers
) -> AgentTaskOut:
    """Import what the user's Claude Code changed in a handoff's worktree."""
    return await agent_tasks.act(session, ctx, bridge, deps.store, task_id, "collect")


@router.post("/tasks/{task_id}/checks", status_code=202)
async def check_task(
    task_id: TaskId,
    session: Session,
    ctx: Context,
    bridge: Bridge,
    deps: Providers,
    queue: Queue,
) -> AgentCheckOut:
    """Test a finished task's change in the sandbox (never on the user's machine)."""
    return await agent_tasks.start_check(session, ctx, bridge, deps.store, queue, task_id)


@router.get("/checks/{check_id}")
async def get_check(check_id: CheckId, session: Session, ctx: Context) -> AgentCheckOut:
    return await agent_tasks.get_check(session, ctx, check_id)


@router.post("/tasks/{task_id}/publish")
async def publish_task(
    task_id: TaskId,
    data: AgentPublishIn,
    session: Session,
    ctx: Context,
    bridge: Bridge,
    deps: Providers,
) -> Publication:
    """After the user's approval: local commit, push of the task's branch, draft PR."""
    return await agent_tasks.publish(session, ctx, bridge, deps.store, task_id, data)


@router.get("/tasks/{task_id}/publication")
async def get_publication(
    task_id: TaskId, session: Session, ctx: Context, bridge: Bridge, deps: Providers
) -> Publication:
    """Each publication fact, verified again on GitHub."""
    return await agent_tasks.publication(session, ctx, bridge, deps.store, task_id)
