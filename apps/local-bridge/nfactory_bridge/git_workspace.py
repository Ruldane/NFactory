"""Git work on the user's repository (task 4.5, spec §13). Standard library + the git CLI.

A run never touches the user's checkout: it works in its own `git worktree`, on a new
branch `nfactory/<project>/<run-id>`, started from a commit (never from uncommitted
edits). Every write by NFactory is staged at once, so the index records what NFactory
wrote: a file whose working copy differs from the index, or an untracked file in the
way, was changed by someone else and is never overwritten (Conflict, nothing written).

Interface: prepare, apply_files, adopt, manifest, diff, tracked_files, commit, rollback;
check_repo_root; Worktree; GitRefused,
Conflict. Every git call is a fixed argv; names and paths are checked before use.
"""

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

BRANCH_PREFIX = "nfactory/"
_PROJECT = re.compile(r"^[a-z0-9][a-z0-9-]{0,49}$")
_RUN_ID = re.compile(r"^[A-Za-z0-9_]{1,64}$")
_AUTHOR = ("-c", "user.name=NFactory", "-c", "user.email=nfactory@localhost")
_CHANGES = {"A": "added", "M": "modified", "D": "deleted", "T": "modified"}
_TIMEOUT_S = 120


class GitRefused(ValueError):
    """A request NFactory will not run (bad name, path, branch, or not a repository)."""


class Conflict(GitRefused):
    def __init__(self, paths: list[str]) -> None:
        self.paths = paths
        super().__init__(
            "Fichiers modifiés hors de NFactory, laissés intacts : " + ", ".join(paths)
        )


@dataclass(frozen=True)
class Worktree:
    path: Path
    branch: str
    base: str  # the commit the run started from


def _git(cwd: Path, *args: str) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_TERMINAL_PROMPT"] = "0"  # never wait for a password
    done = subprocess.run(  # noqa: S603 - fixed argv, checked names and paths
        ["git", "-C", str(cwd), *args],  # noqa: S607 - git from the user's PATH
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=_TIMEOUT_S,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    if done.returncode != 0:
        raise GitRefused(f"git {args[0]} a échoué : {done.stderr.strip()[:300]}")
    return done.stdout


def _succeeds(cwd: Path, *args: str) -> bool:
    try:
        _git(cwd, *args)
    except GitRefused:
        return False
    return True


def check_repo_root(repo: Path) -> None:
    """Refuse anything but the top folder of a Git repository."""
    try:
        top = Path(_git(repo, "rev-parse", "--show-toplevel").strip())
    except (GitRefused, OSError) as exc:
        raise GitRefused(f"« {repo} » n'est pas un dépôt Git.") from exc
    if top.resolve() != repo.resolve():
        raise GitRefused(f"« {repo} » n'est pas la racine d'un dépôt Git.")


def prepare(repo: Path, root: Path, *, project: str, run_id: str, base: str = "HEAD") -> Worktree:
    if not _PROJECT.match(project) or not _RUN_ID.match(run_id):
        raise GitRefused("Nom de projet ou de run invalide pour une branche.")
    check_repo_root(repo)
    branch = f"{BRANCH_PREFIX}{project}/{run_id}"
    if _succeeds(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"):
        raise GitRefused(f"La branche {branch} existe déjà : elle n'est pas réutilisée.")
    path = root / run_id
    if path.exists():
        raise GitRefused(f"Le dossier {path} existe déjà.")
    commit_id = _git(repo, "rev-parse", "--verify", f"{base}^{{commit}}").strip()
    root.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "--quiet", "-b", branch, str(path), commit_id)
    return Worktree(path=path, branch=branch, base=commit_id)


def apply_files(
    work: Worktree, files: dict[str, str | bytes], delete: list[str] | None = None
) -> None:
    """Write and delete files, all or nothing; refuse any file changed by someone else."""
    targets = {_checked(path): content for path, content in files.items()}
    removed = [_checked(path) for path in delete or []]
    edited = set(_git(work.path, "diff", "--name-only", "-z").split("\0"))
    untracked = set(_git(work.path, "ls-files", "--others", "--exclude-standard", "-z").split("\0"))
    conflicts = sorted(p for p in [*targets, *removed] if p in edited or p in untracked)
    if conflicts:
        raise Conflict(conflicts)
    for path, content in targets.items():
        target = work.path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        data = content.encode("utf-8") if isinstance(content, str) else content
        target.write_bytes(data)
    for path in removed:
        (work.path / path).unlink(missing_ok=True)
    if targets or removed:
        _git(work.path, "add", "--all", "--", *targets, *removed)


def adopt(work: Worktree) -> None:
    """Stage what an agent wrote in the worktree, so new files count and later NFactory
    writes see it as NFactory's own work."""
    _git(work.path, "add", "--all")


def manifest(work: Worktree) -> list[dict[str, str]]:
    """Files created, modified or deleted since the run's base commit."""
    raw = _git(work.path, "diff", "--name-status", "--no-renames", "-z", work.base)
    fields = [f for f in raw.split("\0") if f]
    changes = [
        {"path": path, "change": _CHANGES.get(status[:1], "modified")}
        for status, path in zip(fields[::2], fields[1::2], strict=True)
    ]
    return sorted(changes, key=lambda change: change["path"])


def diff(work: Worktree) -> str:
    return _git(work.path, "diff", "--no-renames", work.base)


def tracked_files(work: Worktree) -> list[str]:
    """Regular files in the index, sorted: no link, no submodule, nothing ignored."""
    raw = _git(work.path, "ls-files", "--stage", "-z")
    paths = []
    for entry in filter(None, raw.split("\0")):
        meta, _, path = entry.partition("\t")
        if meta.split(" ", 1)[0] in ("100644", "100755"):
            paths.append(_checked(path))
    return sorted(paths)


def commit(work: Worktree, message: str) -> str:
    """A local commit on the run's branch (`local_commit_created`); nothing is pushed."""
    _git(work.path, "add", "--all")
    _git(work.path, *_AUTHOR, "commit", "--quiet", "-m", message[:2000])
    return _git(work.path, "rev-parse", "HEAD").strip()


def rollback(repo: Path, work: Worktree) -> None:
    """Remove the run's worktree and branch. The user's checkout and branches stay."""
    if not work.branch.startswith(BRANCH_PREFIX):
        raise GitRefused("Seule une branche nfactory/… peut être supprimée.")
    listed = _git(repo, "worktree", "list", "--porcelain")
    registered = {
        Path(line.removeprefix("worktree ")).resolve()
        for line in listed.splitlines()
        if line.startswith("worktree ")
    }
    if work.path.resolve() in registered:
        _git(repo, "worktree", "remove", "--force", str(work.path))
    _git(repo, "worktree", "prune")
    if _succeeds(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{work.branch}"):
        _git(repo, "branch", "-D", work.branch)


def _checked(path: str) -> str:
    normal = path.replace("\\", "/")
    parts = PurePosixPath(normal).parts
    if (
        not parts
        or normal.startswith("/")
        or ":" in normal
        or ".." in parts
        or any(part.lower() == ".git" for part in parts)
    ):
        raise GitRefused(f"Chemin refusé : {path}")
    return "/".join(parts)
