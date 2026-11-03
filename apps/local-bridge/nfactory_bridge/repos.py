"""Repositories the user authorized for NFactory, kept on the bridge side (spec §13.2).

The user adds one from their own terminal (`bridge.ps1 -Allow <folder>`); NFactory then
names it by id only, so no request can point the bridge at a path. The store lives in the
user's profile next to the pairing file, out of any repository.

Interface: RepoRegistry (allow, revoke, get, all, public), Repo, RepoRefused.
"""

import json
import re
import threading
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from nfactory_bridge.git_workspace import GitRefused, check_repo_root

_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,49}$")


class RepoRefused(ValueError):
    """Not a repository root, or an id the user never authorized."""


@dataclass(frozen=True)
class Repo:
    id: str
    name: str
    path: Path


class RepoRegistry:
    def __init__(self, store: Path) -> None:
        self._store = store
        self._lock = threading.Lock()
        self._repos = self._load()

    def allow(self, folder: Path) -> Repo:
        try:
            check_repo_root(folder)
        except GitRefused as exc:
            raise RepoRefused(str(exc)) from exc
        path = folder.resolve()
        with self._lock:
            for repo in self._repos:
                if repo.path == path:
                    return repo
            repo = Repo(id=self._free_id(_slug(path.name)), name=path.name, path=path)
            self._repos.append(repo)
            self._save()
        return repo

    def revoke(self, repo_id: str) -> None:
        with self._lock:
            self._repos = [r for r in self._repos if r.id != repo_id]
            self._save()

    def get(self, repo_id: str) -> Repo:
        for repo in self._repos:
            if repo.id == repo_id:
                return repo
        raise RepoRefused("Dépôt non autorisé sur ce poste : ajoutez-le avec bridge.ps1 -Allow.")

    def all(self) -> list[Repo]:
        return list(self._repos)

    def public(self) -> list[dict[str, str]]:
        """What may leave the bridge: ids and folder names, never a path."""
        return [{"id": r.id, "name": r.name} for r in self._repos]

    def _free_id(self, base: str) -> str:
        taken = {r.id for r in self._repos}
        candidate, n = base, 2
        while candidate in taken:
            candidate, n = f"{base[:45]}-{n}", n + 1
        return candidate

    def _load(self) -> list[Repo]:
        try:
            raw = json.loads(self._store.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        repos = []
        for item in raw.get("repos", []) if isinstance(raw, dict) else []:
            if isinstance(item, dict) and _ID.match(str(item.get("id", ""))):
                repos.append(Repo(id=item["id"], name=str(item["name"]), path=Path(item["path"])))
        return repos

    def _save(self) -> None:
        self._store.parent.mkdir(parents=True, exist_ok=True)
        data = {"repos": [{"id": r.id, "name": r.name, "path": str(r.path)} for r in self._repos]}
        self._store.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _slug(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:40]
    return slug or "depot"
