"""Local coding tools through the bridge on the user's machine (tasks 4.1, 4.2, ADR-0008).

The bridge runs outside Docker, next to codex / claude / gh, and listens on 127.0.0.1
only; the API reaches it as host.docker.internal. Pairing trades the one-time code the
bridge printed for a token, stored encrypted in the SecretStore (a `local_bridge`
connection) and never sent back. The API only relays what the bridge detected.

Interface: local_runtimes / pair / unpair / paired_token, BridgeClient (the port), HttpBridge (its
adapter), BridgeUnreachable / BridgeUnauthorized / BridgeRefused.
"""

import re
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError
from app.schemas.local_runtimes import (
    BridgeState,
    BridgeStatus,
    LocalRuntime,
    LocalRuntimesOut,
)
from app.services.identity import RequestContext
from nfactory_core.connections import workspace_connections
from nfactory_core.local_bridge import KIND, bridge_token
from nfactory_core.models import ProviderConnection
from nfactory_core.secrets import SecretStore, SecretUnreadableError

_TIMEOUT_S = 30.0  # detection runs a few official commands on the user's machine
_PUBLISH_TIMEOUT_S = 120.0  # commit, push and a draft PR through gh
START_HINT = (
    "Pont local non joignable : lancez ./scripts/bridge.ps1 (ou scripts/bridge.sh) "
    "sur cet ordinateur."
)
_MESSAGES = {
    "unpaired": "Pont local démarré : saisissez le code d'appairage qu'il affiche.",
    "paired": "Pont local associé.",
    "token_rejected": (
        "Le pont ne reconnaît plus NFactory : relancez-le avec -Pair et saisissez le nouveau code."
    ),
}


class BridgeUnreachable(Exception):
    """No bridge answers, or it answered something unexpected."""


class BridgeUnauthorized(Exception):
    """The bridge refused the token."""


class BridgeRefused(Exception):
    """The bridge refused a request (a pairing code, a task); its code, status and French
    message are kept so the user reads the bridge's own reason."""

    def __init__(self, message: str, *, code: str = "pairing_refused", status: int = 403) -> None:
        super().__init__(message)
        self.code, self.status = code, status


class BridgeClient(Protocol):
    async def health(self) -> dict[str, Any]: ...
    async def pair(self, code: str) -> str: ...
    async def runtimes(self, token: str) -> list[dict[str, Any]]: ...
    async def unpair(self, token: str) -> None: ...
    async def repos(self, token: str) -> list[dict[str, Any]]: ...
    async def start_task(self, token: str, body: dict[str, Any]) -> dict[str, Any]: ...
    async def task(self, token: str, task_id: str, action: str | None = None) -> dict[str, Any]: ...
    async def publish(self, token: str, task_id: str, body: dict[str, Any]) -> dict[str, Any]: ...
    async def publication(self, token: str, task_id: str) -> dict[str, Any]: ...


class HttpBridge:
    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")

    async def health(self) -> dict[str, Any]:
        body = await self._call("GET", "/health")
        return body if isinstance(body, dict) else {}

    async def pair(self, code: str) -> str:
        body = await self._call("POST", "/pair", json={"code": code})
        token = body.get("token") if isinstance(body, dict) else None
        if not isinstance(token, str) or not token:
            raise BridgeUnreachable
        return token

    async def runtimes(self, token: str) -> list[dict[str, Any]]:
        body = await self._call("GET", "/runtimes", token=token)
        found = body.get("runtimes") if isinstance(body, dict) else None
        return found if isinstance(found, list) else []

    async def unpair(self, token: str) -> None:
        await self._call("DELETE", "/pair", token=token)

    async def repos(self, token: str) -> list[dict[str, Any]]:
        body = await self._call("GET", "/repos", token=token, refusals=True)
        found = body.get("repos") if isinstance(body, dict) else None
        return found if isinstance(found, list) else []

    async def start_task(self, token: str, body: dict[str, Any]) -> dict[str, Any]:
        answer = await self._call("POST", "/tasks", token=token, json=body, refusals=True)
        return answer if isinstance(answer, dict) else {}

    async def task(self, token: str, task_id: str, action: str | None = None) -> dict[str, Any]:
        method, path = (
            ("POST", f"/tasks/{task_id}/{action}") if action else ("GET", f"/tasks/{task_id}")
        )
        answer = await self._call(method, path, token=token, refusals=True)
        return answer if isinstance(answer, dict) else {}

    async def publish(self, token: str, task_id: str, body: dict[str, Any]) -> dict[str, Any]:
        answer = await self._call(
            "POST",
            f"/tasks/{task_id}/publish",
            token=token,
            json=body,
            refusals=True,
            wait_s=_PUBLISH_TIMEOUT_S,
        )
        return answer if isinstance(answer, dict) else {}

    async def publication(self, token: str, task_id: str) -> dict[str, Any]:
        answer = await self._call(
            "GET", f"/tasks/{task_id}/publication", token=token, refusals=True, wait_s=60.0
        )
        return answer if isinstance(answer, dict) else {}

    async def _call(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        json: Any = None,
        refusals: bool = False,
        wait_s: float = _TIMEOUT_S,
    ) -> Any:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            async with httpx.AsyncClient(timeout=wait_s) as http:
                response = await http.request(
                    method, f"{self._base}{path}", headers=headers, json=json
                )
        except httpx.HTTPError as exc:
            raise BridgeUnreachable from exc
        if response.status_code == 401:
            raise BridgeUnauthorized
        if response.status_code == 403 and path == "/pair":
            raise BridgeRefused(_bridge_message(response))
        if refusals and 400 <= response.status_code < 500:
            code = _bridge_code(response)
            if code is not None:
                raise BridgeRefused(
                    _bridge_message(response), code=code, status=response.status_code
                )
        if response.status_code == 204:
            return None
        if response.status_code not in (200, 202):
            raise BridgeUnreachable
        try:
            return response.json()
        except ValueError as exc:
            raise BridgeUnreachable from exc


