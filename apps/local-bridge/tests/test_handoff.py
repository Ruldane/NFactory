"""Claude Code handoff (task 4.4) and the file snapshot NFactory tests in its sandbox.

NFactory prepares a worktree and a brief; the user runs the official `claude` there
themselves; NFactory then collects the diff. Real git, no agent."""

import base64
import subprocess
from pathlib import Path

import pytest

from nfactory_bridge.codex_runtime import CodexResult
from nfactory_bridge.repos import RepoRegistry
from nfactory_bridge.tasks import TaskRefused, Tasks, handoff_instructions


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
    (path / "old.py").write_text("x = 1\n", encoding="utf-8")
    (path / ".gitignore").write_text(".venv/\n", encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-q", "-m", "initial")
    return path


def never_codex(*args, **kwargs) -> CodexResult:
    raise AssertionError("a handoff never runs an agent")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "profile" / "worktrees"


@pytest.fixture
def tasks(tmp_path: Path, repo: Path, root: Path) -> Tasks:
    registry = RepoRegistry(tmp_path / "profile" / "repos.json")
    registry.allow(repo)
    return Tasks(registry, root, codex=lambda: "codex", runner=never_codex)


def worktree(root: Path, task_id: str) -> Path:
    return root / "nfactory-test" / task_id


def test_a_handoff_prepares_a_worktree_and_a_brief_then_waits(
    tasks: Tasks, repo: Path, root: Path
) -> None:
    view = tasks.start_handoff("nfactory-test", "Ajoute une fonction divide")

    assert view["runtime"] == "claude"
    assert view["status"] == "awaiting_user"
    assert view["branch"] == f"nfactory/nfactory-test/{view['id']}"
    assert worktree(root, view["id"]).is_dir()
    brief = (root / "nfactory-test" / f"{view['id']}.brief.md").read_text(encoding="utf-8")
    assert "Ajoute une fonction divide" in brief
    assert "Ne fais ni commit, ni push" in brief
    assert git(repo, "status", "--porcelain") == ""  # the brief stays out of every checkout
    assert git(worktree(root, view["id"]), "status", "--porcelain") == ""


def test_the_user_gets_the_folder_and_the_official_command(tasks: Tasks, root: Path) -> None:
    view = tasks.start_handoff("nfactory-test", "Ajoute divide")

    lines = handoff_instructions(root, view["id"], windows=True)

    text = "\n".join(lines)
    assert str(worktree(root, view["id"])) in text
    assert 'claude (Get-Content -Raw "' in text
    assert f"{view['id']}.brief.md" in text
    assert "claude" in "\n".join(handoff_instructions(root, view["id"], windows=False))
    assert handoff_instructions(root, "t_000000000000", windows=True) is None
    assert handoff_instructions(root, "../../etc", windows=True) is None


def test_collecting_imports_what_the_user_changed(tasks: Tasks, repo: Path, root: Path) -> None:
    view = tasks.start_handoff("nfactory-test", "Ajoute divide")
    work = worktree(root, view["id"])
    (work / "calc.py").write_text("def divide(a, b):\n    return a / b\n", encoding="utf-8")
    (work / "test_calc.py").write_text("def test_x():\n    pass\n", encoding="utf-8")

    done = tasks.collect(view["id"])

    assert done["status"] == "succeeded"
    assert done["manifest"] == [
        {"path": "calc.py", "change": "modified"},
        {"path": "test_calc.py", "change": "added"},
    ]
    assert "+def divide(a, b):" in done["diff"]
    assert git(repo, "status", "--porcelain") == ""


def test_collecting_an_untouched_handoff_says_nothing_changed(tasks: Tasks) -> None:
    view = tasks.start_handoff("nfactory-test", "Ajoute divide")

    assert tasks.collect(view["id"])["status"] == "no_changes"


def test_only_a_waiting_handoff_can_be_collected(tasks: Tasks) -> None:
    view = tasks.start_handoff("nfactory-test", "Ajoute divide")
    tasks.collect(view["id"])

    with pytest.raises(TaskRefused) as refused:
        tasks.collect(view["id"])
    assert refused.value.code == "invalid_state"


def test_a_waiting_handoff_does_not_block_other_tasks(tasks: Tasks) -> None:
    tasks.start_handoff("nfactory-test", "Première")

    assert tasks.start_handoff("nfactory-test", "Seconde")["status"] == "awaiting_user"


def test_discarding_a_handoff_removes_worktree_branch_and_brief(
    tasks: Tasks, repo: Path, root: Path
) -> None:
    view = tasks.start_handoff("nfactory-test", "Ajoute divide")

    assert tasks.discard(view["id"])["status"] == "discarded"

    assert not worktree(root, view["id"]).exists()
    assert not (root / "nfactory-test" / f"{view['id']}.brief.md").exists()
    assert git(repo, "branch", "--list", "nfactory/*") == ""


def files_of(snapshot: dict) -> dict[str, bytes]:
    return {item["path"]: base64.b64decode(item["data"]) for item in snapshot["files"]}


def test_the_snapshot_holds_the_changed_tree_without_ignored_or_deleted_files(
    tasks: Tasks, root: Path
) -> None:
    view = tasks.start_handoff("nfactory-test", "Ajoute divide")
    work = worktree(root, view["id"])
    (work / "calc.py").write_text("def divide(a, b):\n    return a / b\n", encoding="utf-8")
    (work / "pkg").mkdir()
    (work / "pkg" / "new.py").write_bytes(b"y = 2\n")
    (work / "old.py").unlink()
    (work / ".venv").mkdir()
    (work / ".venv" / "secret.txt").write_text("ignored", encoding="utf-8")
    tasks.collect(view["id"])

    files = files_of(tasks.snapshot(view["id"]))

    assert set(files) == {".gitignore", "calc.py", "pkg/new.py"}
    assert files["pkg/new.py"] == b"y = 2\n"


def test_no_snapshot_before_the_changes_are_collected(tasks: Tasks) -> None:
    view = tasks.start_handoff("nfactory-test", "Ajoute divide")

    with pytest.raises(TaskRefused) as refused:
        tasks.snapshot(view["id"])
    assert refused.value.code == "invalid_state"


def test_a_snapshot_too_large_is_refused(
    tasks: Tasks, root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("nfactory_bridge.tasks.SNAPSHOT_MAX_BYTES", 10)
    view = tasks.start_handoff("nfactory-test", "Ajoute divide")
    (worktree(root, view["id"]) / "calc.py").write_text("x" * 50, encoding="utf-8")
    tasks.collect(view["id"])

    with pytest.raises(TaskRefused) as refused:
        tasks.snapshot(view["id"])
    assert refused.value.code == "too_large"
