"""Knowledge base use cases (tasks 3.2 to 3.4): upload, documents, search, engine choice."""

import logging

from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError, not_found
from app.queue import JobQueue, QueueUnavailableError
from app.schemas.knowledge import (
    DocumentDetail,
    DocumentList,
    DocumentOut,
    EngineOption,
    EngineUse,
    HitOut,
    IndexOut,
    KnowledgeSettingsOut,
    SearchOut,
    UploadOut,
)
from app.services.identity import RequestContext
from app.services.providers import ProviderDeps
from app.services.routing import routing_config
from nfactory_core.connections import connection_facts, workspace_connections
from nfactory_core.knowledge import ExtractionError, Scope, index_status, ingest, search
from nfactory_core.knowledge.embedders import LOCAL_PROVIDER, Embedder
from nfactory_core.knowledge.engine import (
    POLICY_KEY,
    EmbeddingChoice,
    EmbeddingUnavailableError,
    check_choice,
    embedding_choice,
    open_embedder,
)
from nfactory_core.models import Document, DocumentChunk, Project, Workspace
from nfactory_core.providers import SPECS, ProviderError

logger = logging.getLogger(__name__)

_EXTRACTION_STATUS = {"file_too_large": 413, "unsupported_file_type": 415}
_ENGINE_STATUS = {"embeddings_unsupported": 422}


async def upload(
    session: AsyncSession,
    ctx: RequestContext,
    queue: JobQueue,
    *,
    filename: str,
    data: bytes,
    project_id: str | None,
) -> UploadOut:
    scope = await _scope(session, ctx, project_id)
    try:
        result = await ingest(session, scope, filename, data)
    except ExtractionError as exc:
        raise AppError(_EXTRACTION_STATUS.get(exc.code, 422), exc.code, exc.message) from None
    await session.commit()
    if not result.duplicate:
        await _queue_indexing(queue, scope.workspace_id)
    view = await _document_out(session, ctx, result.document.id)
    return UploadOut(**view.model_dump(), duplicate=result.duplicate, replaced=result.replaced)


async def list_documents(
    session: AsyncSession, ctx: RequestContext, project_id: str | None
) -> DocumentList:
    query = _documents(await _active_key(session, ctx))
    if project_id:
        query = query.where(Document.project_id == project_id)
    rows = (await session.execute(query.where(Document.workspace_id.in_(ctx.workspace_ids)))).all()
    return DocumentList(items=[_out(doc, chunks, embedded) for doc, chunks, embedded in rows])


async def get_document(
    session: AsyncSession, ctx: RequestContext, document_id: str
) -> DocumentDetail:
    view = await _document_out(session, ctx, document_id)
    content = await session.scalar(select(Document.content).where(Document.id == document_id))
    return DocumentDetail(**view.model_dump(), content=content or "")


async def delete_document(session: AsyncSession, ctx: RequestContext, document_id: str) -> None:
    await _document_out(session, ctx, document_id)  # 404 outside the workspace
    await session.execute(delete(Document).where(Document.id == document_id))
    await session.commit()


async def search_knowledge(
    session: AsyncSession,
    ctx: RequestContext,
    deps: ProviderDeps,
    *,
    query: str,
    project_id: str | None,
    limit: int,
) -> SearchOut:
    scope = await _scope(session, ctx, project_id)
    choice = await _choice(session, ctx)
    try:
        embedder = await _embedder(session, ctx, deps, choice)
        hits = await search(session, scope, query, embedder=embedder, limit=limit)
        engine = EngineUse(key=choice.key, used=True)
    except (EmbeddingUnavailableError, ProviderError) as exc:
        # Reported, never replaced by another embedder: the text search still answers.
        hits = await search(session, scope, query, limit=limit)
        engine = EngineUse(key=choice.key, used=False, error=exc.message)
    return SearchOut(
        hits=[HitOut(**{**hit.__dict__, "matched": list(hit.matched)}) for hit in hits],
        engine=engine,
    )


async def settings_view(session: AsyncSession, ctx: RequestContext) -> KnowledgeSettingsOut:
    workspace = await session.get_one(Workspace, ctx.default_workspace_id)
    choice = embedding_choice(workspace.data_policy)
    index_error = ((workspace.data_policy or {}).get(POLICY_KEY) or {}).get("index_error")
    status = await index_status(session, ctx.default_workspace_id, choice.key)
    facts = connection_facts(await workspace_connections(session, ctx.default_workspace_id))
    local_only = (await routing_config(session, ctx.default_workspace_id)).local_only
    options = [
        EngineOption(
            provider=LOCAL_PROVIDER,
            label="Empreinte locale (sans modèle)",
            local=True,
            available=True,
        )
    ]
    for kind, spec in SPECS.items():
        if not spec.embeddings:
            continue
        reason = None
        try:
            check_choice(
                EmbeddingChoice(provider=kind, model="probe"), facts, local_only=local_only
            )
        except EmbeddingUnavailableError as exc:
            reason = exc.message
        options.append(
            EngineOption(
                provider=kind,
                label=spec.label,
                local=spec.local,
                available=reason is None,
                reason=reason,
            )
        )
    return KnowledgeSettingsOut(
        embedding=choice,
        index=IndexOut(total=status.total, embedded=status.embedded),
        options=options,
        index_error=index_error,
    )


