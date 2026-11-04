"""The knowledge base a run may read: its project's documents and the workspace-wide ones.

The search runs with the workspace's embedder. If that embedder fails, the run still
gets the full-text results and the reason is reported: no other embedder is used.
"""

import logging

from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError

from nfactory_core.config import Settings
from nfactory_core.connections import connection_facts, workspace_connections
from nfactory_core.knowledge import Hit, Scope, search
from nfactory_core.knowledge.engine import (
    EmbeddingUnavailableError,
    check_choice,
    embedding_choice,
    open_embedder,
)
from nfactory_core.models import Document, Workspace
from nfactory_core.providers import ProviderError
from nfactory_core.routing import RoutingConfig
from nfactory_core.secrets import SecretStore
from nfactory_worker.jobs.reporting import Sessions
from nfactory_worker.pipeline import Knowledge, Retrieval

log = logging.getLogger("nfactory.worker.knowledge")
LIMIT = 6


class DatabaseKnowledge:
    def __init__(self, sessions: Sessions, scope: Scope, settings: Settings) -> None:
        self._sessions = sessions
        self._scope = scope
        self._settings = settings

    async def retrieve(self, query: str) -> Retrieval:
        try:
            async with self._sessions() as session:
                workspace = await session.get_one(Workspace, self._scope.workspace_id)
                policy = workspace.data_policy or {}
                choice = embedding_choice(policy)
                try:
                    routing = RoutingConfig.model_validate(policy.get("routing") or {})
                    facts = connection_facts(
                        await workspace_connections(session, self._scope.workspace_id)
                    )
                    check_choice(
                        choice, facts, local_only=routing.local_only, eu_only=routing.eu_only
                    )
                    embedder = await open_embedder(
                        session,
                        self._scope.workspace_id,
                        choice,
                        SecretStore(self._settings.nfactory_secret_key.get_secret_value()),
                        allowed_private_hosts=frozenset(
                            self._settings.nfactory_allowed_private_llm_hosts
                        ),
                    )
                    hits = await search(session, self._scope, query, embedder=embedder, limit=LIMIT)
                    error = None
                except (EmbeddingUnavailableError, ProviderError) as exc:
                    hits = await search(session, self._scope, query, limit=LIMIT)
                    error = f"Recherche sans vecteurs : {exc.message}"
        except SQLAlchemyError:
            log.exception("knowledge search failed for %s", self._scope)
            return Retrieval([], "Base de connaissances indisponible pour ce run.")
        return Retrieval([_passage(hit) for hit in hits], error)


async def knowledge_for(
    sessions: Sessions, workspace_id: str, project_id: str, settings: Settings
) -> Knowledge | None:
    """None when the run can see no document: nothing to search, nothing to report."""
    scope = Scope(workspace_id, project_id)
    async with sessions() as session:
        visible = await session.scalar(
            select(Document.id)
            .where(
                Document.workspace_id == workspace_id,
                or_(Document.project_id == project_id, Document.project_id.is_(None)),
            )
            .limit(1)
        )
    return DatabaseKnowledge(sessions, scope, settings) if visible else None


def _passage(hit: Hit) -> dict[str, object]:
    return {
        "document_id": hit.document_id,
        "path": hit.path,
        "start_line": hit.start_line,
        "end_line": hit.end_line,
        "section": hit.section,
        "content": hit.content,
    }
