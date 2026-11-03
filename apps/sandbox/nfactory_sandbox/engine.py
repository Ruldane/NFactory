"""Minimal Docker Engine client over its Unix socket. Standard library only.

Only the calls the supervisor needs: create, start, wait, kill, inspect, logs, remove,
list. The transport is passed in, so the logic is tested without Docker.
"""

import http.client
import json
import socket
import struct
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

API_VERSION = "1.45"  # first version with volume subpath mounts (Docker Engine 26)
_LOG_TAIL_LINES = 4000

Transport = Callable[..., tuple[int, bytes]]


class EngineError(RuntimeError):
    """The Docker Engine refused a call or cannot be reached."""


class UnixTransport:
    """HTTP over the Docker socket: `(method, path, body, timeout) -> (status, bytes)`."""

    def __init__(self, socket_path: str = "/var/run/docker.sock") -> None:
        self._socket_path = socket_path

    def __call__(
        self, method: str, path: str, body: Any = None, timeout: float | None = 30
    ) -> tuple[int, bytes]:
        connection = _UnixConnection(self._socket_path, timeout)
        try:
            data = None if body is None else json.dumps(body).encode()
            headers = {"Content-Type": "application/json"} if data is not None else {}
            connection.request(method, path, body=data, headers=headers)
            response = connection.getresponse()
            return response.status, response.read()
        except TimeoutError:
            raise
        except OSError as exc:
            raise EngineError(f"Docker Engine unreachable: {type(exc).__name__}") from exc
        finally:
            connection.close()


class _UnixConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: str, timeout: float | None) -> None:
        super().__init__("localhost", timeout=timeout)
        self._socket_path = socket_path

    def connect(self) -> None:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)  # type: ignore[attr-defined,unused-ignore]
        sock.settimeout(self.timeout)
        sock.connect(self._socket_path)
        self.sock = sock


class DockerEngine:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def ping(self) -> bool:
        try:
            status, _ = self._transport("GET", "/_ping", None, 5)
        except (EngineError, TimeoutError):
            return False
        return status == 200

    def create(self, spec: dict[str, Any], name: str | None = None) -> str:
        path = f"/containers/create?name={quote(name, safe='')}" if name else "/containers/create"
        data = self._json("POST", path, spec, ok=(201,))
        return str(data["Id"])

    def running(self, container: str) -> bool:
        status, data = self._transport(
            "GET", f"/v{API_VERSION}/containers/{container}/json", None, 30
        )
        if status == 404:
            return False
        if status != 200:
            raise EngineError(f"GET /containers/{container}/json -> {status}: {_message(data)}")
        return bool(json.loads(data).get("State", {}).get("Running"))

    def start(self, container: str) -> None:
        self._call("POST", f"/containers/{container}/start", ok=(204, 304))

    def wait(self, container: str, timeout_s: float) -> int:
        """Exit code of the container; TimeoutError once `timeout_s` has passed."""
        data = self._json("POST", f"/containers/{container}/wait", timeout=timeout_s)
        return int(data["StatusCode"])

    def kill(self, container: str) -> None:
        self._call("POST", f"/containers/{container}/kill", ok=(204, 404, 409))

    def oom_killed(self, container: str) -> bool:
        data = self._json("GET", f"/containers/{container}/json")
        return bool(data.get("State", {}).get("OOMKilled"))

    def logs(self, container: str) -> tuple[str, str]:
        query = f"stdout=1&stderr=1&tail={_LOG_TAIL_LINES}"
        return demux(self._call("GET", f"/containers/{container}/logs?{query}"))

    def remove(self, container: str) -> None:
        self._call("DELETE", f"/containers/{container}?force=1&v=1", ok=(204, 404, 409))

    def leftovers(self, label: str) -> list[str]:
        filters = quote(json.dumps({"label": [label]}), safe="")
        data = self._json("GET", f"/containers/json?all=1&filters={filters}")
        return [str(item["Id"]) for item in data]

    def _json(
        self,
        method: str,
        path: str,
        body: Any = None,
        ok: tuple[int, ...] = (200,),
        timeout: float | None = 30,
    ) -> Any:
        return json.loads(self._call(method, path, body, ok, timeout) or b"null")

    def _call(
        self,
        method: str,
        path: str,
        body: Any = None,
        ok: tuple[int, ...] = (200,),
        timeout: float | None = 30,
    ) -> bytes:
        status, data = self._transport(method, f"/v{API_VERSION}{path}", body, timeout)
        if status not in ok:
            raise EngineError(f"{method} {path.split('?')[0]} -> {status}: {_message(data)}")
        return data


def demux(raw: bytes) -> tuple[str, str]:
    """Split Docker's multiplexed log stream (8-byte frame headers) into stdout, stderr."""
    streams: dict[int, list[bytes]] = {1: [], 2: []}
    offset = 0
    while offset + 8 <= len(raw):
        kind, size = struct.unpack_from(">BxxxI", raw, offset)
        offset += 8
        streams.setdefault(kind, []).append(raw[offset : offset + size])
        offset += size
    out, err = (b"".join(streams[k]).decode("utf-8", "replace") for k in (1, 2))
    return out, err


def _message(data: bytes) -> str:
    try:
        return str(json.loads(data).get("message", ""))[:300]
    except (ValueError, AttributeError):
        return data[:300].decode("utf-8", "replace")
