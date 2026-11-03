"""Anthropic Messages API (not OpenAI-compatible).

Wire facts (claude-api reference, docs/research/providers.md):
- `x-api-key` + `anthropic-version: 2026-10-21`; that version rejects temperature,
  top_p and top_k, so none is ever sent.
- `system` is a top-level field; tool results travel as user `tool_result` blocks.
- Structured output is `output_config.format` with a JSON schema that has closed
  objects and no length or numeric bounds; it is sent only to models whose
  `/v1/models` capabilities say `structured_outputs` is supported.
- Streams are named SSE events with no [DONE]; `message_delta.usage` is cumulative.
"""

import time
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from nfactory_core.providers.errors import ProviderError, classify_http_error
from nfactory_core.providers.http import ProviderHttp, parse_json_line
from nfactory_core.providers.sse import iter_sse
from nfactory_core.providers.types import (
    Completion,
    ConnectionReport,
    Message,
    ModelInfo,
    ProviderCapabilities,
    StreamChunk,
    ToolCall,
    ToolSpec,
    Usage,
)

API_VERSION = "2026-10-21"
DEFAULT_MAX_TOKENS = 16000  # non-streaming default that stays under HTTP timeouts

_UNSUPPORTED_KEYS = frozenset(
    {
        "minLength", "maxLength", "minimum", "maximum", "exclusiveMinimum",
        "exclusiveMaximum", "multipleOf", "minItems", "maxItems", "uniqueItems",
        "pattern", "default",
    }
)  # fmt: skip

_STOP = {"end_turn": "stop", "tool_use": "tool_calls", "max_tokens": "length"}

# Status to classify a mid-stream `event: error` by its error type.
_ERROR_STATUS = {
    "overloaded_error": 529,
    "rate_limit_error": 429,
    "api_error": 500,
    "timeout_error": 504,
    "authentication_error": 401,
    "permission_error": 403,
    "billing_error": 402,
    "not_found_error": 404,
}


def anthropic_schema(schema: Any) -> Any:
    """Copy of `schema` the Messages API accepts: closed objects, no bounds.
    The reply is still validated client-side against the full schema."""
    if isinstance(schema, list):
        return [anthropic_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    out = {k: anthropic_schema(v) for k, v in schema.items() if k not in _UNSUPPORTED_KEYS}
    if out.get("type") == "object" or "properties" in out:
        out["additionalProperties"] = False
    return out


def anthropic_headers(api_key: str) -> dict[str, str]:
    return {"x-api-key": api_key, "anthropic-version": API_VERSION}


class AnthropicProvider:
    kind = "anthropic_api"

    def __init__(self, http: ProviderHttp) -> None:
        self._http = http
        self._models: dict[str, ModelInfo] | None = None

    # --- discovery ---------------------------------------------------------------------

    async def list_models(self) -> list[ModelInfo]:
        models: list[ModelInfo] = []
        params: dict[str, Any] = {"limit": 1000}
        while True:
            page = await self._http.get_json("/v1/models", params=params)
            models += [_model_info(item) for item in page.get("data", []) if item.get("id")]
            if not page.get("has_more") or not page.get("last_id"):
                break
            params = {"limit": 1000, "after_id": page["last_id"]}
        self._models = {m.id: m for m in models}
        return models

    async def _model(self, model: str) -> ModelInfo | None:
        if self._models is None:
            try:
                await self.list_models()
            except ProviderError:
                return None
        return (self._models or {}).get(model)

    async def capabilities(self, model: str) -> ProviderCapabilities:
        info = await self._model(model)
        caps = info.capabilities if info else {}
        return ProviderCapabilities(
            streaming=True,
            tool_calling=True,
            structured_output=_supported(caps, "structured_outputs"),
            vision=_supported(caps, "image_input"),
            embeddings=False,
            json_schema=_supported(caps, "structured_outputs"),
            max_context_tokens=info.context_window if info else None,
        )

    async def check_connection(self, probe_model: str | None = None) -> ConnectionReport:
        started = time.monotonic()
        models = await self.list_models()
        return ConnectionReport(True, int((time.monotonic() - started) * 1000), len(models))

    # --- generation --------------------------------------------------------------------

    async def _body(
        self,
        model: str,
        messages: list[Message],
        *,
        json_schema: dict[str, Any] | None,
        tools: Sequence[ToolSpec],
        max_tokens: int | None,
    ) -> dict[str, Any]:
        system, turns = _to_anthropic(messages)
        info = await self._model(model) if json_schema is not None else None
        body: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens or DEFAULT_MAX_TOKENS,
            "messages": turns,
        }
        if system:
            body["system"] = system
        if tools:
            body["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.parameters}
                for t in tools
            ]
        if json_schema is not None and info and _supported(info.capabilities, "structured_outputs"):
            body["output_config"] = {
                "format": {"type": "json_schema", "schema": anthropic_schema(json_schema)}
            }
        return body

    async def complete(
        self,
        model: str,
        messages: list[Message],
        *,
        json_schema: dict[str, Any] | None = None,
        tools: Sequence[ToolSpec] = (),
        max_tokens: int | None = None,
    ) -> Completion:
        body = await self._body(
            model, messages, json_schema=json_schema, tools=tools, max_tokens=max_tokens
        )
        reply = await self._http.post_json("/v1/messages", body)
        text: list[str] = []
        calls: list[ToolCall] = []
        for block in reply.get("content") or []:
            if block.get("type") == "text":
                text.append(str(block.get("text", "")))
            elif block.get("type") == "tool_use":
                calls.append(
                    ToolCall(
                        str(block.get("id")), str(block.get("name")), dict(block.get("input") or {})
                    )
                )
        return Completion(
            content="".join(text),
            model=str(reply.get("model") or model),
            usage=_usage(reply.get("usage")),
            finish_reason=_STOP.get(str(reply.get("stop_reason")), str(reply.get("stop_reason"))),
            tool_calls=tuple(calls),
            raw={"id": reply.get("id")},
        )

    async def stream(
        self, model: str, messages: list[Message], *, max_tokens: int | None = None
    ) -> AsyncIterator[StreamChunk]:
        body = await self._body(model, messages, json_schema=None, tools=(), max_tokens=max_tokens)
        body["stream"] = True
        input_usage: Mapping[str, Any] = {}
        output_tokens = 0
        finish = "stop"
        async with self._http.post_stream("/v1/messages", body) as lines:
            async for event in iter_sse(lines):
                if event.event == "ping":
                    continue
                data = parse_json_line(self.kind, event.data)
                kind = data.get("type", event.event)
                if kind == "error":
                    error_type = str((data.get("error") or {}).get("type", ""))
                    raise classify_http_error(
                        self.kind, _ERROR_STATUS.get(error_type, 500), data, {}
                    )
                if kind == "message_start":
                    input_usage = (data.get("message") or {}).get("usage") or {}
                elif kind == "content_block_delta":
                    delta = data.get("delta") or {}
                    if delta.get("type") == "text_delta" and delta.get("text"):
                        yield StreamChunk(text=str(delta["text"]))
                elif kind == "message_delta":
                    reason = (data.get("delta") or {}).get("stop_reason")
                    if reason:
                        finish = _STOP.get(str(reason), str(reason))
                    output_tokens = int((data.get("usage") or {}).get("output_tokens") or 0)
                elif kind == "message_stop":
                    break
                # Unknown event types are ignored, as the docs require.
        usage = _usage({**input_usage, "output_tokens": output_tokens})
        yield StreamChunk(usage=usage, finish_reason=finish)


