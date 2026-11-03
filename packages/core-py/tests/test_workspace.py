"""A run workspace never lets a path escape its root (spec §8.3)."""

from pathlib import Path

import pytest

from nfactory_core.workspace import UnsafePathError, Workspace


@pytest.fixture
def workspace(tmp_path: Path) -> Workspace:
    return Workspace.create(tmp_path, "run_abc")


def test_create_makes_a_directory_named_after_the_run(tmp_path: Path) -> None:
    ws = Workspace.create(tmp_path, "run_abc")
    assert ws.root == tmp_path / "run_abc"
    assert ws.root.is_dir()


@pytest.mark.parametrize("name", ["", "..", "a/b", "a\\b", "run abc"])
def test_workspace_name_must_be_a_plain_identifier(tmp_path: Path, name: str) -> None:
    with pytest.raises(UnsafePathError):
        Workspace.create(tmp_path, name)


def test_write_files_creates_nested_text_and_binary_files(workspace: Workspace) -> None:
    workspace.write_files({"app/main.py": "print('ok')\n", "data/blob.bin": b"\x00\x01"})
    assert workspace.read_text("app/main.py") == "print('ok')\n"
    assert (workspace.root / "data" / "blob.bin").read_bytes() == b"\x00\x01"


@pytest.mark.parametrize(
    "path", ["../evil.py", "a/../../evil.py", "/etc/passwd", "C:/Windows/x", "", "a/./../.."]
)
def test_paths_outside_the_root_are_refused(workspace: Workspace, path: str) -> None:
    with pytest.raises(UnsafePathError):
        workspace.write_files({path: "x"})
    with pytest.raises(UnsafePathError):
        workspace.read_text(path)


def test_files_lists_relative_posix_paths_without_caches(workspace: Workspace) -> None:
    workspace.write_files(
        {
            "b.txt": "b",
            "a/c.py": "c",
            "__pycache__/x.pyc": "x",
            ".pytest_cache/v": "x",
            "a/__pycache__/y.pyc": "y",
        }
    )
    assert workspace.files() == ["a/c.py", "b.txt"]


def test_files_leaves_out_installed_dependencies(workspace: Workspace) -> None:
    workspace.write_files(
        {
            "frontend/src/App.jsx": "x",
            "frontend/node_modules/vite/a.js": "x",
            "frontend/.vite/c": "x",
        }
    )
    assert workspace.files() == ["frontend/src/App.jsx"]


def _link_dir(link: Path, target: Path) -> None:
    """A directory link: a symlink where allowed, else a Windows junction."""
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        import _winapi  # Windows only: junctions need no privilege

        _winapi.CreateJunction(str(target), str(link))  # type: ignore[attr-defined]


def test_files_never_follows_a_link(workspace: Workspace, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("x", encoding="utf-8")
    workspace.write_files({"kept.txt": "k"})
    _link_dir(workspace.root / "escape", outside)
    try:
        (workspace.root / "file-link.txt").symlink_to(outside / "secret.txt")
    except OSError:
        pass  # file symlinks need a privilege on Windows; the directory case still runs

    assert workspace.files() == ["kept.txt"]
