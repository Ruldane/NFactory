"""Live preview of a finished run (spec §3.1, task 3.10).

The API never runs generated code. It asks the sandbox supervisor to start the command
the recipe recorded in the run's package step, then hands the dashboard the gateway URL
(another origin) to frame. The request carries only the run id: the command comes from
the run's record, and is checked against the same allow-list as the supervisor's.

Interface: start_preview / preview_status / stop_preview, PreviewControl (the port to
the supervisor), SupervisorPreviews (its HTTP adapter), PreviewError.
"""

from typing import Any, Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError
from app.schemas.runs import PreviewOut
from app.services.identity import RequestContext
from app.services.runs import owned_run
from nfactory_core.models import RunStep
from nfactory_core.states import RunState

_EXECUTABLES = ("python", "pwsh", "node")  # the supervisor's allow-list
_TIMEOUT_S = 30.0


class PreviewError(AppError):
    def __init__(self, code: str, message: str, *, status: int = 502) -> None:
        super().__init__(status, code, message)


class PreviewControl(Protocol):
    async def start(self, workspace: str, argv: list[str]) -> dict[str, Any]: ...
    async def status(self, workspace: str) -> dict[str, Any]: ...
    async def stop(self, workspace: str) -> None: ...


class SupervisorPreviews:
    """Talks to the sandbox supervisor's /previews routes (bearer token)."""

    def __init__(self, base_url: str, token: str) -> None:
        self._base = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}

    async def start(self, workspace: str, argv: list[str]) -> dict[str, Any]:
        body = {"workspace": workspace, "argv": argv}
        return await self._call("POST", "/previews", body)

    async def status(self, workspace: str) -> dict[str, Any]:
        return await self._call("GET", f"/previews/{workspace}")

    async def stop(self, workspace: str) -> None:
        await self._call("DELETE", f"/previews/{workspace}")

    async def _call(self, method: str, path: str, body: Any = None) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_S) as http:
                response = await http.request(
                    method, self._base + path, json=body, headers=self._headers
                )
        except httpx.HTTPError:
            raise PreviewError("preview_failed", "Le sandbox ne répond pas.") from None
        if response.status_code == 503:
            raise PreviewError(
                "preview_busy",
                "Trop d'aperçus ouverts : fermez-en un puis réessayez.",
                status=503,
            )
        if response.status_code != 200:
            raise PreviewError("preview_failed", "Le sandbox n'a pas pu lancer l'aperçu.")
        data: dict[str, Any] = response.json()
        return data


async def start_preview(
    session: AsyncSession,
    ctx: RequestContext,
    control: PreviewControl | None,
    public_url: str,
    run_id: str,
) -> PreviewOut:
    run = await owned_run(session, ctx, run_id)
    control = _enabled(control)
    if run.state != RunState.COMPLETED.value:
        raise PreviewError(
            "run_not_completed", "Seul un run terminé avec succès a un aperçu.", status=409
        )
    argv = _preview_command(await _package_output(session, run.id))
    started = await control.start(run.id, argv)
    return PreviewOut(
        running=True, url=_url(public_url, run.id), expires_in_s=started.get("expires_in_s")
    )


async def preview_status(
    session: AsyncSession,
    ctx: RequestContext,
    control: PreviewControl | None,
    public_url: str,
    run_id: str,
) -> PreviewOut:
    run = await owned_run(session, ctx, run_id)
    if control is None:
        return PreviewOut(running=False)
    status = await control.status(run.id)
    if not status.get("running"):
        return PreviewOut(running=False)
    return PreviewOut(
        running=True, url=_url(public_url, run.id), expires_in_s=status.get("expires_in_s")
    )


async def stop_preview(
    session: AsyncSession, ctx: RequestContext, control: PreviewControl | None, run_id: str
) -> None:
    run = await owned_run(session, ctx, run_id)
    if control is not None:
        await control.stop(run.id)


def _enabled(control: PreviewControl | None) -> PreviewControl:
    if control is None:
        raise PreviewError(
            "preview_disabled",
            "Aperçu indisponible : le sandbox n'est pas configuré.",
            status=503,
        )
    return control


async def _package_output(session: AsyncSession, run_id: str) -> dict[str, Any]:
    step = await session.scalar(
        select(RunStep).where(RunStep.run_id == run_id, RunStep.name == "package")
    )
    return dict(step.output or {}) if step else {}


def _preview_command(output: dict[str, Any]) -> list[str]:
    preview = output.get("preview")
    argv = preview.get("argv") if isinstance(preview, dict) else None
    valid = (
        isinstance(argv, list)
        and bool(argv)
        and all(isinstance(a, str) for a in argv)
        and argv[0] in _EXECUTABLES
    )
    if not valid:
        raise PreviewError(
            "preview_unavailable", "Ce livrable n'a pas d'aperçu interactif.", status=409
        )
    return list(argv)  # type: ignore[arg-type]


def _url(public_url: str, run_id: str) -> str:
    return f"{public_url.rstrip('/')}/preview/{run_id}/"
