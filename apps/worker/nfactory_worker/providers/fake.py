"""Deterministic offline provider for demo mode (spec F40). No network, no key.

Replies come, in order, from: a responder callable (computes a reply from the whole
conversation; demo agents use it), keyword scripts (prompt contains a keyword -> fixed
reply), or a stable hash-derived sentence. Always flagged `demo`.
"""

import hashlib
from collections.abc import AsyncIterator, Callable, Mapping
from typing import Any

from nfactory_core.providers import (
    Completion,
    ConnectionReport,
    Message,
    ModelInfo,
    ProviderCapabilities,
    StreamChunk,
    Usage,
)
from nfactory_core.routing import DEMO_MODEL_ID

FAKE_MODEL_ID = DEMO_MODEL_ID

_WORDS = (
    "plan", "module", "test", "fichier", "API", "schéma", "validation", "rapport",
    "workflow", "données", "export", "contrôle",
)  # fmt: skip


Responder = Callable[[list[Message]], str | None]


class FakeProvider:
    def __init__(
        self, scripts: Mapping[str, str] | None = None, responder: Responder | None = None
    ) -> None:
        # Keyword (case-insensitive) -> exact reply.
        self._scripts = {k.lower(): v for k, v in (scripts or {}).items()}
        self._responder = responder

    async def check_connection(self, probe_model: str | None = None) -> ConnectionReport:
        return ConnectionReport(True, 0, 1, detail="modèle de démonstration, sans IA réelle")

    async def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(FAKE_MODEL_ID, "Modèle de démonstration", capabilities={"demo": True})]

    async def capabilities(self, model: str) -> ProviderCapabilities:
        return ProviderCapabilities(
            streaming=True,
            tool_calling=False,
            structured_output=True,
            vision=False,
            embeddings=False,
            json_schema=True,
            max_context_tokens=None,
        )

    async def complete(self, model: str, messages: list[Message], **kwargs: Any) -> Completion:
        # json_schema / tools / max_tokens are accepted and ignored: replies are scripted.
        prompt = _last_user_text(messages)
        computed = self._responder(messages) if self._responder else None
        content = computed if computed is not None else self._reply(prompt)
        return Completion(
            content=content,
            model=model,
            usage=Usage(input_tokens=_count_tokens(prompt), output_tokens=_count_tokens(content)),
            raw={"demo": True},
        )

    async def stream(
        self, model: str, messages: list[Message], **kwargs: Any
    ) -> AsyncIterator[StreamChunk]:
        completion = await self.complete(model, messages)
        content = completion.content
        for i in range(0, len(content), 8):
            yield StreamChunk(text=content[i : i + 8])
        yield StreamChunk(usage=completion.usage, finish_reason="stop")

    def _reply(self, prompt: str) -> str:
        lowered = prompt.lower()
        for keyword, reply in self._scripts.items():
            if keyword in lowered:
                return reply
        digest = hashlib.sha256(prompt.encode()).digest()
        words = " ".join(_WORDS[b % len(_WORDS)] for b in digest[:8])
        return f"[démo] Réponse simulée : {words}."


def _last_user_text(messages: list[Message]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return str(message.get("content", ""))
    return ""


def _count_tokens(text: str) -> int:
    # Rough estimate, good enough for a fake: ~1 token per word.
    return max(1, len(text.split()))
