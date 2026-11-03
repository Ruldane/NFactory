"""What a child run changed in the delivered project (scenario E): a file summary and a
unified diff, ignoring what the run itself rebuilds (reports, build output)."""

from pathlib import Path

from nfactory_core.workspace import Workspace
from nfactory_worker.changes import diff_workspaces


def workspace(root: Path, name: str, files: dict[str, str | bytes]) -> Workspace:
    created = Workspace.create(root, name)
    created.write_files(files)
    return created


def test_added_modified_removed_and_a_unified_diff(tmp_path: Path) -> None:
    parent = workspace(
        tmp_path, "run_a", {"app/models.py": "a = 1\nb = 2\n", "old.txt": "x\n", "same.py": "s\n"}
    )
    child = workspace(
        tmp_path, "run_b", {"app/models.py": "a = 1\nb = 3\n", "new.py": "n\n", "same.py": "s\n"}
    )

    changes = diff_workspaces(parent, child)

    assert (changes.added, changes.modified, changes.removed) == (
        ["new.py"],
        ["app/models.py"],
        ["old.txt"],
    )
    assert "--- a/app/models.py\n+++ b/app/models.py\n" in changes.patch
    assert "-b = 2\n+b = 3\n" in changes.patch
    assert "+n\n" in changes.patch and "-x\n" in changes.patch
    assert "same.py" not in changes.patch


def test_rebuilt_outputs_are_not_changes(tmp_path: Path) -> None:
    rebuilt = {
        ".nfactory/junit.xml": "<a/>",
        "frontend/dist/assets/index-1.js": "1",
        "EXPLICATION.md": "parent",
    }
    parent = workspace(tmp_path, "run_a", rebuilt)
    child = workspace(
        tmp_path,
        "run_b",
        {
            ".nfactory/junit.xml": "<b/>",
            "frontend/dist/assets/index-2.js": "2",
            "EXPLICATION.md": "child",
        },
    )

    changes = diff_workspaces(parent, child)

    assert (changes.added, changes.modified, changes.removed) == ([], [], [])
    assert changes.patch == ""


def test_a_binary_file_is_listed_without_its_bytes(tmp_path: Path) -> None:
    parent = workspace(tmp_path, "run_a", {"rapport.xlsx": b"PK\x03\x04\x00old"})
    child = workspace(tmp_path, "run_b", {"rapport.xlsx": b"PK\x03\x04\x00new"})

    changes = diff_workspaces(parent, child)

    assert changes.modified == ["rapport.xlsx"]
    assert "Fichier binaire modifié : rapport.xlsx" in changes.patch
    assert "old" not in changes.patch


def test_a_huge_patch_is_cut_and_says_so(tmp_path: Path) -> None:
    parent = workspace(
        tmp_path, "run_a", {"big.txt": "".join(f"ligne {i}\n" for i in range(50_000))}
    )
    child = workspace(
        tmp_path, "run_b", {"big.txt": "".join(f"LIGNE {i}\n" for i in range(50_000))}
    )

    changes = diff_workspaces(parent, child, max_chars=10_000)

    assert len(changes.patch) < 10_200
    assert changes.patch.endswith("[diff tronqué]\n")
    assert changes.summary()["truncated"] is True


def test_the_summary_is_json_ready(tmp_path: Path) -> None:
    parent = workspace(tmp_path, "run_a", {"a.py": "1\n"})
    child = workspace(tmp_path, "run_b", {"a.py": "2\n"})

    assert diff_workspaces(parent, child).summary() == {
        "added": [],
        "modified": ["a.py"],
        "removed": [],
        "truncated": False,
    }
