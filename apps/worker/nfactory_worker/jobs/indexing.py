"""Background indexing (ADR-0007): compute the missing vectors of a workspace.

Runs as the `index_knowledge` job after an upload or an engine change, and every
minute as a catch-up. A failing embedder stops the pass and its reason is stored in
`data_policy["knowledge"]["index_error"]` for the UI: no other embedder takes over.
"""

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nfactory_core.config import Settings
from nfactory_core.connections import connection_facts, workspace_connections
from nfactory_core.knowledge import index_batch
from nfactory_core.knowledge.engine import (
    POLICY_KEY,
    EmbeddingUnavailableError,
    check_choice,
    embedding_choice,
    open_embedder,
)
from nfactory_core.models import Document, DocumentChunk, Workspace
from nfactory_core.providers import ProviderError
from nfactory_core.routing import RoutingConfig
from nfactory_core.secrets import SecretStore

log = logging.getLogger("nfactory.worker.indexing")
Sessions = async_sessionmaker[AsyncSession]


@dataclass(frozen=True)
class IndexReport:
    embedded: int
    error: str | None = None


async def index_workspace(sessions: Sessions, workspace_id: str, settings: Settings) -> IndexReport:
    embedded = 0
    async with sessions() as session:
        workspace = await session.get_one(Workspace, workspace_id)
        choice = embedding_choice(workspace.data_policy)
        try:
            policy = workspace.data_policy or {}
            routing = RoutingConfig.model_validate(policy.get("routing") or {})
            facts = connection_facts(await workspace_connections(session, workspace_id))
            check_choice(choice, facts, local_only=routing.local_only)
            embedder = await open_embedder(
                session,
                workspace_id,
                choice,
                SecretStore(settings.nfactory_secret_key.get_secret_value()),
                allowed_private_hosts=frozenset(settings.nfactory_allowed_private_llm_hosts),
            )
            while done := await index_batch(session, workspace_id, embedder):
                embedded += done
                await session.commit()  # progress survives a later failure
        except (EmbeddingUnavailableError, ProviderError) as exc:
            await session.rollback()
            log.warning("indexing stopped for %s: %s", workspace_id, exc.message)
            await _record_error(session, workspace_id, exc.message)
            return IndexReport(embedded, exc.message)
        await _record_error(session, workspace_id, None)
    return IndexReport(embedded)


async def index_pending_workspaces(sessions: Sessions, settings: Settings) -> list[str]:
    """The catch-up pass: index every workspace that has chunks without a current vector."""
    async with sessions() as session:
        workspaces = (
            await session.scalars(
                select(Workspace).where(exists().where(Document.workspace_id == Workspace.id))
            )
        ).all()
        pending = [w.id for w in workspaces if await _has_pending(session, w)]
    for workspace_id in pending:
        await index_workspace(sessions, workspace_id, settings)
    return pending


async def _has_pending(session: AsyncSession, workspace: Workspace) -> bool:
    key = embedding_choice(workspace.data_policy).key
    found = await session.scalar(
        select(DocumentChunk.id)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            Document.workspace_id == workspace.id,
            DocumentChunk.embedding_model.is_distinct_from(key),
        )
        .limit(1)
    )
    return found is not None


async def _record_error(session: AsyncSession, workspace_id: str, message: str | None) -> None:
    workspace = await session.get_one(Workspace, workspace_id)
    policy: dict[str, Any] = dict(workspace.data_policy or {})
    knowledge = dict(policy.get(POLICY_KEY) or {})
    if knowledge.get("index_error") == message:
        return
    if message is None:
        knowledge.pop("index_error", None)
    else:
        knowledge["index_error"] = message
    policy[POLICY_KEY] = knowledge
    workspace.data_policy = policy
    await session.commit()
