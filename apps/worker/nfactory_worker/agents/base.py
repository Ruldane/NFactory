"""Agent = versioned prompt + typed output (spec §5.1).

An agent sends a system prompt (marker, instructions, JSON schema) and a JSON input,
then validates the reply against its Pydantic model. Each result records the prompt
version, provider, model, usage and duration.
"""

import json
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from nfactory_core.providers import ModelProvider, Pricing, cost_usd

INPUT_PREFIX = "INPUT:\n"
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class AgentOutputError(ValueError):
    pass


@dataclass(frozen=True)
class LLM:
    """The model an agent talks to, with the facts recorded on every call."""

    provider: ModelProvider
    provider_name: str
    model: str
    demo: bool
    pricing: Pricing | None = None  # from the admin catalog; None = cost unmeasured


@dataclass(frozen=True)
class AgentMeta:
    agent: str
    prompt_version: str
    provider: str
    model: str
    demo: bool
    input_tokens: int
    output_tokens: int
    duration_s: float
    cost_usd: float | None = None


@dataclass(frozen=True)
class AgentResult[OutT: BaseModel]:
    output: OutT
    meta: AgentMeta


class Agent[OutT: BaseModel]:
    def __init__(
        self, *, name: str, prompt_version: str, instructions: str, output_model: type[OutT]
    ) -> None:
        self.name = name
        self.prompt_version = prompt_version
        self.output_model = output_model
        self.json_schema = output_model.model_json_schema()
        schema = json.dumps(self.json_schema, ensure_ascii=False)
        self.system_prompt = (
            f"[agent:{name}] [prompt:{prompt_version}]\n{instructions.strip()}\n\n"
            "Answer with ONE JSON object matching this JSON schema, and nothing else. "
            "Write user-facing text in French.\n"
            f"{schema}"
        )

    async def run(self, llm: LLM, payload: Mapping[str, Any]) -> AgentResult[OutT]:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": INPUT_PREFIX + json.dumps(payload, ensure_ascii=False)},
        ]
        started = time.monotonic()
        # The schema is also in the prompt: providers without JSON mode still follow it,
        # and the reply is validated here whatever the provider claims.
        completion = await llm.provider.complete(llm.model, messages, json_schema=self.json_schema)
        try:
            output = self.output_model.model_validate(parse_json_object(completion.content))
        except (ValueError, ValidationError) as exc:
            raise AgentOutputError(f"{self.name}: invalid output ({exc})") from exc
        meta = AgentMeta(
            agent=self.name,
            prompt_version=self.prompt_version,
            provider=llm.provider_name,
            model=completion.model,
            demo=llm.demo,
            input_tokens=completion.usage.input_tokens,
            output_tokens=completion.usage.output_tokens,
            duration_s=time.monotonic() - started,
            cost_usd=0.0 if llm.demo else cost_usd(completion.usage, llm.pricing),
        )
        return AgentResult(output=output, meta=meta)


def parse_json_object(text: str) -> dict[str, Any]:
    """The first JSON object in a reply, tolerating code fences and surrounding prose."""
    fenced = _FENCE.search(text)
    candidate = fenced.group(1) if fenced else text
    start, end = candidate.find("{"), candidate.rfind("}")
    if start == -1 or end < start:
        raise AgentOutputError("no JSON object in reply")
    try:
        value = json.loads(candidate[start : end + 1])
    except json.JSONDecodeError as exc:
        raise AgentOutputError(f"invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise AgentOutputError("reply is not a JSON object")
    return value


def read_input(messages: list[dict[str, Any]]) -> tuple[str | None, dict[str, Any]]:
    """Inverse of `Agent.run`: (agent name, input payload). Used by the demo responder."""
    system = str(messages[0].get("content", "")) if messages else ""
    match = re.match(r"\[agent:([a-z_]+)\]", system)
    user = str(messages[-1].get("content", "")) if messages else ""
    payload = json.loads(user[len(INPUT_PREFIX) :]) if user.startswith(INPUT_PREFIX) else {}
    return (match.group(1) if match else None), payload
