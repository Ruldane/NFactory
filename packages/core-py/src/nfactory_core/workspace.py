"""Per-run workspace on disk.

Interface: Workspace.create, Workspace.open, write_files, read_text, read_bytes, files.

Every path is validated: generated content is untrusted and must never write or read
outside the workspace root (spec §8.3).
"""

import os
import re
from collections.abc import Mapping
from pathlib import Path, PurePosixPath

_NAME = re.compile(r"^[A-Za-z0-9_-]+$")
# Caches and installed dependencies: rebuilt from the sources, never delivered.
_IGNORED_DIRS = frozenset(
    {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", "node_modules", ".vite"}
)


class UnsafePathError(ValueError):
    pass


def _root(base: Path, name: str) -> Path:
    if not _NAME.fullmatch(name):
        raise UnsafePathError(f"Invalid workspace name: {name!r}")
    return base / name


class Workspace:
    def __init__(self, root: Path) -> None:
        self.root = root

    @classmethod
    def create(cls, base: Path, name: str) -> "Workspace":
        root = _root(base, name)
        root.mkdir(parents=True, exist_ok=True)
        return cls(root)

    @classmethod
    def open(cls, base: Path, name: str) -> "Workspace | None":
        """The existing workspace, or None. Never creates anything (read-only callers)."""
        root = _root(base, name)
        return cls(root) if root.is_dir() else None

    def resolve(self, relative: str) -> Path:
        """Absolute path for `relative`, or UnsafePathError if it leaves the root."""
        pure = PurePosixPath(relative.replace("\\", "/"))
        if not relative or pure.is_absolute() or ".." in pure.parts or ":" in relative:
            raise UnsafePathError(f"Unsafe path: {relative!r}")
        target = (self.root / pure).resolve()
        if not target.is_relative_to(self.root.resolve()) or target == self.root.resolve():
            raise UnsafePathError(f"Unsafe path: {relative!r}")
        return target

    def write_files(self, files: Mapping[str, str | bytes]) -> None:
        # Validate everything first so a bad path never leaves a half-written workspace.
        targets = [(self.resolve(path), content) for path, content in files.items()]
        for target, content in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                target.write_bytes(content)
            else:
                target.write_text(content, encoding="utf-8", newline="\n")

    def read_text(self, relative: str) -> str:
        return self.resolve(relative).read_text(encoding="utf-8")

    def read_bytes(self, relative: str) -> bytes:
        return self.resolve(relative).read_bytes()

    def files(self) -> list[str]:
        """Relative POSIX paths of every regular file, sorted.

        Caches and dependencies are left out, and links (symlinks, Windows junctions)
        are never crossed: generated code may plant one pointing outside the root.
        """
        found = []
        for folder, dirs, names in os.walk(self.root, followlinks=False):
            base = Path(folder)
            dirs[:] = [d for d in dirs if d not in _IGNORED_DIRS and not _is_link(base / d)]
            for name in names:
                path = base / name
                if not _is_link(path) and path.is_file():
                    found.append(path.relative_to(self.root).as_posix())
        return sorted(found)


def _is_link(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()
