"""Repositories the user authorized on the bridge side (spec §13.2). NFactory names a
repository by its id only: no path ever comes from the API."""

import json
import subprocess
from pathlib import Path

import pytest

from nfactory_bridge.repos import RepoRefused, RepoRegistry


def make_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "-C", str(path), "init", "-q", "-b", "main"], check=True)
    return path


@pytest.fixture
def store(tmp_path: Path) -> Path:
    return tmp_path / "profile" / "repos.json"


def test_an_allowed_repository_gets_an_id_and_is_listed(tmp_path: Path, store: Path) -> None:
    repo = make_repo(tmp_path / "Mon Projet")
    registry = RepoRegistry(store)

    allowed = registry.allow(repo)

    assert allowed.id == "mon-projet"
    assert allowed.name == "Mon Projet"
    assert registry.get("mon-projet").path == repo.resolve()
    assert [r.id for r in registry.all()] == ["mon-projet"]


def test_the_list_survives_a_restart(tmp_path: Path, store: Path) -> None:
    repo = make_repo(tmp_path / "app")
    RepoRegistry(store).allow(repo)

    assert RepoRegistry(store).get("app").path == repo.resolve()


def test_two_folders_with_the_same_name_get_distinct_ids(tmp_path: Path, store: Path) -> None:
    registry = RepoRegistry(store)
    first = registry.allow(make_repo(tmp_path / "a" / "app"))
    second = registry.allow(make_repo(tmp_path / "b" / "app"))

    assert first.id == "app"
    assert second.id == "app-2"


def test_allowing_the_same_repository_twice_keeps_one_entry(tmp_path: Path, store: Path) -> None:
    repo = make_repo(tmp_path / "app")
    registry = RepoRegistry(store)

    registry.allow(repo)
    again = registry.allow(repo)

    assert again.id == "app"
    assert len(registry.all()) == 1


def test_a_folder_that_is_not_a_repository_root_is_refused(tmp_path: Path, store: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    repo = make_repo(tmp_path / "repo")
    (repo / "sub").mkdir()
    registry = RepoRegistry(store)

    with pytest.raises(RepoRefused, match="dépôt Git"):
        registry.allow(plain)
    with pytest.raises(RepoRefused, match="racine"):
        registry.allow(repo / "sub")


def test_an_unknown_id_is_refused(store: Path) -> None:
    with pytest.raises(RepoRefused):
        RepoRegistry(store).get("../etc")


def test_revoking_removes_the_repository(tmp_path: Path, store: Path) -> None:
    registry = RepoRegistry(store)
    registry.allow(make_repo(tmp_path / "app"))

    registry.revoke("app")

    assert registry.all() == []
    assert json.loads(store.read_text(encoding="utf-8")) == {"repos": []}


def test_the_public_view_never_shows_the_path(tmp_path: Path, store: Path) -> None:
    registry = RepoRegistry(store)
    registry.allow(make_repo(tmp_path / "app"))

    assert registry.public() == [{"id": "app", "name": "app", "github": None}]
