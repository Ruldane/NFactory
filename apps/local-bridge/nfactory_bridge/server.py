"""HTTP layer of the local bridge. Standard library only.

GET    /health              {"status", "paired", "version"}: no token, nothing else revealed
POST   /pair                {"code": "ABCD-EFGH"} -> {"token": ...} once; 403 pairing_refused
DELETE /pair                forget the token (needs it)
GET    /runtimes            {"runtimes": [...]} detected tools (needs the token)
GET    /repos               {"repos": [{"id", "name"}]} repositories the user authorized
POST   /tasks               {"runtime": "codex" | "claude", "repo_id", "task", "consent": true}
                            -> 202; "claude" prepares a handoff the user runs themselves
GET    /tasks/<id>          status, events, manifest, diff
POST   /tasks/<id>/cancel   stop a running task
POST   /tasks/<id>/collect  import what the user's Claude Code changed (handoff)
GET    /tasks/<id>/snapshot the finished task's files (base64), tested by NFactory's sandbox
POST   /tasks/<id>/discard  remove the task's worktree and branch

Each route runs a fixed action: no request field ever becomes a command or a path (a
repository is named by the id the user gave it on this machine). The server binds to an
IPv4 loopback address only. Requests carrying an `Origin` header come from a browser and
are refused (403), as are requests naming a foreign host (421, DNS rebinding): the bridge
talks to the NFactory API server only, which reaches it as host.docker.internal.
"""

import ipaddress
import json
import re
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Protocol

from nfactory_bridge import __version__
from nfactory_bridge.pairing import Pairing, PairingRefused
from nfactory_bridge.tasks import TaskRefused

# A task of 4,000 accented characters is about 24 KB once JSON-escaped.
MAX_BODY_BYTES = 32_768
# A refused body up to this size is read and dropped first: answering while the client
# still sends makes Windows abort the connection before the client sees the 413.
DRAIN_BYTES = 1_048_576
ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "host.docker.internal"})
RUNTIMES = frozenset({"codex", "claude"})
_TASK_PATH = re.compile(
    r"^/tasks/(t_[0-9a-f]{12}|[A-Za-z0-9_]{1,40})(/cancel|/discard|/collect|/snapshot)?$"
)
# The method each task route accepts (no suffix: read the task).
_TASK_METHODS = {
    None: "GET",
    "/snapshot": "GET",
    "/cancel": "POST",
    "/discard": "POST",
    "/collect": "POST",
}
_REFUSAL_STATUS = {
    "not_found": 404,
    "repo_not_allowed": 403,
    "invalid_task": 400,
    "codex_refused": 400,
}

Detect = Callable[[], list[dict[str, Any]]]


class TaskBoard(Protocol):
    def start_codex(self, repo_id: str, task: str) -> dict[str, Any]: ...
    def get(self, task_id: str) -> dict[str, Any]: ...
    def cancel(self, task_id: str) -> dict[str, Any]: ...
    def discard(self, task_id: str) -> dict[str, Any]: ...
    def start_handoff(self, repo_id: str, task: str) -> dict[str, Any]: ...
    def collect(self, task_id: str) -> dict[str, Any]: ...
    def snapshot(self, task_id: str) -> dict[str, Any]: ...


class RepoList(Protocol):
    def public(self) -> list[dict[str, str]]: ...


