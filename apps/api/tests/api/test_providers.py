"""AI Providers API (tasks 2.6, 2.7, 2.9): honest statuses, keys never returned.

Provider servers are mocked with respx; only a successful test makes a provider
"connected".
"""

import httpx
import pytest
import respx
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from nfactory_core.models import ProviderConnection, StoredSecret

pytestmark = pytest.mark.integration

KEY = "sk-provider-test-0123456789abcdefghijkl"
OPENAI = "https://api.openai.com/v1"
ZAI = "https://api.z.ai/api/paas/v4"


async def configure(client: AsyncClient, kind: str, **body: object) -> httpx.Response:
    return await client.put(f"/api/v1/providers/{kind}/configuration", json=body)


async def test_every_provider_is_listed_unconfigured_and_coding_agents_wait_for_phase_4(
    provider_client: AsyncClient,
) -> None:
    body = (await provider_client.get("/api/v1/providers")).json()

    kinds = {p["kind"]: p for p in body["providers"]}
    chat = {"openai_api", "anthropic_api", "deepseek_api", "zai_glm_api", "moonshot_kimi_api"}
    chat |= {"qwen_api", "minimax_api", "custom_openai_compatible", "ollama_local"}
    assert chat <= set(kinds)
    assert all(kinds[k]["status"] == "not_configured" for k in kinds)
    assert kinds["codex_local"]["available"] is False
    assert kinds["codex_local"]["phase"] == 4
    assert [r["id"] for r in kinds["moonshot_kimi_api"]["regions"]] == ["intl", "cn"]
    assert kinds["ollama_local"]["base_url"] == "http://127.0.0.1:11434"  # server default
    qwen = {r["id"]: r["needs_workspace"] for r in kinds["qwen_api"]["regions"]}
    assert qwen["eu-central-1"] is True and qwen["legacy-intl"] is False


async def test_each_provider_and_region_says_where_it_processes_data(
    provider_client: AsyncClient,
) -> None:
    body = (await provider_client.get("/api/v1/providers")).json()
    views = {p["kind"]: p for p in body["providers"]}

    assert views["openai_api"]["residency"]["zone"] == "outside_eu"
    assert views["openai_api"]["residency"]["source"].startswith("https://")
    assert views["ollama_local"]["residency"]["zone"] == "local"
    assert views["custom_openai_compatible"]["residency"]["zone"] == "unknown"
    frankfurt = next(r for r in views["qwen_api"]["regions"] if r["id"] == "eu-central-1")
    assert (frankfurt["zone"], frankfurt["country"]) == ("eu", "Allemagne")

    await configure(
        provider_client, "qwen_api", api_key=KEY, region="eu-central-1", workspace_id="ws-abc123"
    )
    saved = {
        p["kind"]: p for p in (await provider_client.get("/api/v1/providers")).json()["providers"]
    }
    assert saved["qwen_api"]["residency"]["country"] == "Allemagne"


async def test_a_saved_key_is_encrypted_never_returned_and_not_yet_connected(
    provider_client: AsyncClient, migrated_database_url: str
) -> None:
    response = await configure(provider_client, "openai_api", api_key=KEY)

    assert response.status_code == 200
    assert KEY not in response.text
    view = response.json()
    assert view["status"] == "configured"  # saved, not tested: never "connected"
    assert view["key_source"] == "stored"
    assert KEY not in (await provider_client.get("/api/v1/providers")).text

    engine = create_async_engine(migrated_database_url)
    async with engine.connect() as conn:
        ref = await conn.scalar(
            select(ProviderConnection.secret_ref).where(ProviderConnection.kind == "openai_api")
        )
        ciphertext = await conn.scalar(select(StoredSecret.ciphertext))
    await engine.dispose()
    assert ref is not None and ref.startswith("db:")
    assert ciphertext is not None and KEY.encode() not in ciphertext


@respx.mock
async def test_successful_test_connects_and_fills_the_catalog(
    provider_client: AsyncClient,
) -> None:
    respx.get(f"{OPENAI}/models").mock(
        return_value=httpx.Response(200, json={"data": [{"id": "model-x"}, {"id": "model-y"}]})
    )
    await configure(provider_client, "openai_api", api_key=KEY)

    result = (await provider_client.post("/api/v1/providers/openai_api/validate")).json()

    assert result["ok"] is True
    assert result["status"] == "connected"
    assert result["models_found"] == 2
    assert respx.calls.last.request.headers["authorization"] == f"Bearer {KEY}"
    models = (await provider_client.get("/api/v1/providers/openai_api/models")).json()
    assert [(m["model_id"], m["source"]) for m in models["models"]] == [
        ("model-x", "discovered"),
        ("model-y", "discovered"),
    ]


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (401, {"error": {"message": "bad key"}}, "invalid_credentials"),
        (429, {"error": {"code": "credit_balance_exhausted"}}, "quota_exceeded"),
        (503, {"error": {"code": "server_is_overloaded"}}, "unreachable"),
    ],
)
@respx.mock
async def test_failed_test_gives_an_honest_status_and_a_french_reason(
    provider_client: AsyncClient, status: int, body: dict, expected: str
) -> None:
    respx.get(f"{OPENAI}/models").mock(return_value=httpx.Response(status, json=body))
    await configure(provider_client, "openai_api", api_key=KEY)

    result = (await provider_client.post("/api/v1/providers/openai_api/validate")).json()

    assert result["ok"] is False
    assert result["status"] == expected
    listed = {
        p["kind"]: p for p in (await provider_client.get("/api/v1/providers")).json()["providers"]
    }
    assert listed["openai_api"]["status"] == expected
    assert listed["openai_api"]["last_error"]["message"].startswith("OpenAI :")


