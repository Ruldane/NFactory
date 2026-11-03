"""GitHub through the user's official `gh` CLI (task 4.6, spec §13).

`gh` keeps its own login: the bridge never reads its token, only runs fixed commands and
keeps a few parsed fields of their answer (never the raw output, which can carry
secrets). Pull requests are always drafts; nothing here merges, and only `nfactory/…`
branches are named. Every status (pushed, PR created, merged) is read back from GitHub.

Interface: GitHub (default_branch, branch_sha, find_pr, create_draft_pr), parse_remote,
run_gh, GitHubRefused.
"""

import json
import re
import subprocess
from collections.abc import Callable
from typing import Any

from nfactory_bridge.detection import Completed

SLUG = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9_.-]{1,100}$")
_BRANCH = re.compile(r"^nfactory/[a-z0-9][a-z0-9-]{0,49}/[A-Za-z0-9_]{1,64}$")
_REMOTE = re.compile(
    r"^(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)"
    r"(?P<slug>[^/\s]+/[^/\s]+?)(?:\.git)?/?$"
)
_TIMEOUT_S = 60

GhRun = Callable[..., Completed]


class GitHubRefused(ValueError):
    def __init__(self, message: str, code: str = "github_refused") -> None:
        self.code = code
        super().__init__(message)


def parse_remote(url: str) -> str | None:
    """`owner/name` of a GitHub remote URL, or None for any other remote."""
    match = _REMOTE.match(url.strip())
    if not match:
        return None
    slug = match.group("slug")
    return slug if SLUG.fullmatch(slug) and ".." not in slug else None


def run_gh(argv: list[str], stdin: str | None = None) -> Completed:
    done = subprocess.run(  # noqa: S603 - fixed argv, checked slug and branch
        argv,
        input=stdin if stdin is not None else "",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=_TIMEOUT_S,
        check=False,
    )
    return Completed(done.returncode, done.stdout, done.stderr)


class GitHub:
    def __init__(self, *, gh: Callable[[], str], run: GhRun = run_gh) -> None:
        self._gh = gh  # the gh executable, or a refusal when it is missing or logged out
        self._run = run

    def default_branch(self, slug: str) -> str:
        data = self._json(["api", f"repos/{_slug(slug)}"], "Dépôt GitHub inaccessible.")
        branch = data.get("default_branch") if isinstance(data, dict) else None
        if not isinstance(branch, str) or not branch:
            raise GitHubRefused("Branche par défaut du dépôt GitHub introuvable.")
        return branch

    def branch_sha(self, slug: str, branch: str) -> str | None:
        """The commit GitHub holds for the branch, or None when it is not there."""
        argv = ["api", f"repos/{_slug(slug)}/git/ref/heads/{_branch(branch)}"]
        done = self._call(argv)
        if done.code != 0:
            if "404" in done.stderr or "Not Found" in done.stderr:
                return None
            raise GitHubRefused("GitHub n'a pas répondu sur la branche.")
        sha = _loads(done.stdout).get("object", {}).get("sha")
        return sha if isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{40}", sha) else None

    def find_pr(self, slug: str, branch: str) -> dict[str, Any] | None:
        fields = "number,url,state,isDraft,headRefOid,mergedAt"
        argv = ["pr", "list", "--repo", _slug(slug), "--head", _branch(branch)]
        found = self._json(
            [*argv, "--state", "all", "--json", fields, "--limit", "1"], "PR introuvable."
        )
        if not isinstance(found, list) or not found or not isinstance(found[0], dict):
            return None
        pr = found[0]
        return {
            "number": int(pr.get("number", 0)),
            "url": str(pr.get("url", ""))[:300],
            "state": str(pr.get("state", ""))[:20],
            "draft": bool(pr.get("isDraft")),
            "head": str(pr.get("headRefOid", ""))[:40],
            "merged": bool(pr.get("mergedAt")),
        }

    def create_draft_pr(self, slug: str, *, base: str, head: str, title: str, body: str) -> None:
        argv = [
            "pr", "create", "--repo", _slug(slug), "--draft",
            "--base", _ref(base), "--head", _branch(head),
            "--title", title.replace("\n", " ")[:200], "--body-file", "-",
        ]  # fmt: skip
        done = self._call(argv, stdin=body[:60_000])
        if done.code != 0:
            raise GitHubRefused("GitHub a refusé la création de la PR brouillon.")

    def _json(self, argv: list[str], refusal: str) -> Any:
        done = self._call(argv)
        if done.code != 0:
            raise GitHubRefused(refusal)  # gh's own output is never relayed
        return _loads(done.stdout)

    def _call(self, argv: list[str], stdin: str | None = None) -> Completed:
        try:
            return self._run([self._gh(), *argv], stdin=stdin)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GitHubRefused("La commande gh n'a pas pu tourner.") from exc


def _loads(text: str) -> Any:
    try:
        return json.loads(text or "null") or {}
    except ValueError as exc:
        raise GitHubRefused("Réponse de gh inattendue.") from exc


def _slug(slug: str) -> str:
    if not SLUG.fullmatch(slug) or ".." in slug:
        raise GitHubRefused("Nom de dépôt GitHub refusé.")
    return slug


def _branch(branch: str) -> str:
    if not _BRANCH.fullmatch(branch):
        raise GitHubRefused("Seule une branche nfactory/… peut être publiée.")
    return branch


def _ref(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._/-]{1,100}", name) or ".." in name or name.startswith("-"):
        raise GitHubRefused("Nom de branche de base refusé.")
    return name
