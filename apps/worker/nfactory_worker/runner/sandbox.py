"""Runs commands in the sandbox container over HTTP (ADR-0005). Same contract as
LocalRunner; the sandbox re-validates everything on its side."""

import httpx

from nfactory_worker.runner.types import (
    ALLOWED_EXECUTABLES,
    CommandNotAllowedError,
    CommandResult,
    truncate,
)

# Extra time for the HTTP round trip on top of the command's own timeout.
_GRACE_S = 15


class SandboxError(RuntimeError):
    pass


class SandboxRunner:
    def __init__(self, url: str, token: str) -> None:
        self._url = url.rstrip("/")
        self._token = token

    async def run(self, workspace: str, argv: tuple[str, ...], timeout_s: int) -> CommandResult:
        if not argv or argv[0] not in ALLOWED_EXECUTABLES:
            raise CommandNotAllowedError(f"Executable not allowed: {argv[:1]}")
        body = {"workspace": workspace, "argv": list(argv), "timeout_s": timeout_s}
        try:
            async with httpx.AsyncClient(timeout=timeout_s + _GRACE_S) as client:
                response = await client.post(
                    f"{self._url}/run",
                    json=body,
                    headers={"Authorization": f"Bearer {self._token}"},
                )
        except httpx.HTTPError as exc:
            raise SandboxError(f"Sandbox injoignable : {type(exc).__name__}") from exc
        if response.status_code != 200:
            raise SandboxError(f"Sandbox a refusé la commande ({response.status_code})")
        data = response.json()
        return CommandResult(
            argv=argv,
            exit_code=int(data["exit_code"]),
            stdout=truncate(str(data["stdout"])),
            stderr=truncate(str(data["stderr"])),
            duration_s=float(data["duration_s"]),
            timed_out=bool(data["timed_out"]),
        )
