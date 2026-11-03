"""doctor.py must report tool status without ever echoing credentials (spec §17.2)."""

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "doctor", Path(__file__).resolve().parent.parent / "doctor.py"
)
assert _spec and _spec.loader
doctor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(doctor)


def runner(outputs: dict[str, tuple[int, str]]):
    def run(cmd: list[str]) -> tuple[int, str]:
        return outputs.get(cmd[0], (127, ""))

    return run


def test_missing_tool_is_reported_as_missing() -> None:
    result = doctor.check_tool("codex", ["codex", "--version"], run=runner({}))
    assert result.status == "missing"


def test_installed_tool_reports_first_version_line() -> None:
    run = runner({"claude": (0, "2.1.316 (Claude Code)\nextra")})
    result = doctor.check_tool("claude", ["claude", "--version"], run=run)
    assert (result.status, result.detail) == ("ok", "2.1.316 (Claude Code)")


def test_gh_auth_never_leaks_the_token() -> None:
    output = (
        "github.com\n  ✓ Logged in to github.com account me\n  - Token: gho_SECRETSECRETSECRET1234"
    )
    result = doctor.check_gh_auth(run=runner({"gh": (0, output)}))

    assert result.status == "ok"
    assert "gho_" not in result.detail
    assert "SECRET" not in result.detail


def test_gh_logged_out_is_a_warning_with_the_fix() -> None:
    run = runner({"gh": (1, "You are not logged into any GitHub hosts.")})
    result = doctor.check_gh_auth(run=run)
    assert result.status == "warn"
    assert "gh auth login" in result.detail


def test_api_key_presence_is_reported_without_value() -> None:
    result = doctor.check_api_keys({"OPENAI_API_KEY": "sk-live-123", "ANTHROPIC_API_KEY": ""})
    assert "OPENAI_API_KEY" in result.detail
    assert "sk-live" not in result.detail
