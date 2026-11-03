"""OpenAI-compatible dialect: OpenAI, DeepSeek, Z.ai, Kimi, Qwen, MiniMax, custom.

"Compatible" is not "identical" (spec §6.1): each provider gets a profile describing
its JSON mode, how it reports usage while streaming and which token-limit field it
reads. Facts come from docs/research/providers.md.
"""

import json
import re
import time
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Literal

from nfactory_core.providers.errors import ProviderError, check_vectors, classify_http_error
from nfactory_core.providers.http import ProviderHttp, parse_json_line
from nfactory_core.providers.sse import iter_sse
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

JsonMode = Literal["json_schema", "json_object", "none"]


@dataclass(frozen=True)
class OpenAIProfile:
    json_mode: JsonMode = "none"
    # Send stream_options.include_usage (undocumented on Z.ai: never sent there).
    stream_usage: bool = True
    max_tokens_field: str = "max_tokens"
    # False when the provider documents no model listing (Z.ai, Qwen).
    discovery: bool = True
    extra_body: Mapping[str, Any] = field(default_factory=dict)


PROFILES: dict[str, OpenAIProfile] = {
    # Reasoning models reject max_tokens: max_completion_tokens is the current field.
    "openai_api": OpenAIProfile("json_schema", True, "max_completion_tokens"),
    "deepseek_api": OpenAIProfile("json_object", True, "max_tokens"),
    "zai_glm_api": OpenAIProfile("json_object", False, "max_tokens", discovery=False),
    "moonshot_kimi_api": OpenAIProfile("json_schema", True, "max_completion_tokens"),
    "qwen_api": OpenAIProfile("json_object", True, "max_tokens", discovery=False),
    # JSON mode is undocumented on MiniMax's OpenAI-compatible endpoint; reasoning_split
    # keeps <think> blocks out of the content.
    "minimax_api": OpenAIProfile(
        "none", True, "max_completion_tokens", extra_body={"reasoning_split": True}
    ),
    "custom_openai_compatible": OpenAIProfile("none", False, "max_tokens"),
}

_THINK = re.compile(r"^\s*<think>.*?</think>\s*", re.DOTALL)


def custom_profile(options: Mapping[str, Any]) -> OpenAIProfile:
    """The custom endpoint's capabilities are whatever its admin declared."""
    base = PROFILES["custom_openai_compatible"]
    mode = options.get("json_mode", base.json_mode)
    return replace(
        base,
        json_mode=mode if mode in ("json_schema", "json_object", "none") else "none",
        stream_usage=bool(options.get("stream_usage", base.stream_usage)),
        discovery=bool(options.get("discovery", True)),
    )