@respx.mock
async def test_provider_without_discovery_needs_a_catalog_model_then_probes_it(
    provider_client: AsyncClient,
) -> None:
    probe = respx.post(f"{ZAI}/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "model": "glm-x",
                "choices": [{"message": {"content": "pong"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )
    )
    await configure(provider_client, "zai_glm_api", api_key=KEY, region="intl")

    first = (await provider_client.post("/api/v1/providers/zai_glm_api/validate")).json()
    assert first["status"] == "needs_model"
    assert "catalogue" in first["message"]

    added = await provider_client.put(
        "/api/v1/providers/zai_glm_api/models/glm-x",
        json={"pricing": {"input_per_mtok": 0.5, "output_per_mtok": 2}},
    )
    assert added.status_code == 200
    second = (await provider_client.post("/api/v1/providers/zai_glm_api/validate")).json()
    assert second["status"] == "connected"
    assert probe.called
    models = (await provider_client.get("/api/v1/providers/zai_glm_api/models")).json()["models"]
    assert models == [
        {
            "model_id": "glm-x",
            "source": "manual",
            "pricing": {
                "input_per_mtok": 0.5,
                "output_per_mtok": 2.0,
                "cached_input_per_mtok": None,
            },
            "context_window": None,
        }
    ]


async def test_custom_endpoint_on_a_private_network_is_refused(
    provider_client: AsyncClient,
) -> None:
    response = await configure(
        provider_client, "custom_openai_compatible", base_url="https://intranet.corp/v1"
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsafe_base_url"


async def test_qwen_needs_a_valid_workspace_id(provider_client: AsyncClient) -> None:
    response = await configure(provider_client, "qwen_api", api_key=KEY, region="eu-central-1")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_provider_config"

    ok = await configure(
        provider_client, "qwen_api", api_key=KEY, region="eu-central-1", workspace_id="ws-abc123"
    )
    assert ok.status_code == 200
    assert (
        ok.json()["base_url"]
        == "https://ws-abc123.eu-central-1.maas.aliyuncs.com/compatible-mode/v1"
    )


async def test_a_key_from_the_environment_is_referenced_not_copied(
    provider_client: AsyncClient, monkeypatch: pytest.MonkeyPatch, migrated_database_url: str
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", KEY)

    listed = {
        p["kind"]: p for p in (await provider_client.get("/api/v1/providers")).json()["providers"]
    }
    assert listed["deepseek_api"]["env_key_available"] is True

    view = (await configure(provider_client, "deepseek_api", use_env_key=True)).json()
    assert view["key_source"] == "env"
    engine = create_async_engine(migrated_database_url)
    async with engine.connect() as conn:
        ref = await conn.scalar(
            select(ProviderConnection.secret_ref).where(ProviderConnection.kind == "deepseek_api")
        )
    await engine.dispose()
    assert ref == "env:DEEPSEEK_API_KEY"


async def test_coding_agents_cannot_be_configured_here(provider_client: AsyncClient) -> None:
    response = await configure(provider_client, "codex_local")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "provider_unavailable"


async def test_removing_a_connection_forgets_its_key(
    provider_client: AsyncClient, migrated_database_url: str
) -> None:
    await configure(provider_client, "openai_api", api_key=KEY)

    response = await provider_client.delete("/api/v1/providers/openai_api/configuration")

    assert response.status_code == 200
    assert response.json()["status"] == "not_configured"
    engine = create_async_engine(migrated_database_url)
    async with engine.connect() as conn:
        assert await conn.scalar(select(StoredSecret.id)) is None
    await engine.dispose()


async def test_catalog_model_can_be_removed(provider_client: AsyncClient) -> None:
    await provider_client.put("/api/v1/providers/ollama_local/models/llama-test", json={})

    removed = await provider_client.delete("/api/v1/providers/ollama_local/models/llama-test")

    assert removed.status_code == 200
    assert (await provider_client.get("/api/v1/providers/ollama_local/models")).json()[
        "models"
    ] == []
