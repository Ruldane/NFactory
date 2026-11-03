"""Sandbox v2 (ADR-0005, D8): one confined, throwaway container per command."""

from pathlib import Path
from typing import Any

import pytest

from nfactory_sandbox.containers import ContainerExecutor, Limits, container_spec
from nfactory_sandbox.engine import EngineError
from nfactory_sandbox.server import BadRequest

IMAGE = "nfactory-sandbox:latest"
VOLUME = "nfactory_workspaces"


def spec(workspace: str = "run_1", argv: tuple[str, ...] = ("python", "-V")) -> dict[str, Any]:
    return container_spec(IMAGE, VOLUME, workspace, list(argv), Limits())


def test_the_container_has_no_network_and_no_privilege() -> None:
    host = spec()["HostConfig"]

    assert host["NetworkMode"] == "none"
    assert spec()["NetworkDisabled"] is True
    assert host["ReadonlyRootfs"] is True
    assert host["CapDrop"] == ["ALL"]
    assert host["SecurityOpt"] == ["no-new-privileges:true"]
    assert host["Privileged"] is False
    assert spec()["User"] == "10001:10001"
    assert "Binds" not in host and "Devices" not in host and "CapAdd" not in host


def test_quotas_bound_cpu_memory_processes_tmp_and_logs() -> None:
    host = spec()["HostConfig"]

    assert host["NanoCpus"] == 1_000_000_000
    assert host["Memory"] == host["MemorySwap"] == 1024**3  # no swap on top
    assert host["PidsLimit"] == 256
    assert host["Tmpfs"] == {"/tmp": "rw,nosuid,nodev,size=256m"}
    assert host["LogConfig"]["Config"]["max-size"] == "2m"


def test_only_the_runs_own_workspace_is_mounted() -> None:
    created = spec("run_42")

    assert created["HostConfig"]["Mounts"] == [
        {
            "Type": "volume",
            "Source": VOLUME,
            "Target": "/data/workspaces/run_42",
            # NoCopy: Docker would otherwise copy the image's mount point into an empty
            # workspace and hand it to root, and the run could not write its files.
            "VolumeOptions": {"Subpath": "run_42", "NoCopy": True},
        }
    ]
    assert created["WorkingDir"] == "/data/workspaces/run_42"


def test_the_command_runs_without_shell_and_without_secrets() -> None:
    created = spec(argv=("node", "a b; rm -rf /"))

    assert created["Entrypoint"] == []
    assert created["Cmd"] == ["node", "a b; rm -rf /"]  # one argument, never parsed by a shell
    assert all("TOKEN" not in item and "KEY" not in item for item in created["Env"])
    assert created["Labels"]["nfactory.sandbox"] == "1"


class FakeEngine:
    """The Docker Engine, as the executor sees it."""

    def __init__(self, *, wait_codes: list[int | None], oom: bool = False) -> None:
        self.calls: list[str] = []
        self.created: list[dict[str, Any]] = []
        self._wait_codes = wait_codes
        self._oom = oom

    def create(self, spec: dict[str, Any]) -> str:
        self.calls.append("create")
        self.created.append(spec)
        return "c1"

    def start(self, container: str) -> None:
        self.calls.append("start")

    def wait(self, container: str, timeout_s: float) -> int:
        self.calls.append("wait")
        code = self._wait_codes.pop(0)
        if code is None:
            raise TimeoutError
        return code

    def kill(self, container: str) -> None:
        self.calls.append("kill")

    def oom_killed(self, container: str) -> bool:
        return self._oom

    def logs(self, container: str) -> tuple[str, str]:
        self.calls.append("logs")
        return "sortie", "erreurs"

    def remove(self, container: str) -> None:
        self.calls.append("remove")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    (tmp_path / "run_1").mkdir()
    return tmp_path


def executor(engine: FakeEngine, root: Path) -> ContainerExecutor:
    return ContainerExecutor(engine, image=IMAGE, volume=VOLUME, root=root, limits=Limits())


def test_a_command_runs_then_its_container_is_removed(root: Path) -> None:
    engine = FakeEngine(wait_codes=[3])

    result = executor(engine, root).run("run_1", ["python", "-c", "exit(3)"], 30)

    assert engine.calls == ["create", "start", "wait", "logs", "remove"]
    assert (result["exit_code"], result["stdout"], result["stderr"]) == (3, "sortie", "erreurs")
    assert result["timed_out"] is False


def test_a_command_past_its_timeout_is_killed(root: Path) -> None:
    engine = FakeEngine(wait_codes=[None, 137])

    result = executor(engine, root).run("run_1", ["python", "-c", "while True: pass"], 2)

    assert engine.calls == ["create", "start", "wait", "kill", "wait", "logs", "remove"]
    assert result["timed_out"] is True
    assert result["exit_code"] == -1


def test_running_out_of_memory_is_explained(root: Path) -> None:
    engine = FakeEngine(wait_codes=[137], oom=True)

    result = executor(engine, root).run("run_1", ["python", "-c", "x = ' ' * 10**10"], 30)

    assert "Mémoire dépassée" in result["stderr"]


def test_the_container_is_removed_even_when_the_engine_fails(root: Path) -> None:
    engine = FakeEngine(wait_codes=[])  # wait raises IndexError: an engine failure

    with pytest.raises(IndexError):
        executor(engine, root).run("run_1", ["python", "-V"], 30)
    assert engine.calls[-1] == "remove"


def test_an_unknown_workspace_starts_no_container(root: Path) -> None:
    engine = FakeEngine(wait_codes=[0])

    with pytest.raises(BadRequest):
        executor(engine, root).run("run_unknown", ["python", "-V"], 30)
    assert engine.calls == []


def test_engine_errors_are_a_distinct_failure() -> None:
    assert not issubclass(EngineError, BadRequest)  # the worker must not see them as 400