class OpenAICompatibleProvider:
    def __init__(self, kind: str, http: ProviderHttp, profile: OpenAIProfile) -> None:
        self.kind = kind
        self._http = http
        self._profile = profile
        self._models: dict[str, ModelInfo] | None = None

    # --- discovery ---------------------------------------------------------------------

    async def list_models(self) -> list[ModelInfo]:
        if not self._profile.discovery:
            raise ProviderError(
                "unsupported",
                provider=self.kind,
                detail="pas de liste de modèles publiée : utilisez le catalogue",
            )
        body = await self._http.get_json("/models")
        models = [_model_info(item) for item in body.get("data", []) if item.get("id")]
        self._models = {m.id: m for m in models}
        return models

    async def capabilities(self, model: str) -> ProviderCapabilities:
        context = None
        if self._profile.discovery:
            try:
                known = (
                    self._models
                    if self._models is not None
                    else {m.id: m for m in await self.list_models()}
                )
                info = known.get(model)
                context = info.context_window if info else None
            except ProviderError:
                context = None
        return ProviderCapabilities(
            streaming=True,
            tool_calling=True,
            structured_output=self._profile.json_mode != "none",
            vision=False,  # unknown per model: never claimed
            embeddings=False,
            json_schema=self._profile.json_mode == "json_schema",
            max_context_tokens=context,
        )

    async def check_connection(self, probe_model: str | None = None) -> ConnectionReport:
        started = time.monotonic()
        if self._profile.discovery:
            models = await self.list_models()
            return ConnectionReport(True, _ms(started), models_found=len(models))
        if not probe_model:
            raise ProviderError(
                "unsupported",
                provider=self.kind,
                detail="ajoutez un modèle au catalogue pour tester la connexion",
            )
        await self.complete(probe_model, [{"role": "user", "content": "ping"}], max_tokens=1)
        return ConnectionReport(True, _ms(started), detail=f"modèle {probe_model} joignable")

    # --- embeddings --------------------------------------------------------------------

    async def embed(self, model: str, texts: Sequence[str]) -> Embeddings:
        """`/embeddings`: inputs must be non-empty; the reply's `index` gives the order."""
        body = {"model": model, "input": list(texts), "encoding_format": "float"}
        reply = await self._http.post_json("/embeddings", body)
        items = sorted(reply.get("data") or [], key=lambda item: int(item.get("index", 0)))
        vectors = [[float(x) for x in item.get("embedding") or []] for item in items]
        return Embeddings(check_vectors(self.kind, vectors, len(texts)), _usage(reply.get("usage")))

    # --- generation --------------------------------------------------------------------

    def _body(
        self,
        model: str,
        messages: list[Message],
        *,
        json_schema: dict[str, Any] | None,
        tools: Sequence[ToolSpec],
        max_tokens: int | None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "messages": [_to_openai(m) for m in messages],
            **self._profile.extra_body,
        }
        if max_tokens is not None:
            body[self._profile.max_tokens_field] = max_tokens
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
        if json_schema is not None:
            if self._profile.json_mode == "json_schema":
                # strict=False: agent schemas are validated client-side, and strict mode
                # imposes rules (all fields required, closed objects) they do not follow.
                body["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {"name": "reply", "schema": json_schema, "strict": False},
                }
            elif self._profile.json_mode == "json_object":
                body["response_format"] = {"type": "json_object"}
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
            model, messages, json_schema=json_schema, tools=tools, max_tokens=max_tokens
        )
        reply = await self._http.post_json("/chat/completions", body)
        choices = reply.get("choices") or []
        if not choices:
            raise ProviderError("invalid_response", provider=self.kind, detail="no choices")
        choice = choices[0]
        message = choice.get("message") or {}
        calls = tuple(self._tool_call(c) for c in message.get("tool_calls") or [])
        content = _THINK.sub("", message.get("content") or "")
        return Completion(
            content=content,
            model=str(reply.get("model") or model),
            usage=_usage(reply.get("usage")),
            finish_reason=_finish(choice.get("finish_reason"), bool(calls)),
            tool_calls=calls,
            raw={"id": reply.get("id")},
        )

    async def stream(
        self, model: str, messages: list[Message], *, max_tokens: int | None = None
    ) -> AsyncIterator[StreamChunk]:
        body = self._body(model, messages, json_schema=None, tools=(), max_tokens=max_tokens)
        body["stream"] = True
        if self._profile.stream_usage:
            body["stream_options"] = {"include_usage": True}
        usage: Usage | None = None
        finish: str | None = None
        async with self._http.post_stream("/chat/completions", body) as lines:
            async for event in iter_sse(lines):
                if event.data.strip() == "[DONE]":
                    break
                chunk = parse_json_line(self.kind, event.data)
                if "error" in chunk or (
                    "base_resp" in chunk and chunk["base_resp"].get("status_code")
                ):
                    raise classify_http_error(self.kind, 503, chunk, {})
                # Usage arrives on the last content chunk (DeepSeek, Z.ai) or on a
                # separate chunk with no choices (OpenAI, Kimi, Qwen): accept both.
                if chunk.get("usage"):
                    usage = _usage(chunk["usage"])
                for choice in chunk.get("choices") or []:
                    text = (choice.get("delta") or {}).get("content")
                    if text:
                        yield StreamChunk(text=text)
                    if choice.get("finish_reason"):
                        finish = _finish(choice["finish_reason"], False)
        yield StreamChunk(usage=usage, finish_reason=finish or "stop")

    def _tool_call(self, raw: Mapping[str, Any]) -> ToolCall:
        function = raw.get("function") or {}
        arguments = function.get("arguments") or "{}"
        try:
            parsed = json.loads(arguments) if isinstance(arguments, str) else dict(arguments)
        except json.JSONDecodeError as exc:
            raise ProviderError(
                "invalid_response", provider=self.kind, detail="tool arguments are not JSON"
            ) from exc
        return ToolCall(
            id=str(raw.get("id") or ""), name=str(function.get("name")), arguments=parsed
        )


def _to_openai(message: Message) -> dict[str, Any]:
    role = message["role"]
    if role == "tool":
        return {
            "role": "tool",
            "tool_call_id": message.get("tool_call_id", ""),
            "content": str(message.get("content", "")),
        }
    if role == "assistant" and message.get("tool_calls"):
        return {
            "role": "assistant",
            "content": message.get("content") or None,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
                }
                for call in message["tool_calls"]
            ],
        }
    return {"role": role, "content": message.get("content", "")}


def _usage(raw: Mapping[str, Any] | None) -> Usage:
    if not raw:
        return Usage(0, 0)
    prompt = raw.get("prompt_tokens_details") or {}
    completion = raw.get("completion_tokens_details") or {}
    cached = prompt.get("cached_tokens") or raw.get("prompt_cache_hit_tokens") or 0
    return Usage(
        input_tokens=int(raw.get("prompt_tokens") or 0),
        output_tokens=int(raw.get("completion_tokens") or 0),
        cached_input_tokens=int(cached),
        reasoning_tokens=int(completion.get("reasoning_tokens") or 0),
    )


def _finish(reason: Any, has_calls: bool) -> str:
    if has_calls or reason == "tool_calls":
        return "tool_calls"
    return str(reason or "stop")


def _model_info(item: Mapping[str, Any]) -> ModelInfo:
    context = item.get("context_window") or item.get("context_length")
    extras = {
        key: item[key]
        for key in ("owned_by", "supports_reasoning", "supports_image_in", "max_output_tokens")
        if key in item
    }
    return ModelInfo(
        id=str(item["id"]),
        display_name=item.get("name"),
        context_window=int(context) if isinstance(context, int) else None,
        capabilities=extras,
    )


def _ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)
