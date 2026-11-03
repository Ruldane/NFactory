"""The user's own Codex CLI, run on a run's worktree (task 4.3, spec §6.4). Standard library.

`codex exec --json` runs one task non-interactively under Codex's own sandbox:
workspace-write (it may edit the worktree only), network off, no approval prompt. The task
goes through stdin, so no text from NFactory becomes an argument. Each JSONL event is
reduced by `summarize` to a few bounded fields; command output and reasoning stay on the
machine. Codex's own session and login are used as they are: nothing here reads them.

Interface: codex_argv, run_codex, summarize, CodexResult, CodexRefused.
"""

import json
import os
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TIMEOUT_S = 1_800
_TEXT_MAX = 2_000
_COMMAND_MAX = 300
_STDERR_TAIL = 2_000
# cmd.exe interprets these in the arguments of a .cmd / .bat shim (npm installs one).
_BATCH_UNSAFE = set('&|<>^%"\r\n')

Summary = dict[str, Any]


class CodexRefused(ValueError):
    """Codex cannot be started safely with these arguments."""


@dataclass(frozen=True)
class CodexResult:
    exit_code: int
    stderr_tail: str = ""
    cancelled: bool = False
    timed_out: bool = False


def codex_argv(codex: str, worktree: Path, *, windows: bool = os.name == "nt") -> list[str]:
    argv = [
        codex,
        "exec",
        "--json",
        "--color",
        "never",
        "--sandbox",
        "workspace-write",
        "-c",
        "sandbox_workspace_write.network_access=false",
        "-c",
        "approval_policy=never",
        "--ephemeral",
        # The user's config.toml may pick a model or features exec cannot use; Codex keeps
        # the user's own login (CODEX_HOME) either way.
        "--ignore-user-config",
        "--cd",
        str(worktree),
        "-",
    ]
    if windows:
        # Without its Windows sandbox, Codex runs workspace-write as read-only.
        argv[-1:-1] = ["--enable", "experimental_windows_sandbox"]
    if codex.lower().endswith((".cmd", ".bat")) and any(set(a) & _BATCH_UNSAFE for a in argv):
        raise CodexRefused("Chemin de travail incompatible avec le lanceur codex.cmd.")
    return argv


def summarize(event: object, worktree: Path) -> Summary | None:
    """The few fields of a Codex event the dashboard shows; None for everything else."""
    if not isinstance(event, dict):
        return None
    kind = event.get("type")
    if kind == "thread.started":
        return {"type": "started"}
    if kind == "turn.completed":
        usage = _dict(event.get("usage"))
        kept = {k: v for k, v in usage.items() if k.endswith("_tokens") and isinstance(v, int)}
        return {"type": "completed", "usage": kept}
    if kind == "turn.failed":
        error = _dict(event.get("error"))
        return {"type": "failed", "message": _cut(error.get("message"), 500)}
    if kind == "error":
        return {"type": "error", "message": _cut(event.get("message"), 500)}
    if kind in ("item.started", "item.completed") and isinstance(event.get("item"), dict):
        return _item(event["item"], completed=kind == "item.completed", worktree=worktree)
    return None


def _item(item: dict[str, Any], *, completed: bool, worktree: Path) -> Summary | None:
    kind = item.get("type")
    if kind == "agent_message" and completed:
        return {"type": "message", "text": _cut(item.get("text"), _TEXT_MAX)}
    if kind == "command_execution":
        summary: Summary = {
            "type": "command",
            "command": _cut(item.get("command"), _COMMAND_MAX),
            "status": _cut(item.get("status"), 20),
        }
        if completed and isinstance(item.get("exit_code"), int):
            summary["exit_code"] = item["exit_code"]
        return summary
    if kind == "file_change" and completed:
        changes = item.get("changes")
        changes = changes if isinstance(changes, list) else []
        return {
            "type": "file_change",
            "changes": [
                {"path": _relative(c.get("path"), worktree), "kind": _cut(c.get("kind"), 10)}
                for c in changes[:200]
                if isinstance(c, dict)
            ],
        }
    if kind == "error":
        return {"type": "warning", "message": _cut(item.get("message"), 500)}  # not fatal
    return None


def run_codex(
    argv: list[str],
    task: str,
    worktree: Path,
    on_event: Callable[[Summary], None],
    *,
    cancel: threading.Event | None = None,
    timeout_s: float = TIMEOUT_S,
) -> CodexResult:
    """Run Codex to its end, feeding `on_event` one summary per JSONL event."""
    process = subprocess.Popen(  # noqa: S603 - argv from codex_argv only
        argv,
        cwd=worktree,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
    )
    stop = cancel or threading.Event()
    reasons: list[str] = []
    stderr: list[str] = []

    def watchdog() -> None:
        if not stop.wait(timeout_s):
            reasons.append("timeout")
        elif process.poll() is None:
            reasons.append("cancel")
        _kill(process)

    def drain_stderr() -> None:
        assert process.stderr is not None
        for line in process.stderr:
            stderr.append(line)
            del stderr[:-50]

    threading.Thread(target=watchdog, daemon=True).start()
    reader = threading.Thread(target=drain_stderr, daemon=True)
    reader.start()
    assert process.stdin is not None and process.stdout is not None
    try:
        process.stdin.write(task)
        process.stdin.close()
    except OSError:
        pass  # Codex ended before reading its task; its exit code tells why
    for line in process.stdout:
        try:
            summary = summarize(json.loads(line), worktree)
        except ValueError:
            continue
        if summary is not None:
            on_event(summary)
    code = process.wait()
    stop.set()
    reader.join(timeout=5)
    return CodexResult(
        exit_code=code,
        stderr_tail="".join(stderr)[-_STDERR_TAIL:],
        cancelled="cancel" in reasons,
        timed_out="timeout" in reasons,
    )


def _kill(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        # Codex starts child processes: end the whole tree, not only the shim.
        subprocess.run(  # noqa: S603 - fixed argv
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],  # noqa: S607
            capture_output=True,
            check=False,
        )
    process.kill()


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _cut(value: object, limit: int) -> str:
    text = value if isinstance(value, str) else ""
    return text if len(text) <= limit else text[:limit] + "…"


def _relative(path: object, worktree: Path) -> str:
    text = path if isinstance(path, str) else ""
    try:
        return (worktree / text).resolve().relative_to(worktree.resolve()).as_posix()
    except ValueError:
        return _cut(text.replace("\\", "/"), 300)
