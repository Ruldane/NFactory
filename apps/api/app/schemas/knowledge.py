"""Knowledge base contracts (tasks 3.2 to 3.6)."""

from datetime import datetime

from pydantic import BaseModel

from nfactory_core.knowledge.engine import EmbeddingChoice


class DocumentOut(BaseModel):
    id: str
    path: str
    project_id: str | None
    kind: str | None
    size_bytes: int | None
    revision: str | None
    chunks: int
    embedded: int
    created_at: datetime


class UploadOut(DocumentOut):
    duplicate: bool
    replaced: bool


class DocumentList(BaseModel):
    items: list[DocumentOut]


class DocumentDetail(DocumentOut):
    content: str


class HitOut(BaseModel):
    chunk_id: str
    document_id: str
    path: str
    content: str
    start_line: int
    end_line: int
    section: str | None
    symbol: str | None
    page: int | None
    score: float
    matched: list[str]


class EngineUse(BaseModel):
    """The embedder the search used, or why it could not (text search still ran)."""

    key: str
    used: bool
    error: str | None = None


class SearchOut(BaseModel):
    hits: list[HitOut]
    engine: EngineUse


class EngineOption(BaseModel):
    provider: str
    label: str
    local: bool
    available: bool
    reason: str | None = None


class IndexOut(BaseModel):
    total: int
    embedded: int


class KnowledgeSettingsIn(BaseModel):
    embedding: EmbeddingChoice


class KnowledgeSettingsOut(BaseModel):
    embedding: EmbeddingChoice
    index: IndexOut
    options: list[EngineOption]
    # Why the worker's last indexing pass stopped; None when it went through.
    index_error: str | None = None
