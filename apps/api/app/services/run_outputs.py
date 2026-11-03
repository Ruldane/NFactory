"""What a run produced: workspace files (read-only) and stored artifacts.

Paths come from users and from generated content, so both are confined: workspace
paths go through Workspace.resolve, artifact keys must stay under the artifact root.
"""

import asyncio
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError, not_found
from app.schemas.runs import ArtifactOut, FileContent, FileList
from app.services.identity import RequestContext
from app.services.runs import owned_run
from nfactory_core.models import Artifact, Project
from nfactory_core.workspace import UnsafePathError, Workspace

MAX_PREVIEW_BYTES = 1_000_000


async def list_files(
    session: AsyncSession, ctx: RequestContext, workspace_root: Path, run_id: str
) -> FileList:
    run = await owned_run(session, ctx, run_id)
    return FileList(files=await asyncio.to_thread(_workspace_files, workspace_root, run.id))


def _workspace_files(workspace_root: Path, run_id: str) -> list[str]:
    workspace = Workspace.open(workspace_root, run_id)
    return workspace.files() if workspace else []


async def read_file(
    session: AsyncSession, ctx: RequestContext, workspace_root: Path, run_id: str, path: str
) -> FileContent:
    run = await owned_run(session, ctx, run_id)
    return await asyncio.to_thread(_read_workspace_file, workspace_root, run.id, path)


def _read_workspace_file(workspace_root: Path, run_id: str, path: str) -> FileContent:
    workspace = Workspace.open(workspace_root, run_id)
    if workspace is None:
        raise not_found("Fichier")
    try:
        target = workspace.resolve(path)
    except UnsafePathError:
        raise AppError(400, "invalid_path", "Chemin de fichier invalide.") from None
    if not target.is_file():
        raise not_found("Fichier")
    size = target.stat().st_size
    if size > MAX_PREVIEW_BYTES:
        raise AppError(413, "file_too_large", "Fichier trop volumineux pour l'aperçu.")
    text = _as_text(target.read_bytes())
    return FileContent(path=path, content=text, binary=text is None, size=size)


async def list_artifacts(
    session: AsyncSession, ctx: RequestContext, run_id: str
) -> list[ArtifactOut]:
    run = await owned_run(session, ctx, run_id)
    rows = await session.scalars(
        select(Artifact).where(Artifact.run_id == run.id).order_by(Artifact.created_at)
    )
    return [_artifact_out(row) for row in rows]


async def artifact_file(
    session: AsyncSession, ctx: RequestContext, artifact_root: Path, artifact_id: str
) -> tuple[Artifact, Path]:
    artifact = await session.scalar(
        select(Artifact)
        .join(Project, Project.id == Artifact.project_id)
        .where(Artifact.id == artifact_id, Project.workspace_id.in_(ctx.workspace_ids))
    )
    if artifact is None:
        raise not_found("Artefact")
    path = await asyncio.to_thread(_stored_file, artifact_root, artifact.storage_key)
    if path is None:
        raise not_found("Fichier de l'artefact")
    return artifact, path


def _stored_file(artifact_root: Path, storage_key: str) -> Path | None:
    root = artifact_root.resolve()
    path = (root / storage_key).resolve()
    return path if path.is_relative_to(root) and path.is_file() else None


# Control bytes that never appear in text files (tab, newlines and form feed excluded).
_BINARY_BYTES = frozenset({*range(0, 9), 11, *range(14, 32)})


def _as_text(data: bytes) -> str | None:
    if any(byte in _BINARY_BYTES for byte in data[:8192]):
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _artifact_out(row: Artifact) -> ArtifactOut:
    return ArtifactOut(
        id=row.id,
        filename=row.filename,
        mime=row.mime,
        size=row.size,
        checksum=row.checksum,
        created_at=row.created_at,
        download_url=f"/api/v1/artifacts/{row.id}/download",
    )
