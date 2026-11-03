"""Ollama, native API (`/api/*`), preferred over its OpenAI layer: real discovery with
capabilities and context length, `format` takes a JSON schema, explicit errors.
Streams are NDJSON, and a mid-stream error arrives as `{"error"}` with HTTP 200.
"""

import json
import time
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from nfactory_core.providers.errors import ProviderError, check_vectors
from nfactory_core.providers.http import ProviderHttp, parse_json_line
from nfactory_core.providers.types import (
    Completion,
    ConnectionReport,
    Embeddings,
    Message,
    ModelInfo,
    ProviderCapabilities,
    StreamChunk,
    ToolCall,
    ToolSpec,
    Usage,
)


class OllamaProvider:
    kind = "ollama_local"

    def __init__(self, http: ProviderHttp) -> None:
        self._http = http

    async def list_models(self) -> list[ModelInfo]:
        body = await self._http.get_json("/api/tags")
        return [
            ModelInfo(id=str(m["name"]), capabilities=dict(m.get("details") or {}))
            for m in body.get("models", [])
            if m.get("name")
        ]

    async def capabilities(self, model: str) -> ProviderCapabilities:
        try:
            shown = await self._http.post_json("/api/show", {"model": model})
        except ProviderError:
            shown = {}
        caps = set(shown.get("capabilities") or [])
        info = shown.get("model_info") or {}
        context = next((v for k, v in info.items() if k.endswith(".context_length")), None)
        return ProviderCapabilities(
            streaming=True,
            tool_calling="tools" in caps,
            structured_output=True,
            vision="vision" in caps,
            embeddings="embedding" in caps,
            json_schema=True,
            max_context_tokens=int(context) if isinstance(context, int) else None,
        )

    async def check_connection(self, probe_model: str | None = None) -> ConnectionReport:
        started = time.monotonic()
        version = await self._http.get_json("/api/version")
        models = await self.list_models()
        return ConnectionReport(
            True,
            int((time.monotonic() - started) * 1000),
            len(models),
            detail=f"Ollama {version.get('version', '?')}",
        )

    async def embed(self, model: str, texts: Sequence[str]) -> Embeddings:
        """`/api/embed`: one vector per input, in input order."""
        reply = await self._http.post_json("/api/embed", {"model": model, "input": list(texts)})
        self._raise_if_error(reply)
        vectors = [[float(x) for x in v] for v in reply.get("embeddings") or []]
        usage = Usage(int(reply.get("prompt_eval_count") or 0), 0)
        return Embeddings(check_vectors(self.kind, vectors, len(texts)), usage)

    def _body(
        self,
        model: str,
        messages: list[Message],
        *,
        stream: bool,
        json_schema: dict[str, Any] | None = None,
        tools: Sequence[ToolSpec] = (),
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "messages": [_to_ollama(m) for m in messages],
            "stream": stream,
        }
        if max_tokens is not None:
            body["options"] = {"num_predict": max_tokens}
        if json_schema is not None:
            body["format"] = json_schema
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]
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
        body = self._body(
            model,
            messages,
            stream=False,
            json_schema=json_schema,
            tools=tools,
            max_tokens=max_tokens,
        )
        reply = await self._http.post_json("/api/chat", body)
        self._raise_if_error(reply)
        message = reply.get("message") or {}
        calls = tuple(
            _tool_call(i, raw, self.kind) for i, raw in enumerate(message.get("tool_calls") or [])
        )
        return Completion(
            content=str(message.get("content") or ""),
            model=str(reply.get("model") or model),
            usage=_usage(reply),
            finish_reason="tool_calls" if calls else _finish(reply.get("done_reason")),
            tool_calls=calls,
        )

    async def stream(
        self, model: str, messages: list[Message], *, max_tokens: int | None = None
    ) -> AsyncIterator[StreamChunk]:
        body = self._body(model, messages, stream=True, max_tokens=max_tokens)
        async with self._http.post_stream("/api/chat", body) as lines:
            async for line in lines:
                if not line.strip():
                    continue
                chunk = parse_json_line(self.kind, line)
                self._raise_if_error(chunk)
                text = (chunk.get("message") or {}).get("content")
                if text:
                    yield StreamChunk(text=str(text))
                if chunk.get("done"):
                    yield StreamChunk(
                        usage=_usage(chunk), finish_reason=_finish(chunk.get("done_reason"))
                    )
                    return

    def _raise_if_error(self, body: Mapping[str, Any]) -> None:
        if body.get("error"):
            raise ProviderError("unavailable", provider=self.kind, detail=str(body["error"]))


def _to_ollama(message: Message) -> dict[str, Any]:
    out: dict[str, Any] = {"role": message["role"], "content": str(message.get("content") or "")}
    if message.get("tool_calls"):
        out["tool_calls"] = [
            {"function": {"name": c.name, "arguments": c.arguments}} for c in message["tool_calls"]
        ]
    return out


def _tool_call(index: int, raw: Mapping[str, Any], provider: str) -> ToolCall:
    function = raw.get("function") or {}
    arguments = function.get("arguments") or {}
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError as exc:
            raise ProviderError("invalid_response", provider=provider) from exc
    return ToolCall(id=f"call_{index}", name=str(function.get("name")), arguments=dict(arguments))


def _usage(body: Mapping[str, Any]) -> Usage:
    return Usage(
        input_tokens=int(body.get("prompt_eval_count") or 0),
        output_tokens=int(body.get("eval_count") or 0),
        cached_input_tokens=int(body.get("prompt_eval_cached_count") or 0),
    )


def _finish(reason: Any) -> str:
    return str(reason or "stop")