def _to_anthropic(messages: list[Message]) -> tuple[str, list[dict[str, Any]]]:
    system: list[str] = []
    turns: list[dict[str, Any]] = []
    for message in messages:
        role = message["role"]
        if role == "system":
            system.append(str(message.get("content", "")))
            continue
        if role == "tool":
            block = {
                "type": "tool_result",
                "tool_use_id": message.get("tool_call_id", ""),
                "content": str(message.get("content", "")),
            }
            # Results of parallel calls go back together, in one user message.
            if turns and turns[-1]["role"] == "user" and isinstance(turns[-1]["content"], list):
                turns[-1]["content"].append(block)
            else:
                turns.append({"role": "user", "content": [block]})
            continue
        if role == "assistant" and message.get("tool_calls"):
            blocks: list[dict[str, Any]] = []
            if message.get("content"):
                blocks.append({"type": "text", "text": str(message["content"])})
            blocks += [
                {"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments}
                for c in message["tool_calls"]
            ]
            turns.append({"role": "assistant", "content": blocks})
            continue
        turns.append({"role": role, "content": str(message.get("content", ""))})
    return "\n\n".join(system), turns


def _usage(raw: Mapping[str, Any] | None) -> Usage:
    raw = raw or {}
    cache_write = int(raw.get("cache_creation_input_tokens") or 0)
    cache_read = int(raw.get("cache_read_input_tokens") or 0)
    return Usage(
        # Total input = uncached + cache writes + cache reads.
        input_tokens=int(raw.get("input_tokens") or 0) + cache_write + cache_read,
        output_tokens=int(raw.get("output_tokens") or 0),
        cached_input_tokens=cache_read,
    )


def _supported(capabilities: Mapping[str, Any], name: str) -> bool:
    entry = capabilities.get(name)
    return isinstance(entry, Mapping) and bool(entry.get("supported"))


def _model_info(item: Mapping[str, Any]) -> ModelInfo:
    caps = dict(item.get("capabilities") or {})
    if item.get("max_tokens"):
        caps["max_output_tokens"] = item["max_tokens"]
    for key in ("lifecycle", "retires_at"):
        if item.get(key):
            caps[key] = item[key]
    context = item.get("max_input_tokens")
    return ModelInfo(
        id=str(item["id"]),
        display_name=item.get("display_name"),
        context_window=int(context) if isinstance(context, int) else None,
        capabilities=caps,
    )
