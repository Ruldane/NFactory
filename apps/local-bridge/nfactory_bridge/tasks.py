"""Coding tasks on a repository the user authorized (tasks 4.3, 4.4, 4.5).

A task gets its own worktree and branch `nfactory/<repo-id>/<task-id>` (git_workspace),
so the user's checkout is never touched. A Codex task runs the user's Codex there in a
background thread; when it ends, its writes are staged and the task carries the manifest
and the diff against the starting commit. One agent runs at a time.

A Claude Code handoff runs no agent: NFactory writes a brief next to the worktree, the
user runs the official `claude` there themselves (`handoff_instructions`), then asks
NFactory to collect the changes. A finished task offers a snapshot of its files, which
NFactory tests in its sandbox: generated code never runs on the bridge.

Tasks live in memory: after a bridge restart their worktrees stay on disk but are no
longer listed.

Interface: Tasks (start_codex, start_handoff, get, cancel, collect, snapshot, discard),
handoff_instructions, TaskRefused.
"""

import base64
import os
import re
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nfactory_bridge import git_workspace
from nfactory_bridge.codex_runtime import CodexRefused, CodexResult, codex_argv, run_codex
from nfactory_bridge.repos import RepoRefused, RepoRegistry

TASK_MAX_CHARS = 4_000
MAX_EVENTS = 500
DIFF_MAX_CHARS = 400_000
SNAPSHOT_MAX_FILES = 5_000
SNAPSHOT_MAX_BYTES = 20_000_000
_TASK_ID = re.compile(r"^t_[0-9a-f]{12}$")
_ACTIVE = ("preparing", "running")
_FINISHED = ("succeeded", "no_changes")

# Codex gets the user's words plus NFactory's limits for a task.
_RULES = """
Règles de NFactory pour cette tâche :
- Travaille uniquement dans ce dépôt, et garde le changement petit et limité à la tâche.
- Ajoute ou mets à jour les tests qui couvrent le changement.
- Ne fais ni commit, ni push, ni changement de branche : NFactory s'en charge après la revue.
- N'utilise pas le réseau et ne lis aucun fichier de secrets.
"""


