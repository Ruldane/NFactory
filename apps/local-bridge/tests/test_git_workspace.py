"""Git work on the user's repository (task 4.5, spec §13): a separate worktree on a branch
`nfactory/<project>/<run>`, a manifest of changed files, a rollback. The user's own
checkout, including uncommitted edits, is never touched. Real git, throwaway repos."""

import subprocess
from pathlib import Path

import pytest

from nfactory_bridge.git_workspace import (
    Conflict,
    GitRefused,
    apply_files,
    commit,
    diff,
    manifest,
    prepare,
    rollback,
)


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return done.stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "user-repo"
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.name", "Someone")
    git(path, "config", "user.email", "someone@example.com")
    (path / "app.py").write_text("print('v1')\n", encoding="utf-8")
    (path / "old.txt").write_text("old\n", encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-q", "-m", "initial")
    return path


@pytest.fixture
def worktrees(tmp_path: Path) -> Path:
    return tmp_path / "worktrees"


def user_state(repo: Path) -> tuple[str, str, str, str]:
    """What the user sees in their checkout: HEAD, branch, status, and an edited file."""
    return (
        git(repo, "rev-parse", "HEAD"),
        git(repo, "branch", "--show-current"),
        git(repo, "status", "--porcelain"),
        (repo / "app.py").read_text(encoding="utf-8"),
    )


def test_a_run_works_in_its_own_worktree_and_branch(repo: Path, worktrees: Path) -> None:
    work = prepare(repo, worktrees, project="licences", run_id="run_abc123")

    assert work.branch == "nfactory/licences/run_abc123"
    assert work.path == worktrees / "run_abc123"
    assert (work.path / "app.py").read_text(encoding="utf-8") == "print('v1')\n"
    assert git(work.path, "branch", "--show-current").strip() == work.branch
    assert work.base == git(repo, "rev-parse", "HEAD").strip()


def test_the_users_uncommitted_edits_are_never_touched(repo: Path, worktrees: Path) -> None:
    (repo / "app.py").write_text("print('my unsaved work')\n", encoding="utf-8")
    (repo / "notes.md").write_text("draft\n", encoding="utf-8")
    before = user_state(repo)

    work = prepare(repo, worktrees, project="licences", run_id="run_1")
    apply_files(work, {"app.py": "print('v2')\n", "new.py": "x = 1\n"})
    commit(work, "NFactory : ajoute new.py")
    rollback(repo, work)

    assert user_state(repo) == before
    assert (repo / "notes.md").read_text(encoding="utf-8") == "draft\n"


def test_the_worktree_starts_from_the_committed_state(repo: Path, worktrees: Path) -> None:
    # The user's unsaved edit stays in their checkout; the run starts from HEAD.
    (repo / "app.py").write_text("print('my unsaved work')\n", encoding="utf-8")

    work = prepare(repo, worktrees, project="licences", run_id="run_1")

    assert (work.path / "app.py").read_text(encoding="utf-8") == "print('v1')\n"


def test_the_manifest_lists_added_modified_and_deleted_files(repo: Path, worktrees: Path) -> None:
    work = prepare(repo, worktrees, project="licences", run_id="run_1")

    apply_files(work, {"app.py": "print('v2')\n", "src/new.py": "x = 1\n"}, delete=["old.txt"])

    assert manifest(work) == [
        {"path": "app.py", "change": "modified"},
        {"path": "old.txt", "change": "deleted"},
        {"path": "src/new.py", "change": "added"},
    ]
    patch = diff(work)
    assert "+print('v2')" in patch and "+x = 1" in patch and "-old" in patch


def test_the_manifest_still_counts_after_a_commit(repo: Path, worktrees: Path) -> None:
    work = prepare(repo, worktrees, project="licences", run_id="run_1")
    apply_files(work, {"src/new.py": "x = 1\n"})

    sha = commit(work, "NFactory : ajoute new.py")

    assert manifest(work) == [{"path": "src/new.py", "change": "added"}]
    assert git(repo, "rev-parse", work.branch).strip() == sha
    assert git(repo, "rev-parse", "main").strip() == work.base  # main did not move


def test_a_file_changed_by_someone_else_is_not_overwritten(repo: Path, worktrees: Path) -> None:
    work = prepare(repo, worktrees, project="licences", run_id="run_1")
    (work.path / "app.py").write_text("print('edited by hand')\n", encoding="utf-8")

    with pytest.raises(Conflict) as refused:
        apply_files(work, {"app.py": "print('v2')\n", "new.py": "x = 1\n"})

    assert refused.value.paths == ["app.py"]
    assert (work.path / "app.py").read_text(encoding="utf-8") == "print('edited by hand')\n"
    assert not (work.path / "new.py").exists()  # all or nothing


def test_nfactorys_own_earlier_change_can_be_updated(repo: Path, worktrees: Path) -> None:
    work = prepare(repo, worktrees, project="licences", run_id="run_1")
    apply_files(work, {"app.py": "print('v2')\n"})

    apply_files(work, {"app.py": "print('v3')\n"})  # a repair rewrites its own output

    assert (work.path / "app.py").read_text(encoding="utf-8") == "print('v3')\n"


def test_rollback_removes_the_worktree_and_its_branch(repo: Path, worktrees: Path) -> None:
    branches_before = git(repo, "branch", "--list")
    work = prepare(repo, worktrees, project="licences", run_id="run_1")
    apply_files(work, {"new.py": "x = 1\n"})
    commit(work, "NFactory : essai")

    rollback(repo, work)

    assert not work.path.exists()
    assert git(repo, "branch", "--list") == branches_before
    assert "run_1" not in git(repo, "worktree", "list")


def test_an_existing_branch_is_never_reused(repo: Path, worktrees: Path) -> None:
    git(repo, "branch", "nfactory/licences/run_1")

    with pytest.raises(GitRefused, match="existe déjà"):
        prepare(repo, worktrees, project="licences", run_id="run_1")


@pytest.mark.parametrize(
    ("project", "run_id"),
    [("../x", "run_1"), ("licences", "run_1;rm"), ("", "run_1"), ("Licences", "run 1")],
)
def test_names_are_checked(repo: Path, worktrees: Path, project: str, run_id: str) -> None:
    with pytest.raises(GitRefused):
        prepare(repo, worktrees, project=project, run_id=run_id)


@pytest.mark.parametrize(
    "path", ["../escape.py", "/etc/passwd", "C:/x.py", ".git/config", "a/.git/hooks/x"]
)
def test_paths_stay_inside_the_worktree(repo: Path, worktrees: Path, path: str) -> None:
    work = prepare(repo, worktrees, project="licences", run_id="run_1")

    with pytest.raises(GitRefused):
        apply_files(work, {path: "x"})


def test_not_a_repository_is_refused(tmp_path: Path, worktrees: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()

    with pytest.raises(GitRefused, match="dépôt Git"):
        prepare(plain, worktrees, project="licences", run_id="run_1")


def test_rollback_never_deletes_a_branch_outside_nfactory(repo: Path, worktrees: Path) -> None:
    work = prepare(repo, worktrees, project="licences", run_id="run_1")
    forged = type(work)(path=work.path, branch="main", base=work.base)

    with pytest.raises(GitRefused):
        rollback(repo, forged)
    assert git(repo, "rev-parse", "--verify", "main")


def test_windows_line_endings_raise_no_false_conflict(repo: Path, worktrees: Path) -> None:
    # With core.autocrlf the checkout holds CRLF while git stores LF: not a user edit.
    git(repo, "config", "core.autocrlf", "true")
    work = prepare(repo, worktrees, project="licences", run_id="run_1")

    apply_files(work, {"app.py": "print('v2')\n"})
    apply_files(work, {"app.py": "print('v3')\n"})

    assert manifest(work) == [{"path": "app.py", "change": "modified"}]
