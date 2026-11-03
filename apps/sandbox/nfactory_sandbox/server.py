"""HTTP layer of the sandbox supervisor. Standard library only.

POST /run   {"workspace": "run_x", "argv": ["python" | "pwsh" | "node", ...], "timeout_s": 120}
            Authorization: Bearer <NFACTORY_SANDBOX_TOKEN>
GET  /health  200 when the Docker Engine answers, else 503
POST   /previews        {"workspace": "run_x", "argv": [...]}  start (or reuse) a preview
GET    /previews/<ws>   {"running": bool, ...}
DELETE /previews/<ws>   stop it
            all three need the same bearer token as /run

The request is validated here; the executor runs it (one container per command).
Statuses: 400 invalid, 401 token, 413 body too large, 502 engine failure, 503 busy.
"""

import hmac
import json
import re
import sys
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Protocol
from urllib.parse import unquote

WORKSPACE = re.compile(r"^[A-Za-z0-9_-]+$")
EXECUTABLES = ("python", "pwsh", "node")  # installed in the sandbox image
MAX_BODY_BYTES = 64_000


class BadRequest(ValueError):
    pass


class Busy(RuntimeError):
    """No capacity left (answered 503)."""


class Previews(Protocol):
    def start(self, workspace: str, argv: list[str]) -> dict[str, Any]: ...
    def status(self, workspace: str) -> dict[str, Any]: ...
    def stop(self, workspace: str) -> None: ...


class Executor(Protocol):
    def ready(self) -> bool: ...
    def run(self, workspace: str, argv: list[str], timeout_s: int) -> dict[str, Any]: ...


@dataclass(frozen=True)
class Config:
    token: str
    executor: Executor
    max_timeout_s: int = 600
    max_parallel: int = 4
    queue_wait_s: float = 60.0
    previews: Previews | None = None


def validate(config: Config, body: Any) -> tuple[str, list[str], int]:
    workspace, argv = validate_command(body)
    timeout_s = body.get("timeout_s", 120)
    if not isinstance(timeout_s, int) or not 1 <= timeout_s <= config.max_timeout_s:
        raise BadRequest("invalid timeout")
    return workspace, argv, timeout_s


def validate_command(body: Any) -> tuple[str, list[str]]:
    if not isinstance(body, dict):
        raise BadRequest("body must be a JSON object")
    workspace = check_workspace(body.get("workspace"))
    argv = body.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
        raise BadRequest("argv must be a non-empty list of strings")
    if argv[0] not in EXECUTABLES:
        raise BadRequest(f"executable not allowed: {argv[0]}")
    return workspace, argv


def check_workspace(workspace: Any) -> str:
    if not isinstance(workspace, str) or not WORKSPACE.fullmatch(workspace):
        raise BadRequest("invalid workspace")
    return workspace


def make_server(host: str, port: int, config: Config) -> ThreadingHTTPServer:
    slots = threading.BoundedSemaphore(config.max_parallel)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.startswith("/previews/"):
                self._preview_route(lambda p, ws: p.status(ws))
            elif self.path != "/health":
                self._reply(404, {"error": "not found"})
            elif config.executor.ready():
                self._reply(200, {"status": "ok"})
            else:
                self._reply(503, {"status": "engine unavailable"})

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY_BYTES:
                self.close_connection = True
                self._reply(413, {"error": "body too large"})
                return
            # Read the (bounded) body before any reply: closing a socket with unread
            # data resets it, and the client would see an abort instead of the status.
            raw = self.rfile.read(length)
            if self.path == "/previews":
                self._start_preview(raw)
                return
            if self.path != "/run":
                self._reply(404, {"error": "not found"})
                return
            if not self._authorized():
                return
            try:
                request = validate(config, json.loads(raw))
            except (BadRequest, ValueError) as exc:
                self._reply(400, {"error": str(exc)})
                return
            if not slots.acquire(timeout=config.queue_wait_s):
                self._reply(503, {"error": "busy"})
                return
            try:
                self._reply(200, config.executor.run(*request))
            except BadRequest as exc:
                self._reply(400, {"error": str(exc)})
            except Exception as exc:  # engine failure: details stay in this log
                sys.stderr.write(f"sandbox: run failed: {type(exc).__name__}: {exc}\n")
                self._reply(502, {"error": "sandbox engine failure"})
            finally:
                slots.release()

        def do_DELETE(self) -> None:
            self._preview_route(lambda p, ws: p.stop(ws) or {"stopped": True})

        def _authorized(self) -> bool:
            supplied = self.headers.get("Authorization", "").removeprefix("Bearer ")
            if config.token and hmac.compare_digest(supplied, config.token):
                return True
            self._reply(401, {"error": "unauthorized"})
            return False

        def _start_preview(self, raw: bytes) -> None:
            if config.previews is None:
                self._reply(404, {"error": "not found"})
                return
            if not self._authorized():
                return
            previews = config.previews
            try:
                workspace, argv = validate_command(json.loads(raw))
            except (BadRequest, ValueError) as exc:
                self._reply(400, {"error": str(exc)})
                return
            self._answer(lambda: previews.start(workspace, argv))

        def _preview_route(self, action: Any) -> None:
            if config.previews is None:
                self._reply(404, {"error": "not found"})
                return
            if not self._authorized():
                return
            previews = config.previews
            try:
                workspace = check_workspace(unquote(self.path.removeprefix("/previews/")))
            except BadRequest as exc:
                self._reply(400, {"error": str(exc)})
                return
            self._answer(lambda: action(previews, workspace))

        def _answer(self, action: Any) -> None:
            try:
                self._reply(200, action())
            except BadRequest as exc:
                self._reply(400, {"error": str(exc)})
            except Busy as exc:
                self._reply(503, {"error": str(exc)})
            except Exception as exc:  # engine failure: details stay in this log
                sys.stderr.write(f"sandbox: preview failed: {type(exc).__name__}: {exc}\n")
                self._reply(502, {"error": "sandbox engine failure"})

        def _reply(self, status: int, body: dict[str, Any]) -> None:
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: Any) -> None:
            # Log the request line only: never bodies (they may contain project content).
            sys.stderr.write(
                f"sandbox: {self.command} {self.path} {args[1] if len(args) > 1 else ''}\n"
            )

    return ThreadingHTTPServer((host, port), Handler)
