"""What a child run changed in the delivered project (spec §3.5, scenario E).

Interface: diff_workspaces(parent, child, max_chars) -> Changes, with the added, modified
and removed paths and a unified diff. Outputs the run rebuilds every time (test reports,
frontend build, the explanation) are not changes of the project and are left out.
"""

import difflib
from dataclasses import dataclass
from typing import Any

from nfactory_core.workspace import Workspace

MAX_PATCH_CHARS = 200_000
_TRUNCATED = "[diff tronqué]\n"
_REBUILT_PREFIXES = (".nfactory/",)
_REBUILT_PARTS = ("/dist/",)
_REBUILT_FILES = frozenset({"EXPLICATION.md"})


@dataclass(frozen=True)
class Changes:
    added: list[str]
    modified: list[str]
    removed: list[str]
    patch: str
    truncated: bool = False

    def summary(self) -> dict[str, Any]:
        return {
            "added": self.added,
            "modified": self.modified,
            "removed": self.removed,
            "truncated": self.truncated,
        }


def diff_workspaces(
    parent: Workspace, child: Workspace, max_chars: int = MAX_PATCH_CHARS
) -> Changes:
    before = {p for p in parent.files() if _is_source(p)}
    after = {p for p in child.files() if _is_source(p)}
    added = sorted(after - before)
    removed = sorted(before - after)
    modified = sorted(p for p in before & after if parent.read_bytes(p) != child.read_bytes(p))
    chunks: list[str] = []
    for path in sorted([*added, *modified, *removed]):
        old = parent.read_bytes(path) if path in before else b""
        new = child.read_bytes(path) if path in after else b""
        chunks.append(_file_diff(path, old, new))
    patch = "".join(chunks)
    truncated = len(patch) > max_chars
    if truncated:
        patch = patch[:max_chars].rsplit("\n", 1)[0] + "\n" + _TRUNCATED
    return Changes(added, modified, removed, patch, truncated)


def _is_source(path: str) -> bool:
    if path in _REBUILT_FILES or path.startswith(_REBUILT_PREFIXES):
        return False
    return not any(part in f"/{path}" for part in _REBUILT_PARTS)


def _file_diff(path: str, old: bytes, new: bytes) -> str:
    old_text, new_text = _text(old), _text(new)
    if old_text is None or new_text is None:
        return f"Fichier binaire modifié : {path}\n"
    lines = difflib.unified_diff(
        old_text.splitlines(keepends=True),
        new_text.splitlines(keepends=True),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
    )
    return "".join(line if line.endswith("\n") else line + "\n" for line in lines)


def _text(data: bytes) -> str | None:
    if b"\x00" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None
