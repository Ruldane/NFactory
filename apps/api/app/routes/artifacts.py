from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.context import AppSettings, Context, Session
from app.services import run_outputs

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


@router.get("/{artifact_id}/download")
async def download_artifact(
    session: Session, ctx: Context, settings: AppSettings, artifact_id: str
) -> FileResponse:
    artifact, path = await run_outputs.artifact_file(
        session, ctx, Path(settings.artifact_root), artifact_id
    )
    return FileResponse(
        path,
        media_type=artifact.mime,
        filename=artifact.filename,
        headers={"X-Checksum": artifact.checksum},
    )