async def save_settings(
    session: AsyncSession, ctx: RequestContext, queue: JobQueue, choice: EmbeddingChoice
) -> KnowledgeSettingsOut:
    await _check(session, ctx, choice)
    workspace = await session.get_one(Workspace, ctx.default_workspace_id)
    policy = dict(workspace.data_policy or {})
    policy[POLICY_KEY] = {**(policy.get(POLICY_KEY) or {}), "embedding": choice.model_dump()}
    workspace.data_policy = policy
    await session.commit()
    await _queue_indexing(queue, ctx.default_workspace_id)  # a new engine re-indexes
    return await settings_view(session, ctx)


# --- helpers ---------------------------------------------------------------------------


async def _scope(session: AsyncSession, ctx: RequestContext, project_id: str | None) -> Scope:
    if project_id:
        owned = await session.scalar(
            select(Project.id).where(
                Project.id == project_id, Project.workspace_id.in_(ctx.workspace_ids)
            )
        )
        if owned is None:
            raise not_found("Projet")
    return Scope(ctx.default_workspace_id, project_id or None)


async def _choice(session: AsyncSession, ctx: RequestContext) -> EmbeddingChoice:
    workspace = await session.get_one(Workspace, ctx.default_workspace_id)
    return embedding_choice(workspace.data_policy)


async def _active_key(session: AsyncSession, ctx: RequestContext) -> str:
    return (await _choice(session, ctx)).key


async def _check(session: AsyncSession, ctx: RequestContext, choice: EmbeddingChoice) -> None:
    facts = connection_facts(await workspace_connections(session, ctx.default_workspace_id))
    local_only = (await routing_config(session, ctx.default_workspace_id)).local_only
    try:
        check_choice(choice, facts, local_only=local_only)
    except EmbeddingUnavailableError as exc:
        raise AppError(_ENGINE_STATUS.get(exc.code, 409), exc.code, exc.message) from None


async def _embedder(
    session: AsyncSession, ctx: RequestContext, deps: ProviderDeps, choice: EmbeddingChoice
) -> Embedder:
    facts = connection_facts(await workspace_connections(session, ctx.default_workspace_id))
    local_only = (await routing_config(session, ctx.default_workspace_id)).local_only
    check_choice(choice, facts, local_only=local_only)
    return await open_embedder(
        session,
        ctx.default_workspace_id,
        choice,
        deps.store,
        resolver=deps.resolver,
        allowed_private_hosts=deps.allowed_private_hosts,
    )


async def _queue_indexing(queue: JobQueue, workspace_id: str) -> None:
    try:
        await queue.enqueue_indexing(workspace_id)
    except QueueUnavailableError:
        # Not fatal: the worker also indexes pending chunks every minute.
        logger.warning("indexing not queued for %s: queue unavailable", workspace_id)


def _documents(key: str) -> Select[Document, int, int]:
    return (
        select(
            Document,
            func.count(DocumentChunk.id),
            func.count(DocumentChunk.id).filter(DocumentChunk.embedding_model == key),
        )
        .outerjoin(DocumentChunk, DocumentChunk.document_id == Document.id)
        .group_by(Document.id)
        .order_by(Document.created_at.desc(), Document.id)
    )


async def _document_out(
    session: AsyncSession, ctx: RequestContext, document_id: str
) -> DocumentOut:
    row = (
        await session.execute(
            _documents(await _active_key(session, ctx)).where(
                Document.id == document_id, Document.workspace_id.in_(ctx.workspace_ids)
            )
        )
    ).first()
    if row is None:
        raise not_found("Document")
    document, chunks, embedded = row
    return _out(document, chunks, embedded)


def _out(document: Document, chunks: int, embedded: int) -> DocumentOut:
    return DocumentOut(
        id=document.id,
        path=document.path,
        project_id=document.project_id,
        kind=document.kind,
        size_bytes=document.size_bytes,
        revision=document.revision,
        chunks=int(chunks),
        embedded=int(embedded),
        created_at=document.created_at,
    )