def make_server(
    host: str,
    port: int,
    *,
    pairing: Pairing,
    detect: Detect,
    tasks: TaskBoard | None = None,
    repos: RepoList | None = None,
) -> ThreadingHTTPServer:
    if not _is_ipv4_loopback(host):
        raise ValueError(f"Le pont n'écoute que sur une adresse loopback IPv4, pas « {host} ».")

    class Handler(BaseHTTPRequestHandler):
        server_version = "nfactory-bridge"
        sys_version = ""

        def do_GET(self) -> None:
            self._route("GET")

        def do_POST(self) -> None:
            self._route("POST")

        def do_DELETE(self) -> None:
            self._route("DELETE")

        def _route(self, method: str) -> None:
            if not self._trusted():
                return
            path = self.path
            if path == "/health":
                if method != "GET":
                    return self._error(405, "method_not_allowed", "Méthode non autorisée.")
                return self._json(
                    200, {"status": "ok", "paired": pairing.paired, "version": __version__}
                )
            if path == "/pair":
                if method == "POST":
                    return self._pair()
                if method == "DELETE":
                    return self._unpair()
                return self._error(405, "method_not_allowed", "Méthode non autorisée.")
            match = _TASK_PATH.match(path)
            known = path in ("/runtimes", "/repos", "/tasks") or match is not None
            if not known:
                return self._error(404, "not_found", "Route inconnue.")
            if not self._authorized():
                return None
            if path == "/runtimes" and method == "GET":
                return self._json(200, {"runtimes": detect()})
            if path == "/repos" and method == "GET":
                return self._json(200, {"repos": repos.public() if repos else []})
            if path == "/tasks" and method == "POST":
                return self._start_task()
            if match and method == _TASK_METHODS[match.group(2)]:
                return self._task_action(match.group(1), match.group(2))
            return self._error(405, "method_not_allowed", "Méthode non autorisée.")

        def _pair(self) -> None:
            body = self._body()
            if body is None:
                return
            code = body.get("code") if isinstance(body, dict) else None
            if not isinstance(code, str):
                return self._error(400, "invalid_request", "Champ « code » attendu.")
            try:
                token = pairing.pair(code)
            except PairingRefused as exc:
                return self._error(403, "pairing_refused", str(exc))
            self._json(200, {"token": token})

        def _unpair(self) -> None:
            if self._authorized():
                pairing.unpair()
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()

        def _start_task(self) -> None:
            body = self._body()
            if body is None:
                return
            if tasks is None:
                return self._error(503, "tasks_unavailable", "Tâches indisponibles sur ce pont.")
            if not isinstance(body, dict) or body.get("consent") is not True:
                return self._error(
                    403, "consent_required", "L'accord explicite de l'utilisateur est requis."
                )
            runtime, repo_id, task = body.get("runtime"), body.get("repo_id"), body.get("task")
            if runtime not in RUNTIMES or not isinstance(repo_id, str) or not isinstance(task, str):
                return self._error(400, "invalid_request", "runtime, repo_id et task attendus.")
            try:
                start = tasks.start_codex if runtime == "codex" else tasks.start_handoff
                view = start(repo_id, task)
            except TaskRefused as exc:
                return self._refused(exc)
            self._json(202, view)

        def _task_action(self, task_id: str, action: str | None) -> None:
            if tasks is None:
                return self._error(404, "not_found", "Tâche inconnue.")
            try:
                if action == "/cancel":
                    view = tasks.cancel(task_id)
                elif action == "/discard":
                    view = tasks.discard(task_id)
                elif action == "/collect":
                    view = tasks.collect(task_id)
                elif action == "/snapshot":
                    view = tasks.snapshot(task_id)
                else:
                    view = tasks.get(task_id)
            except TaskRefused as exc:
                return self._refused(exc)
            self._json(200, view)

        def _refused(self, exc: TaskRefused) -> None:
            self._error(_REFUSAL_STATUS.get(exc.code, 409), exc.code, str(exc))

        def _trusted(self) -> bool:
            name, _, port = (self.headers.get("Host") or "").rpartition(":")
            address = self.server.server_address
            listening = str(address[1]) if isinstance(address, tuple) else ""
            if name not in ALLOWED_HOSTS or port != listening:
                self._error(421, "unknown_host", "Hôte non reconnu.")
                return False
            if self.headers.get("Origin") is not None:
                self._error(403, "browser_refused", "Le pont ne répond pas aux navigateurs.")
                return False
            return True

        def _authorized(self) -> bool:
            header = self.headers.get("Authorization") or ""
            token = header.removeprefix("Bearer ") if header.startswith("Bearer ") else ""
            if pairing.authorized(token):
                return True
            self._error(401, "unauthorized", "Jeton absent ou invalide : appairez NFactory.")
            return False

        def _body(self) -> Any:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            if length < 0 or length > MAX_BODY_BYTES:
                if 0 < length <= DRAIN_BYTES:
                    self.rfile.read(length)
                self._error(413, "body_too_large", "Requête trop volumineuse.")
                self.close_connection = True
                return None
            try:
                return json.loads(self.rfile.read(length) or b"null")
            except ValueError:
                self._error(400, "invalid_request", "JSON invalide.")
                return None

        def _json(self, status: int, payload: Any) -> None:
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _error(self, status: int, code: str, message: str) -> None:
            self._json(status, {"error": {"code": code, "message": message}})

        def log_message(self, format: str, *args: Any) -> None:
            return  # the request line is enough noise for a local tool; nothing sensitive

    return ThreadingHTTPServer((host, port), Handler)


def _is_ipv4_loopback(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.version == 4 and address.is_loopback
