"""Entry point of the sandbox supervisor: `python -m nfactory_sandbox`."""

import os
import sys
import threading
import time
from pathlib import Path

from nfactory_sandbox.containers import LABEL, WORKSPACES, ContainerExecutor, Limits
from nfactory_sandbox.engine import DockerEngine, EngineError, UnixTransport
from nfactory_sandbox.previews import PreviewManager
from nfactory_sandbox.server import Config, make_server


def main() -> None:
    token = os.environ.get("NFACTORY_SANDBOX_TOKEN", "")
    if len(token) < 16:
        raise SystemExit("NFACTORY_SANDBOX_TOKEN manquant ou trop court (16 caractères min).")
    image = os.environ.get("NFACTORY_SANDBOX_IMAGE", "")
    volume = os.environ.get("NFACTORY_WORKSPACES_VOLUME", "")
    if not image or not volume:
        raise SystemExit("NFACTORY_SANDBOX_IMAGE et NFACTORY_WORKSPACES_VOLUME sont requis.")

    engine = DockerEngine(UnixTransport(os.environ.get("DOCKER_SOCKET", "/var/run/docker.sock")))
    _remove_leftovers(engine)
    executor = ContainerExecutor(
        engine, image=image, volume=volume, root=Path(WORKSPACES), limits=Limits()
    )
    config = Config(
        token=token,
        executor=executor,
        max_parallel=int(os.environ.get("NFACTORY_SANDBOX_MAX_PARALLEL", "4")),
        previews=_previews(engine, image, volume),
    )
    port = int(os.environ.get("SANDBOX_PORT", "8800"))
    print(f"sandbox: supervisor on :{port}, image={image}, volume={volume}", flush=True)
    make_server("0.0.0.0", port, config).serve_forever()  # noqa: S104 - internal network only


def _previews(engine: DockerEngine, image: str, volume: str) -> PreviewManager | None:
    """Previews are on only when their internal network is configured."""
    network = os.environ.get("NFACTORY_PREVIEW_NETWORK", "")
    if not network:
        return None
    previews = PreviewManager(
        engine,
        image=image,
        volume=volume,
        network=network,
        root=Path(WORKSPACES),
        limits=Limits(),
        max_previews=int(os.environ.get("NFACTORY_PREVIEW_MAX", "2")),
        ttl_s=int(os.environ.get("NFACTORY_PREVIEW_TTL_S", "900")),
    )

    def sweep_forever() -> None:
        while True:
            time.sleep(30)
            try:
                previews.sweep()
            except EngineError as exc:
                print(f"sandbox: preview sweep failed ({exc})", file=sys.stderr, flush=True)

    threading.Thread(target=sweep_forever, daemon=True).start()
    return previews


def _remove_leftovers(engine: DockerEngine) -> None:
    """Containers left by a crashed supervisor are removed before serving."""
    try:
        for container in engine.leftovers(f"{LABEL}=1"):
            engine.remove(container)
    except EngineError as exc:
        print(f"sandbox: cannot list leftovers yet ({exc})", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
