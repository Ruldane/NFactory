"""Coding tasks on an authorized repository (tasks 4.3 and 4.5): a worktree per task, the
user's Codex run there in the background, then a manifest and a diff. Fake Codex, real git."""

import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from nfactory_bridge.codex_runtime import CodexResult
from nfactory_bridge.repos import RepoRegistry
from nfactory_bridge.tasks import TaskRefused, Tasks


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "nfactory-test"
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.name", "Someone")
    git(path, "config", "user.email", "someone@example.com")
    (path / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-q", "-m", "initial")
    return path


Runner = Callable[..., CodexResult]


def editing_codex(content: str, exit_code: int = 0) -> Runner:
    """A fake Codex that edits calc.py in the worktree it is given."""

    def run(argv: list[str], task: str, worktree: Path, on_event, **kwargs) -> CodexResult:
        on_event({"type": "started"})
        (worktree / "calc.py").write_text(content, encoding="utf-8")
        on_event({"type": "file_change", "changes": [{"path": "calc.py", "kind": "update"}]})
        on_event({"type": "message", "text": "Fonction ajoutée."})
        return CodexResult(exit_code=exit_code, stderr_tail="" if exit_code == 0 else "boom")

    return run


def make_tasks(tmp_path: Path, repo: Path, runner: Runner, ready: str | None = "codex") -> Tasks:
    registry = RepoRegistry(tmp_path / "profile" / "repos.json")
    registry.allow(repo)

    def codex() -> str:
        if ready is None:
            raise TaskRefused("needs_login", "Codex n'est pas connecté : lancez codex login.")
        return ready

    return Tasks(registry, tmp_path / "profile" / "worktrees", codex=codex, runner=runner)


def wait_done(tasks: Tasks, task_id: str) -> dict:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        view = tasks.get(task_id)
        if view["status"] not in ("preparing", "running"):
            return view
        time.sleep(0.05)
    raise AssertionError("task did not finish")


DOUBLE = "def add(a, b):\n    return a + b\n\n\ndef double(x):\n    return 2 * x\n"


def test_a_codex_task_ends_with_its_events_manifest_and_diff(tmp_path: Path, repo: Path) -> None:
    tasks = make_tasks(tmp_path, repo, editing_codex(DOUBLE))

    started = tasks.start_codex("nfactory-test", "Ajoute une fonction double")
    done = wait_done(tasks, started["id"])

    assert done["status"] == "succeeded"
    assert done["branch"] == f"nfactory/nfactory-test/{started['id']}"
    assert [e["type"] for e in done["events"]] == ["started", "file_change", "message"]
    assert done["manifest"] == [{"path": "calc.py", "change": "modified"}]
    assert "+def double(x):" in done["diff"]
    assert git(repo, "status", "--porcelain") == ""  # the user's checkout is untouched


def test_the_task_reaches_codex_inside_nfactory_rules(tmp_path: Path, repo: Path) -> None:
    seen: dict = {}

    def spy(argv, task, worktree, on_event, **kwargs) -> CodexResult:
        seen.update(argv=argv, task=task, worktree=worktree)
        return CodexResult(exit_code=0)

    tasks = make_tasks(tmp_path, repo, spy)
    started = tasks.start_codex("nfactory-test", "Ajoute une fonction double")
    wait_done(tasks, started["id"])

    assert "Ajoute une fonction double" in seen["task"]
    assert "commit" in seen["task"]  # the rules tell Codex not to commit or push
    assert seen["argv"][seen["argv"].index("--cd") + 1] == str(seen["worktree"])
    assert seen["worktree"] != repo


def test_a_failing_codex_marks_the_task_failed_with_its_reason(tmp_path: Path, repo: Path) -> None:
    tasks = make_tasks(tmp_path, repo, editing_codex(DOUBLE, exit_code=1))

    done = wait_done(tasks, tasks.start_codex("nfactory-test", "x")["id"])

    assert done["status"] == "failed"
    assert "boom" in done["error"]


def test_codex_not_logged_in_is_refused_before_anything_starts(tmp_path: Path, repo: Path) -> None:
    tasks = make_tasks(tmp_path, repo, editing_codex(DOUBLE), ready=None)

    with pytest.raises(TaskRefused) as refused:
        tasks.start_codex("nfactory-test", "x")

    assert refused.value.code == "needs_login"
    assert "nfactory/" not in git(repo, "branch", "--list")


def test_an_unauthorized_repository_is_refused(tmp_path: Path, repo: Path) -> None:
    tasks = make_tasks(tmp_path, repo, editing_codex(DOUBLE))

    with pytest.raises(TaskRefused) as refused:
        tasks.start_codex("other-repo", "x")

    assert refused.value.code == "repo_not_allowed"


@pytest.mark.parametrize("task", ["", "   ", "x" * 4_001])
def test_the_task_text_is_bounded(tmp_path: Path, repo: Path, task: str) -> None:
    tasks = make_tasks(tmp_path, repo, editing_codex(DOUBLE))

    with pytest.raises(TaskRefused):
        tasks.start_codex("nfactory-test", task)


def test_one_task_at_a_time(tmp_path: Path, repo: Path) -> None:
    release = threading.Event()

    def slow(argv, task, worktree, on_event, **kwargs) -> CodexResult:
        release.wait(10)
        return CodexResult(exit_code=0)

    tasks = make_tasks(tmp_path, repo, slow)
    first = tasks.start_codex("nfactory-test", "x")

    with pytest.raises(TaskRefused) as refused:
        tasks.start_codex("nfactory-test", "y")
    release.set()
    wait_done(tasks, first["id"])

    assert refused.value.code == "busy"


def test_cancel_reaches_the_running_codex(tmp_path: Path, repo: Path) -> None:
    def waits(argv, task, worktree, on_event, *, cancel, **kwargs) -> CodexResult:
        cancel.wait(10)
        return CodexResult(exit_code=1, cancelled=True)

    tasks = make_tasks(tmp_path, repo, waits)
    started = tasks.start_codex("nfactory-test", "x")

    tasks.cancel(started["id"])

    assert wait_done(tasks, started["id"])["status"] == "cancelled"


def test_discard_removes_the_worktree_and_branch(tmp_path: Path, repo: Path) -> None:
    tasks = make_tasks(tmp_path, repo, editing_codex(DOUBLE))
    done = wait_done(tasks, tasks.start_codex("nfactory-test", "x")["id"])

    tasks.discard(done["id"])

    assert "nfactory/" not in git(repo, "branch", "--list")
    assert tasks.get(done["id"])["status"] == "discarded"


def test_an_unknown_task_is_refused(tmp_path: Path, repo: Path) -> None:
    tasks = make_tasks(tmp_path, repo, editing_codex(DOUBLE))

    with pytest.raises(TaskRefused) as refused:
        tasks.get("t_nope")

    assert refused.value.code == "not_found"


def test_a_crash_in_the_runner_fails_the_task_cleanly(tmp_path: Path, repo: Path) -> None:
    def crashes(*args, **kwargs) -> CodexResult:
        raise OSError("codex introuvable")

    tasks = make_tasks(tmp_path, repo, crashes)

    done = wait_done(tasks, tasks.start_codex("nfactory-test", "x")["id"])

    assert done["status"] == "failed"
    assert "codex introuvable" in done["error"]


def test_files_created_by_codex_appear_in_the_manifest(tmp_path: Path, repo: Path) -> None:
    def creates(argv, task, worktree, on_event, **kwargs) -> CodexResult:
        (worktree / "tests").mkdir()
        (worktree / "tests" / "test_calc.py").write_text("def test_x():\n    pass\n", "utf-8")
        return CodexResult(exit_code=0)

    tasks = make_tasks(tmp_path, repo, creates)

    done = wait_done(tasks, tasks.start_codex("nfactory-test", "x")["id"])

    assert done["manifest"] == [{"path": "tests/test_calc.py", "change": "added"}]


def test_a_codex_run_that_changed_nothing_says_so(tmp_path: Path, repo: Path) -> None:
    def idle(argv, task, worktree, on_event, **kwargs) -> CodexResult:
        on_event({"type": "message", "text": "Je n'ai rien pu modifier."})
        return CodexResult(exit_code=0)

    tasks = make_tasks(tmp_path, repo, idle)

    done = wait_done(tasks, tasks.start_codex("nfactory-test", "x")["id"])

    assert done["status"] == "no_changes"
    assert done["manifest"] == []
