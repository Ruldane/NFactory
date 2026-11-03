"""The two engine families (spec §6.1). They are deliberately separate interfaces:
a coding-agent runtime works inside a repository and is not a chat completion.
"""

from collections.abc import AsyncIterator, Sequence
from typing import Any, Protocol

from nfactory_core.providers.types import (
    Completion,
    ConnectionReport,
    Message,
    ModelInfo,
    ProviderCapabilities,
    StreamChunk,
    ToolSpec,
)


class ModelProvider(Protocol):
    """Family A: prompt in, text out. Every failure raises `ProviderError`.

    `json_schema` asks for a JSON reply: enforced where the provider supports schemas,
    JSON mode otherwise; callers still validate the reply.
    """

    async def check_connection(self, probe_model: str | None = None) -> ConnectionReport:
        """Without discovery, `probe_model` (from the catalog) is called with one token."""
        ...

    async def list_models(self) -> list[ModelInfo]: ...

    async def capabilities(self, model: str) -> ProviderCapabilities: ...

    async def complete(
        self,
        model: str,
        messages: list[Message],
        *,
        json_schema: dict[str, Any] | None = None,
        tools: Sequence[ToolSpec] = (),
        max_tokens: int | None = None,
    ) -> Completion: ...

    def stream(
        self,
        model: str,
        messages: list[Message],
        *,
        max_tokens: int | None = None,
    ) -> AsyncIterator[StreamChunk]: ...


class CodingAgentRuntime(Protocol):
    """Family B: an agent that edits a workspace (Codex CLI, Claude Code). Phase 4."""

    async def detect(self) -> dict[str, Any]: ...

    async def status(self) -> dict[str, Any]: ...

    async def start_task(
        self, workspace: str, task: dict[str, Any], permissions: dict[str, Any]
    ) -> str: ...

    def stream_events(self, session_id: str) -> AsyncIterator[dict[str, Any]]: ...

    async def cancel(self, session_id: str) -> None: ...
