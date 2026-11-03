"""Agents call a provider, validate its JSON, and record where the answer came from."""

import pytest
from pydantic import BaseModel

from nfactory_core.providers import Completion, Pricing, Usage
from nfactory_worker.agents.base import LLM, Agent, AgentOutputError, parse_json_object
from nfactory_worker.providers.fake import FAKE_MODEL_ID, FakeProvider


class Answer(BaseModel):
    value: int


ECHO = Agent(name="echo", prompt_version="3", instructions="Return a value.", output_model=Answer)


def llm(reply: str) -> LLM:
    return LLM(FakeProvider(responder=lambda _m: reply), "fake", FAKE_MODEL_ID, demo=True)


async def test_valid_json_becomes_the_typed_output() -> None:
    result = await ECHO.run(llm('{"value": 4}'), {"x": 1})
    assert result.output == Answer(value=4)


async def test_meta_records_prompt_version_provider_and_usage() -> None:
    meta = (await ECHO.run(llm('{"value": 4}'), {})).meta
    assert (meta.agent, meta.prompt_version, meta.provider, meta.model, meta.demo) == (
        "echo",
        "3",
        "fake",
        FAKE_MODEL_ID,
        True,
    )
    assert meta.output_tokens > 0


async def test_prompts_carry_agent_marker_schema_and_json_input() -> None:
    seen: list[list[dict[str, str]]] = []

    def capture(messages: list[dict[str, str]]) -> str:
        seen.append(messages)
        return '{"value": 1}'

    await ECHO.run(LLM(FakeProvider(responder=capture), "fake", "m", True), {"q": "é"})
    system, user = seen[0][0]["content"], seen[0][1]["content"]
    assert system.startswith("[agent:echo] [prompt:3]")
    assert '"value"' in system  # JSON schema included
    assert user == 'INPUT:\n{"q": "é"}'


@pytest.mark.parametrize("reply", ["not json", '{"value": "x"}', "[1, 2]", '{"other": 1}'])
async def test_invalid_output_is_rejected(reply: str) -> None:
    with pytest.raises(AgentOutputError):
        await ECHO.run(llm(reply), {})


@pytest.mark.parametrize(
    "text",
    ['{"a": 1}', '```json\n{"a": 1}\n```', 'Voici :\n{"a": 1}\nFin.'],
)
def test_json_object_is_extracted_from_common_wrappings(text: str) -> None:
    assert parse_json_object(text) == {"a": 1}


class SchemaSpy:
    """Records the keyword arguments the agent sends to the provider."""

    def __init__(self) -> None:
        self.kwargs: dict[str, object] = {}

    async def complete(self, model: str, messages: list, **kwargs: object) -> Completion:  # type: ignore[type-arg]
        self.kwargs = kwargs
        return Completion('{"value": 2}', model, Usage(1_000_000, 500_000))


async def test_agent_asks_the_provider_for_json_matching_its_schema() -> None:
    spy = SchemaSpy()

    await ECHO.run(LLM(spy, "openai_api", "m", demo=False), {})  # type: ignore[arg-type]

    assert spy.kwargs["json_schema"] == Answer.model_json_schema()


async def test_cost_is_recorded_when_the_price_is_known_and_unmeasured_otherwise() -> None:
    price = Pricing(input_per_mtok=1.0, output_per_mtok=4.0)
    priced = LLM(SchemaSpy(), "openai_api", "m", demo=False, pricing=price)  # type: ignore[arg-type]
    unpriced = LLM(SchemaSpy(), "openai_api", "m", demo=False)  # type: ignore[arg-type]

    assert (await ECHO.run(priced, {})).meta.cost_usd == 3.0
    assert (await ECHO.run(unpriced, {})).meta.cost_usd is None