async def local_runtimes(
    session: AsyncSession, ctx: RequestContext, bridge: BridgeClient, store: SecretStore
) -> LocalRuntimesOut:
    try:
        health = await bridge.health()
    except BridgeUnreachable:
        return _out("unreachable")
    version = str(health.get("version") or "")[:20] or None
    row = await _connection(session, ctx)
    token = await _token(session, store, row)
    if row is None or token is None:
        return _out("unpaired", version=version)
    try:
        found = await bridge.runtimes(token)
    except BridgeUnauthorized:
        row.status = "token_rejected"
        await session.commit()
        return _out("token_rejected", version=version)
    except BridgeUnreachable:
        return _out("unreachable")
    runtimes = [r for r in (_runtime(item) for item in found) if r is not None]
    row.status = "connected"
    row.last_checked_at = datetime.now(UTC)
    await session.commit()
    return _out("paired", version=version, runtimes=runtimes)


async def pair(
    session: AsyncSession,
    ctx: RequestContext,
    bridge: BridgeClient,
    store: SecretStore,
    code: str,
) -> LocalRuntimesOut:
    try:
        token = await bridge.pair(code.strip().upper())
    except BridgeUnreachable as exc:
        raise AppError(503, "bridge_unreachable", START_HINT) from exc
    except BridgeRefused as exc:
        raise AppError(403, "pairing_refused", str(exc)) from exc
    row = await _connection(session, ctx)
    if row is None:
        row = ProviderConnection(
            workspace_id=ctx.default_workspace_id, kind=KIND, display_name="Pont local"
        )
        session.add(row)
    else:
        await store.delete(session, row.secret_ref)
    row.secret_ref = await store.put(session, ctx.default_workspace_id, token)
    row.status = "connected"
    row.last_error = None
    await session.commit()
    return await local_runtimes(session, ctx, bridge, store)


async def unpair(
    session: AsyncSession, ctx: RequestContext, bridge: BridgeClient, store: SecretStore
) -> None:
    """Forget the token here; tell the bridge too when it is running (best effort)."""
    row = await _connection(session, ctx)
    if row is None:
        return
    token = await _token(session, store, row)
    if token is not None:
        try:
            await bridge.unpair(token)
        except (BridgeUnreachable, BridgeUnauthorized):
            pass  # a stopped or re-paired bridge already does not accept this token
    await store.delete(session, row.secret_ref)
    await session.delete(row)
    await session.commit()


async def paired_token(
    session: AsyncSession, ctx: RequestContext, store: SecretStore
) -> str | None:
    """The bridge token, read at the last moment; None when not paired."""
    return await bridge_token(session, ctx.default_workspace_id, store)


async def _connection(session: AsyncSession, ctx: RequestContext) -> ProviderConnection | None:
    return (await workspace_connections(session, ctx.default_workspace_id)).get(KIND)


async def _token(
    session: AsyncSession, store: SecretStore, row: ProviderConnection | None
) -> str | None:
    if row is None or row.secret_ref is None:
        return None
    try:
        return await store.get(session, row.secret_ref)
    except SecretUnreadableError:
        return None  # the secret key changed: pairing again is the only way


def _runtime(item: Any) -> LocalRuntime | None:
    try:
        return LocalRuntime.model_validate(item)
    except ValidationError:
        return None  # an unknown tool or status is left out rather than guessed


def _bridge_message(response: httpx.Response) -> str:
    try:
        message = response.json()["error"]["message"]
    except (ValueError, KeyError, TypeError):
        message = None
    return message[:200] if isinstance(message, str) else "Code d'appairage refusé."


def _bridge_code(response: httpx.Response) -> str | None:
    try:
        code = response.json()["error"]["code"]
    except (ValueError, KeyError, TypeError):
        return None
    return code if isinstance(code, str) and re.fullmatch(r"[a-z_]{1,40}", code) else None


def _out(
    status: BridgeStatus, *, version: str | None = None, runtimes: list[LocalRuntime] | None = None
) -> LocalRuntimesOut:
    message = START_HINT if status == "unreachable" else _MESSAGES[status]
    state = BridgeState(status=status, message=message, version=version)
    return LocalRuntimesOut(bridge=state, runtimes=runtimes or [])
