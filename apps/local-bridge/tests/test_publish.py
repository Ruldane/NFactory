"""Publishing a task's change (task 4.6): local commit, push of the nfactory/ branch, draft
PR, each status read back. Real git with a bare remote; GitHub faked on top of it."""

import subprocess
from pathlib import Path
from typing import Any

import pytest

from nfactory_bridge.codex_runtime import CodexResult
from nfactory_bridge.repos import RepoRefused, RepoRegistry
from nfactory_bridge.tasks import TaskRefused, Tasks

SLUG = "Ruldane/nfactory-test"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


@pytest.fixture
def remote(tmp_path: Path) -> Path:
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    return bare


@pytest.fixture
def repo(tmp_path: Path, remote: Path) -> Path:
    path = tmp_path / "nfactory-test"
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.name", "Someone")
    git(path, "config", "user.email", "someone@example.com")
    (path / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-q", "-m", "initial")
    # GitHub as seen by gh; pushes land in the local bare repository.
    git(path, "remote", "add", "origin", f"https://github.com/{SLUG}.git")
    git(path, "remote", "set-url", "--push", "origin", str(remote))
    git(path, "push", "-q", "origin", "main")
    return path


class FakeGitHub:
    """GitHub over the bare remote: branches are real, PRs are recorded."""

    def __init__(self, remote: Path) -> None:
        self.remote = remote
        self.prs: list[dict[str, Any]] = []

    def default_branch(self, slug: str) -> str:
        return "main"

    def branch_sha(self, slug: str, branch: str) -> str | None:
        done = subprocess.run(
            ["git", "--git-dir", str(self.remote), "rev-parse", "--verify", f"refs/heads/{branch}"],
            capture_output=True,
            text=True,
            check=False,
        )
        return done.stdout.strip() if done.returncode == 0 else None

    def find_pr(self, slug: str, branch: str) -> dict[str, Any] | None:
        return next((pr for pr in self.prs if pr["branch"] == branch), None)

    def create_draft_pr(self, slug: str, *, base: str, head: str, title: str, body: str) -> None:
        self.prs.append(
            {
                "number": len(self.prs) + 1,
                "url": f"https://github.com/{slug}/pull/{len(self.prs) + 1}",
                "state": "OPEN",
                "draft": True,
                "head": self.branch_sha(slug, head) or "",
                "merged": False,
                "branch": head,
                "base": base,
                "title": title,
                "body": body,
            }
        )


def never_codex(*args, **kwargs) -> CodexResult:
    raise AssertionError("no agent runs here")


@pytest.fixture
def registry(tmp_path: Path, repo: Path) -> RepoRegistry:
    registry = RepoRegistry(tmp_path / "profile" / "repos.json")
    registry.allow(repo)
    return registry


@pytest.fixture
def github(remote: Path) -> FakeGitHub:
    return FakeGitHub(remote)


@pytest.fixture
def tasks(tmp_path: Path, registry: RepoRegistry, github: FakeGitHub) -> Tasks:
    return Tasks(
        registry,
        tmp_path / "profile" / "worktrees",
        codex=lambda: "codex",
        runner=never_codex,
        github=github,
    )


def changed_task(tasks: Tasks, tmp_path: Path) -> str:
    view = tasks.start_handoff("nfactory-test", "Ajoute divide")
    work = tmp_path / "profile" / "worktrees" / "nfactory-test" / view["id"]
    (work / "calc.py").write_text("def divide(a, b):\n    return a / b\n", encoding="utf-8")
    tasks.collect(view["id"])
    return str(view["id"])


def test_push_needs_the_users_permission_for_that_repository(
    tasks: Tasks, registry: RepoRegistry, tmp_path: Path
) -> None:
    task_id = changed_task(tasks, tmp_path)

    with pytest.raises(TaskRefused) as refused:
        tasks.publish(task_id, "Ajoute divide", "corps")
    assert refused.value.code == "push_not_allowed"
    assert "-AllowPush" in str(refused.value)


def test_allowing_push_reads_the_github_remote(registry: RepoRegistry) -> None:
    repo = registry.allow_push("nfactory-test")

    assert repo.github == SLUG
    assert registry.public() == [{"id": "nfactory-test", "name": "nfactory-test", "github": SLUG}]


def test_a_repository_without_a_github_remote_cannot_be_published(
    tmp_path: Path, repo: Path
) -> None:
    git(repo, "remote", "set-url", "origin", "https://gitlab.com/x/y.git")
    registry = RepoRegistry(tmp_path / "other" / "repos.json")
    registry.allow(repo)

    with pytest.raises(RepoRefused):
        registry.allow_push("nfactory-test")


def test_publishing_commits_pushes_the_branch_and_opens_a_draft_pr(
    tasks: Tasks, registry: RepoRegistry, github: FakeGitHub, repo: Path, tmp_path: Path
) -> None:
    registry.allow_push("nfactory-test")
    task_id = changed_task(tasks, tmp_path)

    published = tasks.publish(task_id, "Ajoute divide", "Résultats des tests : 4 réussis")

    branch = f"nfactory/nfactory-test/{task_id}"
    assert published["state"] == "pr_created"
    assert published["pushed"] is True
    assert published["commit"] == github.branch_sha(SLUG, branch)
    assert published["pr"]["url"].endswith("/pull/1") and published["pr"]["draft"] is True
    assert github.prs[0]["base"] == "main" and github.prs[0]["body"].startswith("Résultats")
    assert github.branch_sha(SLUG, "main") == git(repo, "rev-parse", "main")  # main untouched
    assert git(repo, "status", "--porcelain") == ""
    assert tasks.get(task_id)["publication"]["state"] == "pr_created"


def test_publishing_twice_reuses_the_commit_and_the_pr(
    tasks: Tasks, registry: RepoRegistry, github: FakeGitHub, tmp_path: Path
) -> None:
    registry.allow_push("nfactory-test")
    task_id = changed_task(tasks, tmp_path)

    first = tasks.publish(task_id, "Ajoute divide", "corps")
    second = tasks.publish(task_id, "Ajoute divide", "corps")

    assert first["commit"] == second["commit"]
    assert len(github.prs) == 1


def test_statuses_come_from_github_not_from_memory(
    tasks: Tasks, registry: RepoRegistry, github: FakeGitHub, remote: Path, tmp_path: Path
) -> None:
    registry.allow_push("nfactory-test")
    task_id = changed_task(tasks, tmp_path)
    tasks.publish(task_id, "Ajoute divide", "corps")

    github.prs[0]["merged"], github.prs[0]["state"] = True, "MERGED"
    assert tasks.publication(task_id)["state"] == "merged"

    github.prs.clear()
    subprocess.run(
        ["git", "--git-dir", str(remote), "branch", "-D", f"nfactory/nfactory-test/{task_id}"],
        check=True,
        capture_output=True,
    )
    verified = tasks.publication(task_id)
    assert verified["state"] == "local_commit_created"
    assert verified["pushed"] is False and verified["pr"] is None


def test_only_a_finished_task_with_changes_is_published(
    tasks: Tasks, registry: RepoRegistry
) -> None:
    registry.allow_push("nfactory-test")
    view = tasks.start_handoff("nfactory-test", "Rien")

    with pytest.raises(TaskRefused) as waiting:
        tasks.publish(view["id"], "t", "b")
    tasks.collect(view["id"])  # nothing changed
    with pytest.raises(TaskRefused) as empty:
        tasks.publish(view["id"], "t", "b")

    assert waiting.value.code == empty.value.code == "invalid_state"


def test_nothing_is_published_before_the_first_publish(tasks: Tasks, tmp_path: Path) -> None:
    task_id = changed_task(tasks, tmp_path)

    assert tasks.get(task_id)["publication"] is None
