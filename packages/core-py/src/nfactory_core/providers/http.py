"""The one HTTP transport every adapter uses: JSON in, JSON out, errors normalized.

Every failure leaves as a `ProviderError`: timeouts, unreachable hosts, error statuses
(classified per provider), unreadable bodies, and MiniMax's HTTP-200 errors.
"""

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator, Callable, Mapping
from typing import Any

import httpx

from nfactory_core.providers.errors import ProviderError, classify_http_error, minimax_status
from nfactory_core.providers.ssrf import UnsafeUrlError

UrlGuard = Callable[[str], None]

DEFAULT_TIMEOUT_S = 300.0  # agent replies can be long; streaming is not needed for them
CONNECT_TIMEOUT_S = 10.0


class ProviderHttp:
    def __init__(
        self,
        provider: str,
        base_url: str,
        headers: Mapping[str, str],
        *,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        guard: UrlGuard | None = None,
    ) -> None:
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self._headers = dict(headers)
        self._timeout = httpx.Timeout(timeout_s, connect=CONNECT_TIMEOUT_S)
        self._guard = guard

    def _client(self) -> httpx.AsyncClient:
        # Redirects are not followed: a 3xx could point the key at another host.
        return httpx.AsyncClient(
            headers=self._headers, timeout=self._timeout, follow_redirects=False
        )

    async def _check(self, url: str) -> None:
        if self._guard is None:
            return
        try:
            await asyncio.to_thread(self._guard, url)
        except UnsafeUrlError as exc:
            raise ProviderError("blocked", provider=self.provider, detail=str(exc)) from exc

    async def get_json(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        url = self.base_url + path
        await self._check(url)
        async with self._client() as client:
            response = await self._send(client.get(url, params=params))
        return self._parse(response)

    async def post_json(self, path: str, body: Mapping[str, Any]) -> Any:
        url = self.base_url + path
        await self._check(url)
        async with self._client() as client:
            response = await self._send(client.post(url, json=body))
        return self._parse(response)

    @contextlib.asynccontextmanager
    async def post_stream(
        self, path: str, body: Mapping[str, Any]
    ) -> AsyncIterator[AsyncIterator[str]]:
        """Open a streamed POST and yield its lines. Error statuses raise before."""
        url = self.base_url + path
        await self._check(url)
        async with self._client() as client:
            try:
                async with client.stream("POST", url, json=body) as response:
                    if response.status_code >= 400:
                        await response.aread()
                        raise self._error(response)
                    yield self._lines(response)
            except httpx.TimeoutException as exc:
                raise ProviderError("timeout", provider=self.provider, detail=str(exc)) from exc
            except httpx.TransportError as exc:
                raise self._unreachable(exc) from exc

    async def _lines(self, response: httpx.Response) -> AsyncIterator[str]:
        try:
            async for line in response.aiter_lines():
                yield line
        except httpx.TimeoutException as exc:
            raise ProviderError("timeout", provider=self.provider, detail=str(exc)) from exc
        except httpx.TransportError as exc:
            raise self._unreachable(exc) from exc

    async def _send(self, request: Any) -> httpx.Response:
        try:
            response: httpx.Response = await request
        except httpx.TimeoutException as exc:
            raise ProviderError("timeout", provider=self.provider, detail=str(exc)) from exc
        except httpx.TransportError as exc:
            raise self._unreachable(exc) from exc
        if response.status_code >= 400:
            raise self._error(response)
        return response

    def _unreachable(self, exc: Exception) -> ProviderError:
        return ProviderError(
            "unavailable",
            provider=self.provider,
            detail=f"connexion impossible ({type(exc).__name__})",
        )

    def _error(self, response: httpx.Response) -> ProviderError:
        return classify_http_error(
            self.provider, response.status_code, _body(response), response.headers
        )

    def _parse(self, response: httpx.Response) -> Any:
        try:
            body = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise ProviderError(
                "invalid_response", provider=self.provider, status=response.status_code
            ) from exc
        if isinstance(body, dict) and minimax_status(body):
            raise classify_http_error(self.provider, response.status_code, body, response.headers)
        return body


def _body(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except (json.JSONDecodeError, ValueError):
        return {"error": response.text[:300]}
    return body if isinstance(body, dict) else {"error": str(body)[:300]}


def parse_json_line(provider: str, data: str) -> dict[str, Any]:
    """One streamed JSON object (SSE data or NDJSON line)."""
    try:
        value = json.loads(data)
    except json.JSONDecodeError as exc:
        raise ProviderError("invalid_response", provider=provider, detail=data[:100]) from exc
    if not isinstance(value, dict):
        raise ProviderError("invalid_response", provider=provider, detail=data[:100])
    return value
