"""NFactory database schema (spec §10.1), one module per domain.

Importing this package registers every table on `Base.metadata` (used by Alembic).
"""

from nfactory_core.models.agents import AgentCheck
from nfactory_core.models.artifacts import Artifact
from nfactory_core.models.audit import AuditLog
from nfactory_core.models.base import Base
from nfactory_core.models.evaluations import EvaluationCase, EvaluationResult, EvaluationSuite
from nfactory_core.models.github import GithubLink
from nfactory_core.models.identity import Membership, User, Workspace
from nfactory_core.models.knowledge import Document, DocumentChunk
from nfactory_core.models.projects import Project
from nfactory_core.models.providers import ModelCatalogEntry, ProviderConnection, StoredSecret
from nfactory_core.models.runs import Approval, EventRecord, Run, RunStep
from nfactory_core.models.templates import TemplateVersion

__all__ = [
    "AgentCheck",
    "Approval",
    "Artifact",
    "AuditLog",
    "Base",
    "Document",
    "DocumentChunk",
    "EvaluationCase",
    "EvaluationResult",
    "EvaluationSuite",
    "EventRecord",
    "GithubLink",
    "Membership",
    "ModelCatalogEntry",
    "Project",
    "ProviderConnection",
    "Run",
    "RunStep",
    "StoredSecret",
    "TemplateVersion",
    "User",
    "Workspace",
]
