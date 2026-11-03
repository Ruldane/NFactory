"""Provider-neutral value types: every adapter speaks these, whatever its dialect."""

from dataclasses import dataclass, field
from typing import Any

# {"role": "system" | "user" | "assistant" | "tool", "content": str,
#  "tool_calls": [ToolCall] (assistant), "tool_call_id": str (tool)}
Message = dict[str, Any]


@dataclass(frozen=True)
class ProviderCapabilities:
    streaming: bool
    tool_calling: bool
    structured_output: bool
    vision: bool
    embeddings: bool
    json_schema: bool
    max_context_tokens: int | None


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0
    reasoning_tokens: int = 0


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema of the arguments


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class Completion:
    content: str
    model: str
    usage: Usage
    finish_reason: str = "stop"
    tool_calls: tuple[ToolCall, ...] = ()
    # Provider-specific extras (request id, etc.); never secrets.
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StreamChunk:
    """A text delta; the last chunk carries the usage and the finish reason."""

    text: str = ""
    usage: Usage | None = None
    finish_reason: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()


@dataclass(frozen=True)
class Embeddings:
    """One vector per input text, in input order."""

    vectors: list[list[float]]
    usage: Usage


@dataclass(frozen=True)
class ModelInfo:
    id: str
    display_name: str | None = None
    context_window: int | None = None
    capabilities: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectionReport:
    """Result of a consented connection test. `ok` is the only road to "connected"."""

    ok: bool
    latency_ms: int
    models_found: int | None = None
    detail: str = ""
