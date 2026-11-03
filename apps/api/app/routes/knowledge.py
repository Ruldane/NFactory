"""Knowledge base: documents the agents may cite, and the search over them."""

from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Response, UploadFile

from app.context import Context, Providers, Queue, Session
from app.errors import AppError
from app.schemas.knowledge import (
    DocumentDetail,
    DocumentList,
    KnowledgeSettingsIn,
    KnowledgeSettingsOut,
    SearchOut,
    UploadOut,
)
from app.services import knowledge
from nfactory_core.knowledge.extract import MAX_BYTES

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/documents", status_code=201)
async def upload_document(
    response: Response,
    session: Session,
    ctx: Context,
    queue: Queue,
    file: Annotated[UploadFile, File()],
    project_id: Annotated[str | None, Form()] = None,
) -> UploadOut:
    """Text search works at once; vectors are computed by the worker afterwards."""
    data = await file.read(MAX_BYTES + 1)  # one byte more than allowed: enough to refuse
    if len(data) > MAX_BYTES:
        raise AppError(413, "file_too_large", "Fichier trop volumineux (10 Mo au maximum).")
    result = await knowledge.upload(
        session, ctx, queue, filename=file.filename or "document", data=data, project_id=project_id
    )
    if result.duplicate:
        response.status_code = 200
    return result


@router.get("/documents")
async def list_documents(
    session: Session, ctx: Context, project_id: str | None = None
) -> DocumentList:
    return await knowledge.list_documents(session, ctx, project_id)


@router.get("/documents/{document_id}")
async def get_document(document_id: str, session: Session, ctx: Context) -> DocumentDetail:
    return await knowledge.get_document(session, ctx, document_id)


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(document_id: str, session: Session, ctx: Context) -> Response:
    await knowledge.delete_document(session, ctx, document_id)
    return Response(status_code=204)


@router.get("/search")
async def search_knowledge(
    session: Session,
    ctx: Context,
    deps: Providers,
    q: Annotated[str, Query(min_length=1, max_length=500)],
    project_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=20)] = 8,
) -> SearchOut:
    return await knowledge.search_knowledge(
        session, ctx, deps, query=q, project_id=project_id, limit=limit
    )


@router.get("/settings")
async def get_settings(session: Session, ctx: Context) -> KnowledgeSettingsOut:
    return await knowledge.settings_view(session, ctx)


@router.put("/settings")
async def put_settings(
    body: KnowledgeSettingsIn, session: Session, ctx: Context, queue: Queue
) -> KnowledgeSettingsOut:
    """A new embedding engine re-indexes every document; the old vectors are not used."""
    return await knowledge.save_settings(session, ctx, queue, body.embedding)
