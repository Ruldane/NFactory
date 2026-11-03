"""In-memory Reporter and RunControl, for tests and local experiments."""

from collections import Counter
from typing import Any

from nfactory_worker.artifacts import StoredArtifact
from nfactory_worker.pipeline.ports import Retrieval


class MemoryKnowledge:
    """Returns the same passages for every query, and records the queries."""

    def __init__(self, passages: list[dict[str, Any]], error: str | None = None) -> None:
        self._passages = passages
        self._error = error
        self.queries: list[str] = []

    async def retrieve(self, query: str) -> Retrieval:
        self.queries.append(query)
        return Retrieval(list(self._passages), self._error)


class MemoryReporter:
    def __init__(self) -> None:
        self.started: list[str] = []
        self.attempts: Counter[str] = Counter()
        self.succeeded: list[str] = []
        self.failed: dict[str, str] = {}
        self.failed_outputs: dict[str, dict[str, Any]] = {}
        self.skipped: dict[str, str] = {}
        self.outputs: dict[str, dict[str, Any]] = {}
        self.events: list[tuple[str, dict[str, Any], str | None]] = []
        self.artifacts: list[StoredArtifact] = []

    async def step_started(self, step: str) -> None:
        self.started.append(step)
        self.attempts[step] += 1

    async def step_succeeded(self, step: str, output: dict[str, Any]) -> None:
        self.succeeded.append(step)
        self.outputs[step] = output

    async def step_failed(
        self, step: str, error: str, output: dict[str, Any] | None = None
    ) -> None:
        self.failed[step] = error
        if output:
            self.failed_outputs[step] = output

    async def step_skipped(self, step: str, reason: str) -> None:
        self.skipped[step] = reason

    async def emit(self, type: str, payload: dict[str, Any], step: str | None = None) -> None:
        self.events.append((type, payload, step))

    async def artifact_saved(self, artifact: StoredArtifact) -> None:
        self.artifacts.append(artifact)

    def finished_steps(self) -> list[str]:
        return list(dict.fromkeys(self.succeeded))


class MemoryControl:
    def __init__(self, reporter: MemoryReporter) -> None:
        self._reporter = reporter
        self._after: str | None = None

    def cancel_after(self, step: str) -> None:
        self._after = step

    async def cancel_requested(self) -> bool:
        return self._after is not None and self._after in self._reporter.succeeded
