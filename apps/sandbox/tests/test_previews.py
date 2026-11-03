"""Live previews (spec §3.1, task 3.10): the generated app runs in a confined, long-lived
container on an internal network, reachable only through the preview proxy."""

from pathlib import Path
from typing import Any

import pytest

from nfactory_sandbox.containers import Limits
from nfactory_sandbox.previews import (
    PREVIEW_PORT,
    PreviewBusy,
    PreviewManager,
    preview_name,
    preview_spec,
)
from nfactory_sandbox.server import BadRequest


def spec(workspace: str = "run_1") -> dict[str, Any]:
    return preview_spec("img", "vol", "nfactory_preview", workspace, ["python", "x.py"], Limits())


def test_a_preview_keeps_the_confinement_but_joins_the_preview_network() -> None:
    created = spec()
    host = created["HostConfig"]

    assert host["NetworkMode"] == "nfactory_preview"
    assert "NetworkDisabled" not in created
    assert host["ReadonlyRootfs"] is True and host["CapDrop"] == ["ALL"]
    assert host["Memory"] == 1024**3 and host["PidsLimit"] == 256
    assert host["Mounts"][0]["ReadOnly"] is True  # a preview never changes the deliverable
    assert f"PORT={PREVIEW_PORT}" in created["Env"]
    assert created["Labels"]["nfactory.preview"] == "1"
    assert "PortBindings" not in host  # reachable only through the proxy


def test_preview_names_are_stable_per_workspace() -> None:
    assert preview_name("run_1") == "nfactory-preview-run_1"


class FakeEngine:
    def __init__(self) -> None:
        self.created: list[tuple[str | None, dict[str, Any]]] = []
        self.removed: list[str] = []
        self.alive: set[str] = set()

    def create(self, spec: dict[str, Any], name: str | None = None) -> str:
        self.created.append((name, spec))
        return name or "anon"

    def start(self, container: str) -> None:
        self.alive.add(container)

    def running(self, container: str) -> bool:
        return container in self.alive

    def remove(self, container: str) -> None:
        self.removed.append(container)
        self.alive.discard(container)


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def root(tmp_path: Path) -> Path:
    for name in ("run_1", "run_2", "run_3"):
        (tmp_path / name).mkdir()
    return tmp_path


def manager(engine: FakeEngine, root: Path, clock: Clock) -> PreviewManager:
    return PreviewManager(
        engine,
        image="img",
        volume="vol",
        network="nfactory_preview",
        root=root,
        limits=Limits(),
        max_previews=2,
        ttl_s=600,
        clock=clock,
    )


def test_starting_twice_reuses_the_running_preview(root: Path) -> None:
    engine, clock = FakeEngine(), Clock()
    previews = manager(engine, root, clock)

    first = previews.start("run_1", ["python", "tools/preview.py"])
    again = previews.start("run_1", ["python", "tools/preview.py"])

    assert first == again == {"host": "nfactory-preview-run_1", "expires_in_s": 600}
    assert len(engine.created) == 1


def test_the_number_of_previews_is_capped(root: Path) -> None:
    previews = manager(FakeEngine(), root, Clock())
    previews.start("run_1", ["python", "a.py"])
    previews.start("run_2", ["python", "a.py"])

    with pytest.raises(PreviewBusy):
        previews.start("run_3", ["python", "a.py"])


def test_previews_expire_and_are_removed(root: Path) -> None:
    engine, clock = FakeEngine(), Clock()
    previews = manager(engine, root, clock)
    previews.start("run_1", ["python", "a.py"])

    clock.now += 601
    previews.sweep()

    assert engine.removed == ["nfactory-preview-run_1"]
    assert previews.status("run_1") == {"running": False}


def test_a_stopped_preview_frees_its_slot(root: Path) -> None:
    engine = FakeEngine()
    previews = manager(engine, root, Clock())
    previews.start("run_1", ["python", "a.py"])
    previews.start("run_2", ["python", "a.py"])

    previews.stop("run_1")

    assert previews.start("run_3", ["python", "a.py"])["host"] == "nfactory-preview-run_3"


def test_a_crashed_preview_is_not_reported_running(root: Path) -> None:
    engine = FakeEngine()
    previews = manager(engine, root, Clock())
    previews.start("run_1", ["python", "a.py"])
    engine.alive.clear()  # the app exited

    assert previews.status("run_1") == {"running": False}


def test_an_unknown_workspace_starts_nothing(root: Path) -> None:
    engine = FakeEngine()

    with pytest.raises(BadRequest):
        manager(engine, root, Clock()).start("run_9", ["python", "a.py"])
    assert engine.created == []
