"""One throwaway container per command (sandbox v2, ADR-0005 / D8).

The container spec is fixed here: only the workspace name and the allow-listed argv
come from the request. No network, read-only image, no capability, a non-root user,
quotas on CPU, memory, processes, /tmp and logs, and only the run's own workspace
mounted (a subpath of the shared volume), so one run never sees another.
"""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from nfactory_sandbox.server import BadRequest

WORKSPACES = "/data/workspaces"
LABEL = "nfactory.sandbox"
MAX_OUTPUT_CHARS = 64_000
_KILL_GRACE_S = 30
# Non-secret settings for the tools; the image already sets PATH and the toolchain.
_ENV = ("PYTHONDONTWRITEBYTECODE=1", "PYTHONIOENCODING=utf-8", "NO_COLOR=1", "HOME=/tmp")


@dataclass(frozen=True)
class Limits:
    nano_cpus: int = 1_000_000_000  # one CPU
    memory_bytes: int = 1024**3
    pids: int = 256
    tmp_size: str = "256m"
    log_size: str = "2m"


class Engine(Protocol):
    def create(self, spec: dict[str, Any]) -> str: ...
    def start(self, container: str) -> None: ...
    def wait(self, container: str, timeout_s: float) -> int: ...
    def kill(self, container: str) -> None: ...
    def oom_killed(self, container: str) -> bool: ...
    def logs(self, container: str) -> tuple[str, str]: ...
    def remove(self, container: str) -> None: ...


def container_spec(
    image: str, volume: str, workspace: str, argv: list[str], limits: Limits
) -> dict[str, Any]:
    target = f"{WORKSPACES}/{workspace}"
    return {
        "Image": image,
        "Entrypoint": [],
        "Cmd": argv,
        "WorkingDir": target,
        "User": "10001:10001",
        "Env": list(_ENV),
        "Hostname": "sandbox",
        "NetworkDisabled": True,
        "Labels": {LABEL: "1", "nfactory.workspace": workspace},
        "HostConfig": {
            "NetworkMode": "none",
            "ReadonlyRootfs": True,
            "Privileged": False,
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges:true"],
            "Init": True,  # reaps orphans, forwards the kill
            "NanoCpus": limits.nano_cpus,
            "Memory": limits.memory_bytes,
            "MemorySwap": limits.memory_bytes,
            "PidsLimit": limits.pids,
            "Tmpfs": {"/tmp": f"rw,nosuid,nodev,size={limits.tmp_size}"},  # noqa: S108
            "LogConfig": {"Type": "json-file", "Config": {"max-size": limits.log_size}},
            "Mounts": [
                {
                    "Type": "volume",
                    "Source": volume,
                    "Target": target,
                    # NoCopy: else Docker copies the image's mount point into an empty
                    # workspace and gives it to root, and the run cannot write there.
                    "VolumeOptions": {"Subpath": workspace, "NoCopy": True},
                }
            ],
        },
    }


class ContainerExecutor:
    """Runs each command in a fresh container and always removes it afterwards."""

    def __init__(
        self, engine: Engine, *, image: str, volume: str, root: Path, limits: Limits
    ) -> None:
        self._engine = engine
        self._image = image
        self._volume = volume
        self._root = root  # read-only view of the volume, to check the workspace exists
        self._limits = limits

    def ready(self) -> bool:
        ping = getattr(self._engine, "ping", None)
        return bool(ping()) if callable(ping) else True

    def run(self, workspace: str, argv: list[str], timeout_s: int) -> dict[str, Any]:
        if not (self._root / workspace).is_dir():
            raise BadRequest("unknown workspace")
        spec = container_spec(self._image, self._volume, workspace, argv, self._limits)
        started = time.monotonic()
        container = self._engine.create(spec)
        try:
            self._engine.start(container)
            timed_out = False
            try:
                exit_code = self._engine.wait(container, timeout_s)
            except TimeoutError:
                timed_out = True
                self._engine.kill(container)
                self._engine.wait(container, _KILL_GRACE_S)
                exit_code = -1
            oom = not timed_out and exit_code == 137 and self._engine.oom_killed(container)
            stdout, stderr = self._engine.logs(container)
        finally:
            self._engine.remove(container)
        if oom:
            stderr += f"\nMémoire dépassée (limite {self._limits.memory_bytes // 1024**2} Mo)."
        return {
            "exit_code": exit_code,
            "stdout": stdout[-MAX_OUTPUT_CHARS:],
            "stderr": stderr[-MAX_OUTPUT_CHARS:],
            "duration_s": time.monotonic() - started,
            "timed_out": timed_out,
        }
