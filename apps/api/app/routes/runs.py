from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Header, Query, Request, Response, status
from sse_starlette import EventSourceResponse

from app.context import AppSettings, Context, Previews, Queue, RunWakeups, Session, Sessions
from app.schemas.common import Items
from app.schemas.runs import (
    ApprovalDecision,
    ArtifactOut,
    FileContent,
    FileList,
    PreviewOut,
    RunCreate,
    RunDetail,
)
from app.services import previews, run_approvals, run_outputs, runs
from app.services.run_events import parse_last_event_id, stream_run

router = APIRouter(tags=["runs"])


@router.post("/projects/{project_id}/runs", status_code=status.HTTP_201_CREATED)
async def launch_run(
    sessions: Sessions,
    ctx: Context,
    settings: AppSettings,
    queue: Queue,
    project_id: str,
    data: RunCreate,
    response: Response,
    idempotency_key: Annotated[str | None, Header()] = None,
) -> RunDetail:
    launched = await runs.launch_run(
        sessions, ctx, settings, queue, project_id, data, idempotency_key
    )
    if not launched.created:
        response.status_code = status.HTTP_200_OK
    return launched.run


@router.get("/runs/{run_id}")
async def get_run(session: Session, ctx: Context, run_id: str) -> RunDetail:
    return await runs.get_run(session, ctx, run_id)


@router.post("/runs/{run_id}/cancel")
async def cancel_run(sessions: Sessions, ctx: Context, run_id: str) -> RunDetail:
    return await runs.cancel_run(sessions, ctx, run_id)


@router.post("/runs/{run_id}/approvals/{approval_id}/approve")
async def approve(
    sessions: Sessions,
    ctx: Context,
    queue: Queue,
    run_id: str,
    approval_id: str,
    decision: ApprovalDecision,
) -> RunDetail:
    """Resume a paused run, on the same engine or on the replacement chosen."""
    return await run_approvals.approve(sessions, ctx, queue, run_id, approval_id, decision)


@router.post("/runs/{run_id}/approvals/{approval_id}/reject")
async def reject(sessions: Sessions, ctx: Context, run_id: str, approval_id: str) -> RunDetail:
    return await run_approvals.reject(sessions, ctx, run_id, approval_id)


@router.get("/runs/{run_id}/events")
async def stream_events(
    request: Request,
    session: Session,
    sessions: Sessions,
    wakeups: RunWakeups,
    ctx: Context,
    run_id: str,
    last_event_id: Annotated[str | None, Header()] = None,
    after: Annotated[int | None, Query(ge=0)] = None,
) -> EventSourceResponse:
    await runs.owned_run(session, ctx, run_id)  # 404 before the stream opens
    start = after if after is not None else parse_last_event_id(last_event_id)
    return EventSourceResponse(
        stream_run(sessions, wakeups, run_id, start, request.is_disconnected), ping=15
    )


@router.get("/runs/{run_id}/files")
async def list_files(
    session: Session, ctx: Context, settings: AppSettings, run_id: str
) -> FileList:
    return await run_outputs.list_files(session, ctx, Path(settings.workspace_root), run_id)


@router.get("/runs/{run_id}/files/content")
async def read_file(
    session: Session,
    ctx: Context,
    settings: AppSettings,
    run_id: str,
    path: Annotated[str, Query(max_length=500)],
) -> FileContent:
    return await run_outputs.read_file(session, ctx, Path(settings.workspace_root), run_id, path)


@router.get("/runs/{run_id}/artifacts")
async def list_artifacts(session: Session, ctx: Context, run_id: str) -> Items[ArtifactOut]:
    return Items(items=await run_outputs.list_artifacts(session, ctx, run_id))


@router.post("/runs/{run_id}/preview")
async def start_preview(
    session: Session, ctx: Context, settings: AppSettings, control: Previews, run_id: str
) -> PreviewOut:
    public = settings.nfactory_preview_public_url
    return await previews.start_preview(session, ctx, control, public, run_id)


@router.get("/runs/{run_id}/preview")
async def preview_status(
    session: Session, ctx: Context, settings: AppSettings, control: Previews, run_id: str
) -> PreviewOut:
    public = settings.nfactory_preview_public_url
    return await previews.preview_status(session, ctx, control, public, run_id)


@router.delete("/runs/{run_id}/preview", status_code=status.HTTP_204_NO_CONTENT)
async def stop_preview(session: Session, ctx: Context, control: Previews, run_id: str) -> None:
    await previews.stop_preview(session, ctx, control, run_id)
