"""Running the user's own Codex CLI on a run's worktree (task 4.3, spec §6.4).

Codex runs with its own sandbox in workspace-write mode, the network off and no approval
prompt; the task goes through stdin, never through argv. Only a bounded summary of each
JSONL event leaves the bridge: never command output, never reasoning."""

import json
import sys
import threading
from pathlib import Path

import pytest

from nfactory_bridge.codex_runtime import CodexRefused, codex_argv, run_codex, summarize


def test_codex_runs_sandboxed_without_network_or_prompts(tmp_path: Path) -> None:
    argv = codex_argv("codex", tmp_path)

    assert argv[:2] == ["codex", "exec"]
    assert "--json" in argv
    assert argv[argv.index("--sandbox") + 1] == "workspace-write"
    assert argv[argv.index("--cd") + 1] == str(tmp_path)
    assert "sandbox_workspace_write.network_access=false" in argv
    assert "approval_policy=never" in argv
    assert "--ignore-user-config" in argv  # predictable: defaults, the user's own login
    assert argv[-1] == "-"  # the task comes on stdin
    assert not any("danger" in arg or "bypass" in arg for arg in argv)


def test_a_batch_shim_never_receives_shell_metacharacters(tmp_path: Path) -> None:
    risky = tmp_path / "a&b"

    with pytest.raises(CodexRefused):
        codex_argv("C:/nodejs/codex.CMD", risky)
    assert codex_argv("C:/nodejs/codex.CMD", tmp_path)[0] == "C:/nodejs/codex.CMD"


@pytest.mark.parametrize(
    ("event", "summary"),
    [
        ({"type": "thread.started", "thread_id": "th_1"}, {"type": "started"}),
        (
            {"type": "item.completed", "item": {"type": "agent_message", "text": "Fait."}},
            {"type": "message", "text": "Fait."},
        ),
        (
            {
                "type": "item.started",
                "item": {
                    "type": "command_execution",
                    "command": "pytest -q",
                    "status": "in_progress",
                },
            },
            {"type": "command", "command": "pytest -q", "status": "in_progress"},
        ),
        (
            {
                "type": "item.completed",
                "item": {
                    "type": "command_execution",
                    "command": "pytest -q",
                    "aggregated_output": "secret output",
                    "exit_code": 1,
                    "status": "failed",
                },
            },
            {"type": "command", "command": "pytest -q", "status": "failed", "exit_code": 1},
        ),
        (
            {"type": "turn.completed", "usage": {"input_tokens": 120, "output_tokens": 30, "x": 1}},
            {"type": "completed", "usage": {"input_tokens": 120, "output_tokens": 30}},
        ),
        (
            {"type": "turn.failed", "error": {"message": "rate limited"}},
            {"type": "failed", "message": "rate limited"},
        ),
        ({"type": "error", "message": "boom"}, {"type": "error", "message": "boom"}),
    ],
)
def test_events_are_reduced_to_a_bounded_summary(
    event: dict, summary: dict, tmp_path: Path
) -> None:
    assert summarize(event, tmp_path) == summary


def test_file_changes_are_relative_to_the_worktree(tmp_path: Path) -> None:
    event = {
        "type": "item.completed",
        "item": {
            "type": "file_change",
            "changes": [
                {"path": str(tmp_path / "src" / "app.py"), "kind": "update"},
                {"path": "README.md", "kind": "add"},
            ],
            "status": "completed",
        },
    }

    assert summarize(event, tmp_path) == {
        "type": "file_change",
        "changes": [{"path": "src/app.py", "kind": "update"}, {"path": "README.md", "kind": "add"}],
    }


@pytest.mark.parametrize(
    "event",
    [
        {"type": "item.completed", "item": {"type": "reasoning", "text": "private thoughts"}},
        {"type": "turn.started"},
        {"type": "something.new", "payload": "x"},
        {"type": "item.updated", "item": {"type": "todo_list", "items": []}},
        "not an object",
    ],
)
def test_reasoning_and_unknown_events_never_leave_the_bridge(event: object, tmp_path: Path) -> None:
    assert summarize(event, tmp_path) is None


def test_long_texts_are_cut(tmp_path: Path) -> None:
    event = {"type": "item.completed", "item": {"type": "agent_message", "text": "a" * 10_000}}

    summary = summarize(event, tmp_path)

    assert summary is not None and len(summary["text"]) <= 2_001


FAKE_CODEX = """
import json, sys
task = sys.stdin.read()
print(json.dumps({"type": "thread.started", "thread_id": "t"}), flush=True)
print("not json", flush=True)
message = {"type": "agent_message", "text": "re\\u00e7u: " + task.strip()}
print(json.dumps({"type": "item.completed", "item": message}), flush=True)
print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 2}}),
      flush=True)
"""


def fake(tmp_path: Path, source: str) -> list[str]:
    script = tmp_path / "fake_codex.py"
    script.write_text(source, encoding="utf-8")
    return [sys.executable, str(script)]


def test_run_streams_the_summaries_and_returns_the_exit_code(tmp_path: Path) -> None:
    seen: list[dict] = []

    result = run_codex(fake(tmp_path, FAKE_CODEX), "Ajoute un test", tmp_path, seen.append)

    assert result.exit_code == 0
    assert [e["type"] for e in seen] == ["started", "message", "completed"]
    assert seen[1]["text"] == "reçu: Ajoute un test"


def test_a_failing_codex_reports_the_end_of_its_stderr(tmp_path: Path) -> None:
    source = "import sys; sys.stderr.write('Not logged in. Run codex login.'); sys.exit(1)"

    result = run_codex(fake(tmp_path, source), "x", tmp_path, lambda e: None)

    assert result.exit_code == 1
    assert "codex login" in result.stderr_tail


def test_cancel_stops_a_running_codex(tmp_path: Path) -> None:
    source = "import time, sys\nsys.stdin.read()\ntime.sleep(60)\n"
    cancel = threading.Event()
    timer = threading.Timer(0.5, cancel.set)
    timer.start()

    result = run_codex(fake(tmp_path, source), "x", tmp_path, lambda e: None, cancel=cancel)

    assert result.cancelled
    assert result.exit_code != 0


def test_a_codex_over_its_time_limit_is_stopped(tmp_path: Path) -> None:
    source = "import time, sys\nsys.stdin.read()\ntime.sleep(60)\n"

    result = run_codex(fake(tmp_path, source), "x", tmp_path, lambda e: None, timeout_s=0.5)

    assert result.timed_out


def test_events_are_parsed_line_by_line(tmp_path: Path) -> None:
    lines = [json.dumps({"type": "error", "message": f"m{i}"}) for i in range(3)]
    source = "import sys\nsys.stdin.read()\nprint(" + repr("\n".join(lines)) + ")\n"
    seen: list[dict] = []

    run_codex(fake(tmp_path, source), "x", tmp_path, seen.append)

    assert [e["message"] for e in seen] == ["m0", "m1", "m2"]


def test_a_non_fatal_error_item_is_a_warning(tmp_path: Path) -> None:
    event = {"type": "item.completed", "item": {"type": "error", "message": "option dépréciée"}}

    assert summarize(event, tmp_path) == {"type": "warning", "message": "option dépréciée"}


def test_on_windows_codex_gets_its_own_sandbox(tmp_path: Path) -> None:
    # Without it, workspace-write degrades to read-only on Windows (seen live).
    windows = codex_argv("codex", tmp_path, windows=True)
    other = codex_argv("codex", tmp_path, windows=False)

    assert windows[windows.index("--enable") + 1] == "experimental_windows_sandbox"
    assert "--enable" not in other