class TaskRefused(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass
class _Task:
    id: str
    runtime: str
    repo_id: str
    work: git_workspace.Worktree
    status: str = "preparing"
    events: list[dict[str, Any]] = field(default_factory=list)
    manifest: list[dict[str, str]] = field(default_factory=list)
    diff: str = ""
    diff_truncated: bool = False
    error: str = ""
    created_at: float = field(default_factory=time.time)
    cancel: threading.Event = field(default_factory=threading.Event)

    def view(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "runtime": self.runtime,
            "repo_id": self.repo_id,
            "branch": self.work.branch,
            "base": self.work.base,
            "status": self.status,
            "events": list(self.events),
            "manifest": list(self.manifest),
            "diff": self.diff,
            "diff_truncated": self.diff_truncated,
            "error": self.error,
            "created_at": self.created_at,
        }


Runner = Callable[..., CodexResult]


class Tasks:
    def __init__(
        self,
        repos: RepoRegistry,
        root: Path,
        *,
        codex: Callable[[], str],
        runner: Runner = run_codex,
    ) -> None:
        self._repos = repos
        self._root = root
        self._codex = codex  # the Codex executable, or TaskRefused if not usable
        self._runner = runner
        self._lock = threading.Lock()
        self._tasks: dict[str, _Task] = {}

    def start_codex(self, repo_id: str, task: str) -> dict[str, Any]:
        text = _checked_task(task)
        executable = self._codex()
        item = self._prepare("codex", repo_id)
        try:
            argv = codex_argv(executable, item.work.path)
        except CodexRefused as exc:
            self._drop(item)
            raise TaskRefused("codex_refused", str(exc)) from exc
        item.status = "running"
        prompt = f"Tâche demandée par l'utilisateur :\n{text}\n{_RULES}"
        threading.Thread(target=self._run, args=(item, argv, prompt), daemon=True).start()
        return item.view()

    def start_handoff(self, repo_id: str, task: str) -> dict[str, Any]:
        """Prepare a worktree and a brief for the user's own Claude Code (spec §6.5)."""
        text = _checked_task(task)
        item = self._prepare("claude", repo_id, blocking=False)
        brief = _brief_path(self._root, item.repo_id, item.id)
        brief.write_text(_brief(text), encoding="utf-8")
        item.status = "awaiting_user"
        return item.view()

    def get(self, task_id: str) -> dict[str, Any]:
        return self._find(task_id).view()

    def collect(self, task_id: str) -> dict[str, Any]:
        """Import what the user's Claude Code changed in a waiting handoff."""
        item = self._find(task_id)
        if item.status != "awaiting_user":
            raise TaskRefused("invalid_state", "Ce relais n'attend plus de changements.")
        self._collect(item)
        item.status = "succeeded" if item.manifest else "no_changes"
        return item.view()

    def snapshot(self, task_id: str) -> dict[str, Any]:
        """The task's files (base64), for NFactory to test them in its sandbox."""
        item = self._find(task_id)
        if item.status not in _FINISHED:
            raise TaskRefused("invalid_state", "Les changements ne sont pas encore importés.")
        try:
            paths = git_workspace.tracked_files(item.work)
        except git_workspace.GitRefused as exc:
            raise TaskRefused("git_refused", str(exc)) from exc
        if len(paths) > SNAPSHOT_MAX_FILES:
            raise TaskRefused("too_large", f"Trop de fichiers (max {SNAPSHOT_MAX_FILES}).")
        top = item.work.path.resolve()
        files, total = [], 0
        for path in paths:
            target = item.work.path / path
            if target.is_symlink() or not target.resolve().is_relative_to(top):
                continue  # a link planted in the worktree never leads outside it
            if not target.is_file():
                continue
            data = target.read_bytes()
            total += len(data)
            if total > SNAPSHOT_MAX_BYTES:
                raise TaskRefused("too_large", "Dépôt trop volumineux pour être testé (max 20 Mo).")
            files.append({"path": path, "data": base64.b64encode(data).decode("ascii")})
        return {"id": item.id, "files": files}

    def cancel(self, task_id: str) -> dict[str, Any]:
        item = self._find(task_id)
        item.cancel.set()
        return item.view()

    def discard(self, task_id: str) -> dict[str, Any]:
        """Remove the task's worktree and branch (rollback)."""
        item = self._find(task_id)
        if item.status in _ACTIVE:
            raise TaskRefused("busy", "Arrêtez la tâche avant de l'abandonner.")
        repo = self._repos.get(item.repo_id)
        git_workspace.rollback(repo.path, item.work)
        _brief_path(self._root, item.repo_id, item.id).unlink(missing_ok=True)
        item.status = "discarded"
        item.diff = ""
        return item.view()

    def _prepare(self, runtime: str, repo_id: str, *, blocking: bool = True) -> _Task:
        try:
            repo = self._repos.get(repo_id)
        except RepoRefused as exc:
            raise TaskRefused("repo_not_allowed", str(exc)) from exc
        with self._lock:
            if blocking and any(t.status in _ACTIVE for t in self._tasks.values()):
                raise TaskRefused("busy", "Une tâche est déjà en cours sur ce poste.")
            task_id = "t_" + secrets.token_hex(6)
            try:
                work = git_workspace.prepare(
                    repo.path, self._root / repo.id, project=repo.id, run_id=task_id
                )
            except git_workspace.GitRefused as exc:
                raise TaskRefused("git_refused", str(exc)) from exc
            item = _Task(id=task_id, runtime=runtime, repo_id=repo.id, work=work)
            self._tasks[task_id] = item
        return item

    def _drop(self, item: _Task) -> None:
        git_workspace.rollback(self._repos.get(item.repo_id).path, item.work)
        with self._lock:
            self._tasks.pop(item.id, None)

    def _run(self, item: _Task, argv: list[str], prompt: str) -> None:
        def on_event(summary: dict[str, Any]) -> None:
            if len(item.events) < MAX_EVENTS:
                item.events.append(summary)

        try:
            result = self._runner(argv, prompt, item.work.path, on_event, cancel=item.cancel)
        except Exception as exc:
            item.error = f"Codex n'a pas pu tourner : {exc}"[:500]
            item.status = "failed"
            return
        self._collect(item)
        if result.cancelled:
            item.status = "cancelled"
        elif result.timed_out:
            item.status, item.error = "failed", "Codex a dépassé son temps maximal."
        elif result.exit_code != 0:
            item.status = "failed"
            item.error = (f"Codex s'est arrêté (code {result.exit_code}). " + result.stderr_tail)[
                :1_000
            ]
        elif not item.manifest:
            item.status = "no_changes"  # Codex ended well but wrote nothing
        else:
            item.status = "succeeded"

    def _collect(self, item: _Task) -> None:
        try:
            git_workspace.adopt(item.work)
            item.manifest = git_workspace.manifest(item.work)
            patch = git_workspace.diff(item.work)
        except git_workspace.GitRefused as exc:
            item.error = str(exc)[:500]
            return
        item.diff = patch[:DIFF_MAX_CHARS]
        item.diff_truncated = len(patch) > DIFF_MAX_CHARS

    def _find(self, task_id: str) -> _Task:
        item = self._tasks.get(task_id)
        if item is None:
            raise TaskRefused("not_found", "Tâche inconnue.")
        return item


def _brief_path(root: Path, repo_id: str, task_id: str) -> Path:
    # Next to the worktree, never inside it: the brief is not part of the change.
    return root / repo_id / f"{task_id}.brief.md"


def _brief(text: str) -> str:
    return (
        "# Tâche confiée par NFactory à Claude Code\n\n"
        f"Tâche demandée par l'utilisateur :\n{text}\n{_RULES}"
        "- Quand tu as terminé, dis-le : l'utilisateur importera les changements dans NFactory.\n"
    )


def handoff_instructions(
    root: Path, task_id: str, *, windows: bool = os.name == "nt"
) -> list[str] | None:
    """What the user types to run the official `claude` on a handoff; None if unknown.
    The bridge only prints this: the user launches Claude Code themselves."""
    if not _TASK_ID.fullmatch(task_id):
        return None
    briefs = sorted(root.glob(f"*/{task_id}.brief.md"))
    if not briefs or not (briefs[0].parent / task_id).is_dir():
        return None
    brief, folder = briefs[0], briefs[0].parent / task_id
    launch = f'claude (Get-Content -Raw "{brief}")' if windows else f"claude \"$(cat '{brief}')\""
    return [
        f"Relais Claude Code {task_id} (dépôt {brief.parent.name})",
        f"Copie de travail : {folder}",
        f"Brief : {brief}",
        "Dans un terminal, lancez vous-même Claude Code :",
        f'  cd "{folder}"',
        f"  {launch}",
        "Quand Claude a terminé, revenez dans NFactory : « Importer les changements ».",
    ]


def _checked_task(task: str) -> str:
    text = task.strip() if isinstance(task, str) else ""
    if not text:
        raise TaskRefused("invalid_task", "Décrivez la tâche à confier à l'agent.")
    if len(text) > TASK_MAX_CHARS:
        raise TaskRefused("invalid_task", f"Tâche trop longue (max {TASK_MAX_CHARS} caractères).")
    return text
