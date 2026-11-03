# ruff: noqa: E501  (wire-format fixtures read best one per line)
"""Normalized provider errors (task 2.1).

A plain "429 means retry" rule is wrong for every provider: the cases below come from
the official docs (docs/research/providers.md) and pin each provider's own signals.
"""

import pytest

from nfactory_core.providers.errors import ProviderError, classify_http_error

CASES = [
    # (provider, status, body, headers, expected kind)
    ("openai_api", 401, {"error": {"type": "invalid_request_error"}}, {}, "auth"),
    ("openai_api", 429, {"error": {"code": "rate_limit_exceeded"}}, {"retry-after": "2"}, "rate_limit"),
    ("openai_api", 429, {"error": {"type": "insufficient_quota", "code": "credit_balance_exhausted"}}, {}, "quota"),
    ("openai_api", 429, {"error": {"code": "project_spend_limit_exceeded"}}, {}, "quota"),
    ("openai_api", 503, {"error": {"code": "server_is_overloaded"}}, {}, "unavailable"),
    ("openai_api", 404, {"error": {"code": "model_not_found"}}, {}, "not_found"),
    ("openai_api", 400, {"error": {"message": "bad"}}, {}, "bad_request"),
    ("anthropic_api", 429, {"type": "error", "error": {"type": "rate_limit_error"}}, {"retry-after": "5"}, "rate_limit"),
    ("anthropic_api", 429, {"error": {"type": "rate_limit_error", "details": {"error_code": "enforced_spend_limit_reached"}}}, {}, "quota"),
    ("anthropic_api", 400, {"error": {"type": "invalid_request_error", "message": "You have reached your specified API usage limits."}}, {}, "quota"),
    ("anthropic_api", 402, {"error": {"type": "billing_error"}}, {}, "quota"),
    ("anthropic_api", 529, {"error": {"type": "overloaded_error"}}, {}, "unavailable"),
    ("anthropic_api", 504, {"error": {"type": "timeout_error"}}, {}, "timeout"),
    ("deepseek_api", 402, {"error": {"message": "Insufficient Balance"}}, {}, "quota"),
    ("deepseek_api", 429, {"error": {"message": "Rate Limit Reached"}}, {}, "rate_limit"),
    ("zai_glm_api", 429, {"error": {"code": "1302", "message": "Rate limit reached"}}, {}, "rate_limit"),
    ("zai_glm_api", 429, {"error": {"code": "1113", "message": "Insufficient balance"}}, {}, "quota"),
    ("zai_glm_api", 429, {"error": {"code": "1310", "message": "limit exhausted"}}, {}, "quota"),
    ("zai_glm_api", 401, {"error": {"code": "1001"}}, {}, "auth"),
    ("moonshot_kimi_api", 429, {"error": {"type": "rate_limit_reached_error"}}, {}, "rate_limit"),
    ("moonshot_kimi_api", 429, {"error": {"type": "exceeded_current_quota_error"}}, {}, "quota"),
    ("moonshot_kimi_api", 429, {"error": {"type": "engine_overloaded_error"}}, {}, "unavailable"),
    # Qwen: "insufficient_quota" is a tokens-per-minute RATE limit, not a balance problem.
    ("qwen_api", 429, {"code": "Throttling.AllocationQuota", "message": "insufficient_quota"}, {}, "rate_limit"),
    ("qwen_api", 429, {"error": {"code": "insufficient_quota", "message": "Requests rate limit exceeded"}}, {}, "rate_limit"),
    ("qwen_api", 400, {"code": "Arrearage", "message": "Access denied, account is in arrears"}, {}, "quota"),
    ("qwen_api", 429, {"code": "PrepaidBillOverdue"}, {}, "quota"),
    ("qwen_api", 403, {"code": "AllocationQuota.FreeTierOnly"}, {}, "quota"),
    ("qwen_api", 429, {"code": "Throttling.AllocationQuota", "message": "Free allocated quota exceeded."}, {}, "quota"),
    ("minimax_api", 200, {"base_resp": {"status_code": 1008, "status_msg": "insufficient balance"}}, {}, "quota"),
    ("minimax_api", 200, {"base_resp": {"status_code": 1002, "status_msg": "rate limit"}}, {}, "rate_limit"),
    ("minimax_api", 200, {"base_resp": {"status_code": 2049, "status_msg": "invalid api key"}}, {}, "auth"),
    ("minimax_api", 200, {"base_resp": {"status_code": 2022}}, {}, "not_found"),
    ("ollama_local", 404, {"error": "model 'x' not found"}, {}, "not_found"),
    ("ollama_local", 500, {"error": "boom"}, {}, "unavailable"),
    ("custom_openai_compatible", 401, {}, {}, "auth"),
]  # fmt: skip


@pytest.mark.parametrize(("provider", "status", "body", "headers", "kind"), CASES)
def test_each_provider_signal_maps_to_the_right_kind(
    provider: str, status: int, body: dict, headers: dict, kind: str
) -> None:
    error = classify_http_error(provider, status, body, headers)
    assert error.kind == kind
    assert error.provider == provider


def test_only_transient_failures_are_retryable() -> None:
    assert ProviderError("rate_limit", provider="openai_api").retryable
    assert ProviderError("unavailable", provider="openai_api").retryable
    assert ProviderError("timeout", provider="openai_api").retryable
    for kind in ("auth", "quota", "bad_request", "not_found", "unsupported", "invalid_response"):
        assert not ProviderError(kind, provider="openai_api").retryable  # type: ignore[arg-type]


def test_retry_after_is_read_from_the_headers() -> None:
    error = classify_http_error("openai_api", 429, {}, {"retry-after": "7"})
    assert error.retry_after == 7.0


def test_message_is_french_and_names_the_provider() -> None:
    error = classify_http_error("deepseek_api", 402, {}, {})
    assert "DeepSeek" in error.message
    assert "crédit" in error.message.lower() or "quota" in error.message.lower()


def test_provider_detail_never_carries_a_key() -> None:
    body = {"error": {"message": "Incorrect API key provided: sk-abcdefghijklmnopqrstuvwxyz123456"}}
    error = classify_http_error("openai_api", 401, body, {})
    assert "sk-abcdefghijklmnop" not in error.detail
    assert "sk-abcdefghijklmnop" not in str(error)
