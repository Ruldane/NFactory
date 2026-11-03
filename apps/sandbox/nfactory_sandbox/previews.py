"""Live previews of a generated app (spec §3.1, task 3.10).

A preview is one long-lived container per workspace, built from the same confined spec
as a check (read-only image, no capability, non-root, quotas) with two differences:
it joins the internal preview network, which has no route to the Internet nor to
NFactory's own services, and it mounts the workspace read-only. Nothing publishes its
port: the preview gateway reaches it by name. Each preview expires after `ttl_s`.
"""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from nfactory_sandbox.containers import Limits, container_spec
from nfactory_sandbox.server import WORKSPACE, BadRequest, Busy

PREVIEW_PORT = 8000
PREVIEW_LABEL = "nfactory.preview"


class PreviewBusy(Busy):
    """Too many previews running at once."""


class PreviewEngine(Protocol):
    def create(self, spec: dict[str, Any], name: str | None = None) -> str: ...
    def start(self, container: str) -> None: ...
    def running(self, container: str) -> bool: ...
    def remove(self, container: str) -> None: ...


def preview_name(workspace: str) -> str:
    """The container's name, also its host name on the preview network."""
    return f"nfactory-preview-{workspace}"


def preview_spec(
    image: str, volume: str, network: str, workspace: str, argv: list[str], limits: Limits
) -> dict[str, Any]:
    spec = container_spec(image, volume, workspace, argv, limits)
    del spec["NetworkDisabled"]
    spec["Env"] = [*spec["Env"], f"PORT={PREVIEW_PORT}"]
    spec["Labels"] = {**spec["Labels"], PREVIEW_LABEL: "1"}
    host = spec["HostConfig"]
    host["NetworkMode"] = network
    host["Mounts"] = [{**host["Mounts"][0], "ReadOnly": True}]
    return spec


@dataclass
class _Preview:
    container: str
    expires_at: float


class PreviewManager:
    """Starts, reuses, expires and stops previews. Thread-safe."""

    def __init__(
        self,
        engine: PreviewEngine,
        *,
        image: str,
        volume: str,
        network: str,
        root: Path,
        limits: Limits,
        max_previews: int = 2,
        ttl_s: int = 900,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._engine = engine
        self._image = image
        self._volume = volume
        self._network = network
        self._root = root  # read-only view of the volume, to check the workspace exists
        self._limits = limits
        self._max = max_previews
        self._ttl_s = ttl_s
        self._clock = clock
        self._previews: dict[str, _Preview] = {}
        self._lock = threading.Lock()

    def start(self, workspace: str, argv: list[str]) -> dict[str, Any]:
        if not WORKSPACE.fullmatch(workspace) or not (self._root / workspace).is_dir():
            raise BadRequest("unknown workspace")
        with self._lock:
            self._sweep_locked()
            current = self._previews.get(workspace)
            if current and not self._engine.running(current.container):
                self._drop_locked(workspace)
                current = None
            if current is None:
                if len(self._previews) >= self._max:
                    raise PreviewBusy(f"{self._max} aperçus déjà ouverts")
                current = self._create_locked(workspace, argv)
            current.expires_at = self._clock() + self._ttl_s
            return {"host": preview_name(workspace), "expires_in_s": self._ttl_s}

    def status(self, workspace: str) -> dict[str, Any]:
        with self._lock:
            self._sweep_locked()
            current = self._previews.get(workspace)
            if current is None or not self._engine.running(current.container):
                return {"running": False}
            left = int(current.expires_at - self._clock())
            return {"running": True, "host": preview_name(workspace), "expires_in_s": left}

    def stop(self, workspace: str) -> None:
        with self._lock:
            self._drop_locked(workspace)

    def sweep(self) -> None:
        with self._lock:
            self._sweep_locked()

    def _create_locked(self, workspace: str, argv: list[str]) -> _Preview:
        spec = preview_spec(self._image, self._volume, self._network, workspace, argv, self._limits)
        container = self._engine.create(spec, name=preview_name(workspace))
        try:
            self._engine.start(container)
        except Exception:
            self._engine.remove(container)
            raise
        preview = _Preview(container, self._clock() + self._ttl_s)
        self._previews[workspace] = preview
        return preview

    def _sweep_locked(self) -> None:
        now = self._clock()
        for workspace in [w for w, p in self._previews.items() if p.expires_at <= now]:
            self._drop_locked(workspace)

    def _drop_locked(self, workspace: str) -> None:
        preview = self._previews.pop(workspace, None)
        if preview:
            self._engine.remove(preview.container)
