"""Demo brain: deterministic answers for every agent, served through FakeProvider so the
pipeline uses exactly the same path as with a real model."""

import json
from collections.abc import Callable
from typing import Any

from nfactory_core.providers import Message
from nfactory_worker.agents.base import LLM, read_input
from nfactory_worker.agents.demo import planning, quality, requirements
from nfactory_worker.providers.fake import FAKE_MODEL_ID, FakeProvider

_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "requirements": requirements.answer,
    "planner": planning.plan,
    "architect": planning.architecture,
    "reviewer": quality.review,
    "debugger": quality.debug,
    "documenter": quality.explain,
}


def respond(messages: list[Message]) -> str | None:
    agent, payload = read_input(messages)
    handler = _HANDLERS.get(agent or "")
    return json.dumps(handler(payload), ensure_ascii=False) if handler else None


def demo_llm() -> LLM:
    return LLM(FakeProvider(responder=respond), "fake", FAKE_MODEL_ID, demo=True)


__all__ = ["demo_llm", "respond"]
