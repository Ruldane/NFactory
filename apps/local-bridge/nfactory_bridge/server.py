"""HTTP layer of the local bridge. Standard library only.

GET    /health    {"status", "paired", "version"}: no token, nothing else revealed
POST   /pair      {"code": "ABCD-EFGH"} -> {"token": ...} once; 403 pairing_refused
DELETE /pair      forget the token (needs it)
GET    /runtimes  {"runtimes": [...]} detected tools (needs the token)

Each route runs a fixed action: no request field ever becomes a command. The server binds
to an IPv4 loopback address only. Requests carrying an `Origin` header come from a browser
and are refused (403), as are requests naming a foreign host (421, DNS rebinding): the
bridge talks to the NFactory API server only, which reaches it as host.docker.internal.
"""

import ipaddress
import json
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from nfactory_bridge import __version__
from nfactory_bridge.pairing import Pairing, PairingRefused

MAX_BODY_BYTES = 8_192
# A refused body up to this size is read and dropped first: answering while the client
# still sends makes Windows abort the connection before the client sees the 413.
DRAIN_BYTES = 1_048_576
ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "host.docker.internal"})

Detect = Callable[[], list[dict[str, Any]]]


def make_server(host: str, port: int, *, pairing: Pairing, detect: Detect) -> ThreadingHTTPServer:
    if not _is_ipv4_loopback(host):
        raise ValueError(f"Le pont n'écoute que sur une adresse loopback IPv4, pas « {host} ».")

    class Handler(BaseHTTPRequestHandler):
        server_version = "nfactory-bridge"
        sys_version = ""

        def do_GET(self) -> None:
            if not self._trusted():
                return
            if self.path == "/health":
                self._json(200, {"status": "ok", "paired": pairing.paired, "version": __version__})
            elif self.path == "/runtimes":
                if self._authorized():
                    self._json(200, {"runtimes": detect()})
            elif self.path == "/pair":
                self._error(405, "method_not_allowed", "Méthode non autorisée.")
            else:
                self._error(404, "not_found", "Route inconnue.")

        def do_POST(self) -> None:
            if not self._trusted():
                return
            if self.path in ("/health", "/runtimes"):
                self._error(405, "method_not_allowed", "Méthode non autorisée.")
                return
            if self.path != "/pair":
                self._error(404, "not_found", "Route inconnue.")
                return
            body = self._body()
            if body is None:
                return
            code = body.get("code") if isinstance(body, dict) else None
            if not isinstance(code, str):
                self._error(400, "invalid_request", "Champ « code » attendu.")
                return
            try:
                token = pairing.pair(code)
            except PairingRefused as exc:
                self._error(403, "pairing_refused", str(exc))
                return
            self._json(200, {"token": token})

        def do_DELETE(self) -> None:
            if not self._trusted():
                return
            if self.path != "/pair":
                self._error(404, "not_found", "Route inconnue.")
            elif self._authorized():
                pairing.unpair()
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()

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
