"""Contract every model provider adapter satisfies (task 2.2, spec §6.6).

Runs once per provider kind against a mocked server speaking that provider's dialect
(see conftest.py). The assertions are the same for every adapter.
"""

import json

import httpx
import pytest

from nfactory_core.providers.errors import ProviderError
from nfactory_core.providers.types import (
    Completion,
    ConnectionReport,
    ProviderCapabilities,
    ToolSpec,
)

KEY = "sk-contract-test-0123456789abcdefghij"
MESSAGES = [
    {"role": "system", "content": "Tu réponds en JSON."},
    {"role": "user", "content": "Décris une API de gestion de stock"},
]
SCHEMA = {
    "type": "object",
    "properties": {"title": {"type": "string", "minLength": 1}, "count": {"type": "integer"}},
    "required": ["title"],
}
WEATHER = ToolSpec(
    name="get_weather",
    description="Météo d'une ville",
    parameters={"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},
)

# How each provider asks for JSON (docs/research/providers.md, "JSON and tools").
JSON_FLAGS = {
    "openai_api": "json_schema",
    "anthropic_api": "json_schema",
    "deepseek_api": "json_object",
    "zai_glm_api": "json_object",
    "moonshot_kimi_api": "json_schema",
    "qwen_api": "json_object",
    "minimax_api": None,  # undocumented on the OpenAI-compatible endpoint
    "custom_openai_compatible": None,  # unknown until the admin says otherwise
    "ollama_local": "schema",
}


async def test_complete_returns_text_model_and_usage(case) -> None:  # type: ignore[no-untyped-def]
    case.reply('{"title": "Stock"}')

    result = await case.provider.complete(case.model, MESSAGES)

    assert isinstance(result, Completion)
    assert result.content == '{"title": "Stock"}'
    assert result.model == case.model
    assert (result.usage.input_tokens, result.usage.output_tokens) == (12, 5)
    assert result.finish_reason == "stop"


async def test_the_key_travels_only_in_the_auth_header(case) -> None:  # type: ignore[no-untyped-def]
    route = case.reply("ok")

    await case.provider.complete(case.model, MESSAGES)

    request = route.calls.last.request
    assert KEY not in request.content.decode()
    assert KEY not in str(request.url)
    if case.kind == "ollama_local":
        assert "authorization" not in request.headers
    elif case.kind == "anthropic_api":
        assert request.headers["x-api-key"] == KEY
        assert request.headers["anthropic-version"] == "2026-10-21"
        assert "temperature" not in json.loads(request.content)  # 400 on 2026-10-21
    else:
        assert request.headers["authorization"] == f"Bearer {KEY}"


async def test_system_prompt_reaches_the_model(case) -> None:  # type: ignore[no-untyped-def]
    route = case.reply("ok")

    await case.provider.complete(case.model, MESSAGES)

    body = json.loads(route.calls.last.request.content)
    if case.dialect == "anthropic":
        assert body["system"] == "Tu réponds en JSON."
        assert [m["role"] for m in body["messages"]] == ["user"]
        assert body["max_tokens"] > 0  # required by the Messages API
    else:
        assert body["messages"][0] == {"role": "system", "content": "Tu réponds en JSON."}


async def test_stream_concatenates_and_ends_with_usage(case) -> None:  # type: ignore[no-untyped-def]
    route = case.stream(["Bon", "jour ", "le monde"])

    chunks = [chunk async for chunk in case.provider.stream(case.model, MESSAGES)]

    assert "".join(c.text for c in chunks) == "Bonjour le monde"
    final = chunks[-1]
    assert final.usage is not None
    assert (final.usage.input_tokens, final.usage.output_tokens) == (12, 5)
    assert final.finish_reason == "stop"
    body = json.loads(route.calls.last.request.content)
    assert body.get("stream") is not False
    if case.kind == "zai_glm_api":
        assert "stream_options" not in body  # undocumented there: never sent


async def test_tool_calls_are_parsed_into_name_and_arguments(case) -> None:  # type: ignore[no-untyped-def]
    route = case.reply_tool("get_weather", {"city": "Lyon"})

    result = await case.provider.complete(case.model, MESSAGES, tools=[WEATHER])

    assert [(c.name, c.arguments) for c in result.tool_calls] == [("get_weather", {"city": "Lyon"})]
    assert result.finish_reason == "tool_calls"
    sent = json.dumps(json.loads(route.calls.last.request.content)["tools"])
    assert "get_weather" in sent and "city" in sent


async def test_json_request_uses_the_provider_json_mode(case) -> None:  # type: ignore[no-untyped-def]
    case.models([case.model])  # Anthropic sends a schema only to models that support it
    route = case.reply('{"title": "x"}')

    await case.provider.complete(case.model, MESSAGES, json_schema=SCHEMA)

    request = route.calls.last.request
    assert case.json_flag(request) == JSON_FLAGS[case.kind]
    if case.dialect == "anthropic":
        sent = json.loads(request.content)["output_config"]["format"]["schema"]
        # The Messages API refuses length constraints and open objects.
        assert sent["additionalProperties"] is False
        assert "minLength" not in json.dumps(sent)


async def test_models_are_discovered_or_unsupported_is_explicit(case) -> None:  # type: ignore[no-untyped-def]
    case.models(["model-a", "model-b"])

    if case.has_discovery:
        models = await case.provider.list_models()
        assert [m.id for m in models] == ["model-a", "model-b"]
    else:
        with pytest.raises(ProviderError) as caught:
            await case.provider.list_models()
        assert caught.value.kind == "unsupported"


async def test_capabilities_are_typed(case) -> None:  # type: ignore[no-untyped-def]
    case.models([case.model])
    assert isinstance(await case.provider.capabilities(case.model), ProviderCapabilities)


async def test_connection_check_reports_ok(case) -> None:  # type: ignore[no-untyped-def]
    case.models(["model-a"])
    case.reply("ok")  # providers without discovery probe with a one-token completion

    report = await case.provider.check_connection(probe_model="model-a")

    assert isinstance(report, ConnectionReport)
    assert report.ok
    assert report.latency_ms >= 0


async def test_http_401_is_an_auth_error(case) -> None:  # type: ignore[no-untyped-def]
    case.fail(401, {"error": {"message": "invalid key"}})

    with pytest.raises(ProviderError) as caught:
        await case.provider.complete(case.model, MESSAGES)

    assert caught.value.kind == "auth"
    assert not caught.value.retryable


async def test_timeout_is_a_retryable_timeout_error(case) -> None:  # type: ignore[no-untyped-def]
    case.raise_on_chat(httpx.ReadTimeout("slow"))

    with pytest.raises(ProviderError) as caught:
        await case.provider.complete(case.model, MESSAGES)

    assert caught.value.kind == "timeout"
    assert caught.value.retryable


async def test_unreachable_host_is_unavailable(case) -> None:  # type: ignore[no-untyped-def]
    case.raise_on_chat(httpx.ConnectError("refused"))

    with pytest.raises(ProviderError) as caught:
        await case.provider.complete(case.model, MESSAGES)

    assert caught.value.kind == "unavailable"


async def test_streaming_error_status_is_classified(case) -> None:  # type: ignore[no-untyped-def]
    case.fail(429, {"error": {"message": "slow down", "type": "rate_limit_error"}})

    with pytest.raises(ProviderError) as caught:
        async for _ in case.provider.stream(case.model, MESSAGES):
            pass

    assert caught.value.kind in {"rate_limit", "quota"}
