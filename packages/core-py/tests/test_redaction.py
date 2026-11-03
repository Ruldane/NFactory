from nfactory_core.events import REDACTED, redact


def test_masks_values_under_sensitive_keys() -> None:
    payload = {"api_key": "abc", "Authorization": "x", "github_token": "y", "password": "z"}
    assert redact(payload) == {k: REDACTED for k in payload}


def test_masks_secret_looking_values_inside_text() -> None:
    text = "appel avec sk-proj-AbCdEfGhIjKlMnOpQrSt et ghp_0123456789abcdefABCDEF01"
    out = redact({"log": text})["log"]
    assert "sk-proj" not in out
    assert "ghp_" not in out
    assert out.count(REDACTED) == 2


def test_masks_bearer_tokens() -> None:
    assert redact("Bearer eyJhbGciOiJIUzI1NiJ9.payload") == REDACTED


def test_recurses_into_nested_lists_and_dicts() -> None:
    payload = {"calls": [{"headers": {"x-api-key": "secret"}, "status": 200}]}
    assert redact(payload) == {"calls": [{"headers": {"x-api-key": REDACTED}, "status": 200}]}


def test_leaves_harmless_data_untouched() -> None:
    payload = {"agent": "builder", "duration_ms": 18400, "artifacts": ["app/main.py"], "ok": True}
    assert redact(payload) == payload


def test_does_not_mutate_input() -> None:
    payload = {"token": "t"}
    redact(payload)
    assert payload == {"token": "t"}
