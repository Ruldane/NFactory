"""What the pipeline needs from the outside world. The worker job provides database
adapters; tests use the in-memory ones from pipeline.memory."""

from dataclasses import dataclass, field
from typing import Any, Protocol

from nfactory_worker.artifacts import StoredArtifact


class Reporter(Protocol):
    async def step_started(self, step: str) -> None: ...

    async def step_succeeded(self, step: str, output: dict[str, Any]) -> None: ...

    async def step_failed(
        self, step: str, error: str, output: dict[str, Any] | None = None
    ) -> None: ...

    async def step_skipped(self, step: str, reason: str) -> None: ...

    async def emit(self, type: str, payload: dict[str, Any], step: str | None = None) -> None: ...

    async def artifact_saved(self, artifact: StoredArtifact) -> None: ...


@dataclass(frozen=True)
class Retrieval:
    """Passages found for a run. Each passage: document_id, path, start_line, end_line,
    section, content. `error` says why the search fell short; the run goes on anyway."""

    passages: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


class Knowledge(Protocol):
    """The project's knowledge base, already restricted to what the run may see."""

    async def retrieve(self, query: str) -> Retrieval: ...


class RunControl(Protocol):
    async def cancel_requested(self) -> bool: ...
