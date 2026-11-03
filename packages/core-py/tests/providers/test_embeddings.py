"""Embedding endpoints (task 3.3): OpenAI-compatible `/embeddings`, Ollama `/api/embed`.

Facts: https://platform.openai.com/docs/api-reference/embeddings/create and
https://docs.ollama.com/api/embed (docs/research/providers.md, "Embeddings").
"""

import json

import httpx
import pytest
import respx

from nfactory_core.providers import SPECS, ProviderError, build_provider

KEY = "sk-embed-test-0123456789abcdefghij"


@respx.mock
async def test_openai_embeddings_come_back_in_input_order() -> None:
    route = respx.post("https://api.openai.com/v1/embeddings").mock(
        return_value=httpx.Response(
            200,
            json={
                "object": "list",
                "data": [  # out of order on purpose: `index` decides
                    {"object": "embedding", "index": 1, "embedding": [0.0, 1.0]},
                    {"object": "embedding", "index": 0, "embedding": [1.0, 0.0]},
                ],
                "model": "embed-x",
                "usage": {"prompt_tokens": 7, "total_tokens": 7},
            },
        )
    )
    provider = build_provider("openai_api", base_url="https://api.openai.com/v1", api_key=KEY)

    result = await provider.embed("embed-x", ["un", "deux"])  # type: ignore[attr-defined]

    assert result.vectors == [[1.0, 0.0], [0.0, 1.0]]
    assert result.usage.input_tokens == 7
    sent = json.loads(route.calls[0].request.content)
    assert sent == {"model": "embed-x", "input": ["un", "deux"], "encoding_format": "float"}
    assert route.calls[0].request.headers["authorization"] == f"Bearer {KEY}"


@respx.mock
async def test_ollama_embeddings_use_the_native_endpoint() -> None:
    route = respx.post("http://127.0.0.1:11434/api/embed").mock(
        return_value=httpx.Response(
            200,
            json={"model": "nomic", "embeddings": [[0.5, 0.5], [0.1, 0.9]], "prompt_eval_count": 4},
        )
    )
    provider = build_provider("ollama_local", base_url="http://127.0.0.1:11434", api_key=None)

    result = await provider.embed("nomic", ["a", "b"])  # type: ignore[attr-defined]

    assert result.vectors == [[0.5, 0.5], [0.1, 0.9]]
    assert result.usage.input_tokens == 4
    assert json.loads(route.calls[0].request.content) == {"model": "nomic", "input": ["a", "b"]}


@respx.mock
async def test_embedding_errors_are_normalized() -> None:
    respx.post("https://api.openai.com/v1/embeddings").mock(
        return_value=httpx.Response(401, json={"error": {"message": "bad key"}})
    )
    provider = build_provider("openai_api", base_url="https://api.openai.com/v1", api_key=KEY)

    with pytest.raises(ProviderError) as caught:
        await provider.embed("embed-x", ["a"])  # type: ignore[attr-defined]

    assert caught.value.kind == "auth"


@respx.mock
async def test_a_short_answer_is_an_invalid_response() -> None:
    respx.post("https://api.openai.com/v1/embeddings").mock(
        return_value=httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0]}]})
    )
    provider = build_provider("openai_api", base_url="https://api.openai.com/v1", api_key=KEY)

    with pytest.raises(ProviderError) as caught:
        await provider.embed("embed-x", ["a", "b"])  # type: ignore[attr-defined]

    assert caught.value.kind == "invalid_response"


def test_only_verified_embedding_apis_are_offered() -> None:
    offered = {kind for kind, spec in SPECS.items() if spec.embeddings}

    assert offered == {"openai_api", "custom_openai_compatible", "ollama_local"}
