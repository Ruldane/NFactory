# ruff: noqa: E501  (wire-format fixtures read best one per line)
"""Mocked provider servers for the contract suite (respx).

Each server answers in its provider's own dialect, with the quirks the docs describe
(docs/research/providers.md): usage on the last content chunk (DeepSeek, Z.ai) or in a
separate chunk (OpenAI, Kimi, Qwen, MiniMax), keep-alive comments (DeepSeek), named
events without [DONE] (Anthropic), NDJSON (Ollama).
"""

import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
import respx

from nfactory_core.providers.factory import build_provider
from nfactory_core.providers.protocols import ModelProvider

KEY = "sk-contract-test-0123456789abcdefghij"
PUBLIC_IP = "93.184.216.34"

BASES = {
    "openai_api": "https://api.openai.com/v1",
    "anthropic_api": "https://api.anthropic.com",
    "deepseek_api": "https://api.deepseek.com",
    "zai_glm_api": "https://api.z.ai/api/paas/v4",
    "moonshot_kimi_api": "https://api.moonshot.ai/v1",
    "qwen_api": "https://ws-test.eu-central-1.maas.aliyuncs.com/compatible-mode/v1",
    "minimax_api": "https://api.minimax.io/v1",
    "custom_openai_compatible": "https://llm.example.com/v1",
    "ollama_local": "http://127.0.0.1:11434",
}
KINDS = list(BASES)


def public_resolver(host: str) -> list[str]:
    return [PUBLIC_IP]


def _sse(events: Sequence[tuple[str | None, Any]]) -> bytes:
    out = []
    for name, data in events:
        if name == ":":
            out.append(f": {data}\n\n")
            continue
        head = f"event: {name}\n" if name else ""
        body = data if isinstance(data, str) else json.dumps(data)
        out.append(f"{head}data: {body}\n\n")
    return "".join(out).encode()


