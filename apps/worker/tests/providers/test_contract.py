"""The demo provider honours the same ModelProvider contract as the real adapters
(those are covered against mocked servers in packages/core-py/tests/providers)."""

from nfactory_core.providers import Completion, ConnectionReport, ModelInfo, ProviderCapabilities
from nfactory_worker.providers.fake import FAKE_MODEL_ID, FakeProvider

MESSAGES = [{"role": "user", "content": "Décris une API de gestion de stock"}]


async def test_connection_check_and_models_are_typed() -> None:
    provider = FakeProvider()
    assert isinstance(await provider.check_connection(), ConnectionReport)
    models = await provider.list_models()
    assert [type(m) for m in models] == [ModelInfo]
    assert isinstance(await provider.capabilities(models[0].id), ProviderCapabilities)


async def test_complete_returns_content_and_usage() -> None:
    result = await FakeProvider().complete(FAKE_MODEL_ID, MESSAGES, json_schema={"type": "object"})

    assert isinstance(result, Completion)
    assert result.content
    assert result.model == FAKE_MODEL_ID
    assert result.usage.output_tokens >= 1


async def test_stream_concatenates_to_the_full_completion_and_ends_with_usage() -> None:
    provider = FakeProvider()
    full = await provider.complete(FAKE_MODEL_ID, MESSAGES)

    chunks = [chunk async for chunk in provider.stream(FAKE_MODEL_ID, MESSAGES)]

    assert len(chunks) > 2
    assert "".join(c.text for c in chunks) == full.content
    assert chunks[-1].usage == full.usage
