"""Detection of the local coding tools through their public commands only: version and
login status. No auth file is ever opened, and no raw output leaves the bridge."""

import json
import subprocess
from typing import Any

from nfactory_bridge.detection import Completed, detect

PATHS = {"codex": "C:/bin/codex.exe", "claude": "C:/bin/claude.cmd", "gh": "C:/bin/gh.exe"}
CLAUDE_STATUS = {
    "loggedIn": True,
    "authMethod": "claude.ai",
    "email": "someone@example.com",
    "orgId": "org-123",
    "orgName": "Example",
    "subscriptionType": "max",
}


class FakeTools:
    def __init__(self, answers: dict[tuple[str, ...], Any], installed: set[str] | None = None):
        self.answers = answers
        self.installed = installed if installed is not None else set(PATHS)
        self.calls: list[list[str]] = []

    def which(self, name: str) -> str | None:
        return PATHS[name] if name in self.installed else None

    def run(self, argv: list[str], timeout_s: float) -> Completed:
        self.calls.append(argv)
        name = next(k for k, v in PATHS.items() if v == argv[0])
        answer = self.answers[(name, *argv[1:])]
        if isinstance(answer, Exception):
            raise answer
        return answer


def connected_tools() -> FakeTools:
    return FakeTools(
        {
            ("codex", "--version"): Completed(0, "codex-cli 0.155.1\n"),
            ("codex", "login", "status"): Completed(0, "Logged in using ChatGPT\n"),
            ("claude", "--version"): Completed(0, "2.1.316 (Claude Code)\n"),
            ("claude", "auth", "status", "--json"): Completed(0, json.dumps(CLAUDE_STATUS)),
            ("gh", "--version"): Completed(0, "gh version 2.60.1 (2024-10-16)\nhttps://x\n"),
            ("gh", "auth", "status"): Completed(0, "Logged in to github.com account someone\n"),
        }
    )


def by_kind(tools: FakeTools) -> dict[str, dict[str, Any]]:
    return {r["kind"]: r for r in detect(which=tools.which, run=tools.run)}


def test_connected_tools_with_their_versions() -> None:
    found = by_kind(connected_tools())

    assert found["codex"]["status"] == "connected"
    assert found["codex"]["version"] == "0.155.1"
    assert found["codex"]["login"] == "chatgpt"
    assert found["claude"]["status"] == "connected"
    assert found["claude"]["version"] == "2.1.316"
    assert found["gh"]["status"] == "connected"
    assert found["gh"]["version"] == "2.60.1"


def test_no_account_detail_or_raw_output_leaves_the_bridge() -> None:
    sent = json.dumps(detect(which=connected_tools().which, run=connected_tools().run))

    for private in ("someone", "example.com", "org-123", "Example", "max", "Logged in"):
        assert private not in sent


def test_a_missing_tool_is_not_installed_and_never_run() -> None:
    tools = connected_tools()
    tools.installed = {"codex"}

    found = by_kind(tools)

    assert found["claude"]["status"] == "not_installed"
    assert found["gh"]["status"] == "not_installed" and found["gh"]["version"] is None
    assert all(call[0] == PATHS["codex"] for call in tools.calls)


def test_logged_out_tools_need_a_login_with_their_official_command() -> None:
    tools = connected_tools()
    tools.answers[("codex", "login", "status")] = Completed(1, "Not logged in\n")
    tools.answers[("claude", "auth", "status", "--json")] = Completed(
        1, json.dumps({"loggedIn": False})
    )
    tools.answers[("gh", "auth", "status")] = Completed(1, "You are not logged in\n")

    found = by_kind(tools)

    assert {r["status"] for r in found.values()} == {"needs_login"}
    assert found["codex"]["login_command"] == "codex login"
    assert found["claude"]["login_command"] == "claude auth login"
    assert found["gh"]["login_command"] == "gh auth login"


def test_codex_with_an_api_key_says_so() -> None:
    tools = connected_tools()
    tools.answers[("codex", "login", "status")] = Completed(0, "Logged in using an API key\n")

    assert by_kind(tools)["codex"]["login"] == "api_key"


def test_claude_code_is_handoff_only_until_its_runtime_is_cleared() -> None:
    # Spec §6.5: driving Claude Code programmatically on a subscription waits for a
    # compliance check; the handoff (the user runs the official binary) is available.
    claude = by_kind(connected_tools())["claude"]

    assert claude["modes"] == {"handoff": "available", "runtime": "blocked_by_policy"}


def test_a_status_that_hangs_leaves_the_tool_installed_with_a_reason() -> None:
    tools = connected_tools()
    tools.answers[("codex", "login", "status")] = subprocess.TimeoutExpired("codex", 10)

    codex = by_kind(tools)["codex"]

    assert codex["status"] == "installed"
    assert codex["version"] == "0.155.1"
    assert "délai" in codex["detail"]


def test_unreadable_claude_status_is_not_taken_for_a_login() -> None:
    tools = connected_tools()
    tools.answers[("claude", "auth", "status", "--json")] = Completed(0, "not json")

    assert by_kind(tools)["claude"]["status"] == "installed"


def test_only_fixed_public_commands_are_run() -> None:
    tools = connected_tools()
    detect(which=tools.which, run=tools.run)

    assert sorted(tuple(c[1:]) for c in tools.calls) == sorted(
        [
            ("--version",),
            ("login", "status"),
            ("--version",),
            ("auth", "status", "--json"),
            ("--version",),
            ("auth", "status"),
        ]
    )


def test_a_status_printed_on_stderr_is_read_too() -> None:
    # codex (and gh) print their login status on stderr, not stdout.
    tools = connected_tools()
    tools.answers[("codex", "login", "status")] = Completed(0, "", "Logged in using ChatGPT\n")

    assert by_kind(tools)["codex"]["login"] == "chatgpt"