@dataclass
class Case:
    kind: str
    router: respx.MockRouter
    provider: ModelProvider
    base: str

    model = "contract-model"

    # --- what each dialect looks like on the wire -----------------------------------

    @property
    def dialect(self) -> str:
        if self.kind == "anthropic_api":
            return "anthropic"
        if self.kind == "ollama_local":
            return "ollama"
        return "openai"

    @property
    def chat_url(self) -> str:
        return {
            "anthropic": f"{self.base}/v1/messages",
            "ollama": f"{self.base}/api/chat",
            "openai": f"{self.base}/chat/completions",
        }[self.dialect]

    @property
    def has_discovery(self) -> bool:
        return self.kind not in {"zai_glm_api", "qwen_api"}

    def reply(self, text: str) -> respx.Route:
        body: dict[str, Any]
        if self.dialect == "anthropic":
            body = {
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "model": self.model,
                "content": [{"type": "text", "text": text}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 12, "output_tokens": 5},
            }
        elif self.dialect == "ollama":
            body = {
                "model": self.model,
                "message": {"role": "assistant", "content": text},
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 12,
                "eval_count": 5,
            }
        else:
            body = {
                "id": "cmpl_1",
                "model": self.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": text},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 12, "completion_tokens": 5, "total_tokens": 17},
            }
            if self.kind == "minimax_api":
                body["base_resp"] = {"status_code": 0, "status_msg": "success"}
        return self.router.post(self.chat_url).mock(return_value=httpx.Response(200, json=body))

    def reply_tool(self, name: str, arguments: dict[str, Any]) -> respx.Route:
        body: dict[str, Any]
        if self.dialect == "anthropic":
            body = {
                "id": "msg_2",
                "type": "message",
                "model": self.model,
                "content": [
                    {"type": "tool_use", "id": "toolu_1", "name": name, "input": arguments}
                ],
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 20, "output_tokens": 9},
            }
        elif self.dialect == "ollama":
            body = {
                "model": self.model,
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"function": {"name": name, "arguments": arguments}}],
                },
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 20,
                "eval_count": 9,
            }
        else:
            call = {
                "id": "call_1",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }
            body = {
                "id": "cmpl_2",
                "model": self.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": None, "tool_calls": [call]},
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {"prompt_tokens": 20, "completion_tokens": 9},
            }
        return self.router.post(self.chat_url).mock(return_value=httpx.Response(200, json=body))

    def stream(self, pieces: list[str]) -> respx.Route:
        if self.dialect == "anthropic":
            events: list[tuple[str | None, Any]] = [
                ("message_start", {"type": "message_start", "message": {"model": self.model, "usage": {"input_tokens": 12, "output_tokens": 1}}}),
                ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
                ("ping", {"type": "ping"}),
            ]  # fmt: skip
            events += [
                ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": p}})
                for p in pieces
            ]  # fmt: skip
            events += [
                ("content_block_stop", {"type": "content_block_stop", "index": 0}),
                ("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 5}}),
                ("message_stop", {"type": "message_stop"}),
            ]  # fmt: skip
            content = _sse(events)
            headers = {"content-type": "text/event-stream"}
        elif self.dialect == "ollama":
            lines = [
                {"model": self.model, "message": {"content": p}, "done": False} for p in pieces
            ]
            lines.append({"model": self.model, "message": {"content": ""}, "done": True, "done_reason": "stop", "prompt_eval_count": 12, "eval_count": 5})  # fmt: skip
            content = "".join(json.dumps(line) + "\n" for line in lines).encode()
            headers = {"content-type": "application/x-ndjson"}
        else:
            usage = {"prompt_tokens": 12, "completion_tokens": 5, "total_tokens": 17}
            usage_on_last = self.kind in {"deepseek_api", "zai_glm_api"}
            events = []
            if self.kind == "deepseek_api":
                events.append((":", "keep-alive"))
            for i, piece in enumerate(pieces):
                last = i == len(pieces) - 1
                chunk: dict[str, Any] = {
                    "model": self.model,
                    "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": "stop" if last else None}],
                }  # fmt: skip
                if last and usage_on_last:
                    chunk["usage"] = usage
                events.append((None, chunk))
            if not usage_on_last:
                events.append((None, {"model": self.model, "choices": [], "usage": usage}))
            events.append((None, "[DONE]"))
            content = _sse(events)
            headers = {"content-type": "text/event-stream"}
        return self.router.post(self.chat_url).mock(
            return_value=httpx.Response(200, content=content, headers=headers)
        )

    def models(self, ids: list[str]) -> None:
        if self.dialect == "anthropic":
            caps = {"structured_outputs": {"supported": True}, "image_input": {"supported": True}}
            data = [{"id": i, "type": "model", "display_name": i.upper(), "max_input_tokens": 200000, "max_tokens": 64000, "capabilities": caps} for i in ids]  # fmt: skip
            self.router.get(f"{self.base}/v1/models").mock(
                return_value=httpx.Response(200, json={"data": data, "has_more": False})
            )
        elif self.dialect == "ollama":
            self.router.get(f"{self.base}/api/version").mock(
                return_value=httpx.Response(200, json={"version": "0.12.0"})
            )
            data = [{"name": i, "model": i, "details": {"family": "test"}} for i in ids]
            self.router.get(f"{self.base}/api/tags").mock(
                return_value=httpx.Response(200, json={"models": data})
            )
            show = {
                "capabilities": ["completion", "tools"],
                "model_info": {"test.context_length": 8192},
            }
            self.router.post(f"{self.base}/api/show").mock(
                return_value=httpx.Response(200, json=show)
            )
        else:
            data = [{"id": i, "object": "model", "owned_by": "test"} for i in ids]
            self.router.get(f"{self.base}/models").mock(
                return_value=httpx.Response(200, json={"object": "list", "data": data})
            )

    def fail(self, status: int, body: dict[str, Any]) -> respx.Route:
        return self.router.post(self.chat_url).mock(return_value=httpx.Response(status, json=body))

    def raise_on_chat(self, error: Exception) -> respx.Route:
        return self.router.post(self.chat_url).mock(side_effect=error)

    def json_flag(self, request: httpx.Request) -> Any:
        """The field this dialect uses to ask for JSON, or None when it sends none."""
        body = json.loads(request.content)
        if self.dialect == "anthropic":
            return body.get("output_config", {}).get("format", {}).get("type")
        if self.dialect == "ollama":
            fmt = body.get("format")
            return "schema" if isinstance(fmt, dict) else fmt
        return (body.get("response_format") or {}).get("type")


@pytest.fixture(params=KINDS)
def case(request: pytest.FixtureRequest) -> Iterator[Case]:
    kind = request.param
    with respx.mock(assert_all_called=False) as router:
        provider = build_provider(
            kind,
            base_url=BASES[kind],
            api_key=None if kind == "ollama_local" else KEY,
            resolver=public_resolver,
        )
        yield Case(kind=kind, router=router, provider=provider, base=BASES[kind])
