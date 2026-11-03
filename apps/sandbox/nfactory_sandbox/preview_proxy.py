"""Preview gateway: /preview/<workspace>/<path> -> that workspace's preview container.

It runs as its own service, without docker.sock: it sits on the internal preview network
and reaches each preview by its container name. It is the only way into a preview, so it
also enforces what the browser may do with one:
- cookies and credentials never cross it, in either direction;
- only the dashboard may frame a preview (CSP frame-ancestors);
- any other path is refused.
Previews are served on their own origin (another port), never the dashboard's.
"""

import http.client
import re
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

_ROUTE = re.compile(r"^/preview/([A-Za-z0-9_-]{1,64})(/.*)?$")
MAX_BODY_BYTES = 10 * 1024**2
STARTUP_WAIT_S = 30.0  # how long a just-started app may take to listen
_TIMEOUT_S = 30
# Hop-by-hop headers (RFC 9110 §7.6.1) plus everything that carries a credential.
_DROP_REQUEST = {
    "connection", "keep-alive", "proxy-connection", "te", "trailer", "transfer-encoding",
    "upgrade", "host", "content-length", "cookie", "authorization", "proxy-authorization",
}  # fmt: skip
_DROP_RESPONSE = {
    "connection", "keep-alive", "transfer-encoding", "trailer", "upgrade", "content-length",
    "set-cookie", "set-cookie2", "content-security-policy", "x-frame-options",
}  # fmt: skip

Resolver = Callable[[str], tuple[str, int] | None]


def make_proxy(
    host: str,
    port: int,
    *,
    resolve: Resolver,
    frame_ancestors: str,
    startup_wait_s: float = STARTUP_WAIT_S,
) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:
            self._forward()

        def do_HEAD(self) -> None:
            self._forward()

        def do_POST(self) -> None:
            self._forward()

        def do_PUT(self) -> None:
            self._forward()

        def do_PATCH(self) -> None:
            self._forward()

        def do_DELETE(self) -> None:
            self._forward()

        def _forward(self) -> None:
            path, _, query = self.path.partition("?")
            route = _ROUTE.fullmatch(path)
            if route is None:
                self._page(404, "Adresse inconnue.")
                return
            workspace, rest = route.group(1), route.group(2)
            if rest is None:  # relative assets need the trailing slash
                self._redirect(f"/preview/{workspace}/" + (f"?{query}" if query else ""))
                return
            target = resolve(workspace)
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY_BYTES:
                self._page(413, "Requête trop volumineuse.")
                return
            body = self.rfile.read(length) if length else None
            if target is None:
                self._stopped()
                return
            headers = {k: v for k, v in self.headers.items() if k.lower() not in _DROP_REQUEST}
            try:
                upstream = _connect(target, startup_wait_s)
                upstream.request(self.command, rest + (f"?{query}" if query else ""), body, headers)
                response = upstream.getresponse()
                data = response.read(MAX_BODY_BYTES + 1)
            except (OSError, http.client.HTTPException):
                self._stopped()
                return
            if len(data) > MAX_BODY_BYTES:
                self._page(502, "Réponse de l'aperçu trop volumineuse.")
                return
            self.send_response(response.status)
            for key, value in response.getheaders():
                if key.lower() not in _DROP_RESPONSE:
                    self.send_header(key, value)
            self._security_headers()
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        def _stopped(self) -> None:
            self._page(502, "Aperçu arrêté. Relancez-le depuis NFactory.")

        def _redirect(self, location: str) -> None:
            self.send_response(308)
            self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _page(self, status: int, message: str) -> None:
            data = (
                '<!doctype html><html lang="fr"><meta charset="utf-8">'
                f"<title>Aperçu</title><p>{message}</p></html>"
            ).encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self._security_headers()
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        def _security_headers(self) -> None:
            self.send_header("Content-Security-Policy", f"frame-ancestors {frame_ancestors}")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")

        def log_message(self, format: str, *args: Any) -> None:
            pass  # request lines may carry user data

    return ThreadingHTTPServer((host, port), Handler)


def _connect(target: tuple[str, int], startup_wait_s: float) -> http.client.HTTPConnection:
    """Connect to a preview. A refused connection means its app is still starting (the
    container exists, its name resolves): wait for it. Any other error means stopped."""
    deadline = time.monotonic() + startup_wait_s
    while True:
        connection = http.client.HTTPConnection(*target, timeout=_TIMEOUT_S)
        try:
            connection.connect()
            return connection
        except ConnectionRefusedError:
            connection.close()
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.3)


def dns_resolver(port: int) -> Resolver:
    """Production resolver: the preview's container name, on the preview network."""
    from nfactory_sandbox.previews import preview_name

    return lambda workspace: (preview_name(workspace), port)


if __name__ == "__main__":
    import os

    from nfactory_sandbox.previews import PREVIEW_PORT

    server = make_proxy(
        "0.0.0.0",  # noqa: S104 - published on 127.0.0.1 by Compose
        int(os.environ.get("NFACTORY_PREVIEW_GATEWAY_PORT", "8090")),
        resolve=dns_resolver(PREVIEW_PORT),
        frame_ancestors=os.environ.get("NFACTORY_PREVIEW_FRAME_ANCESTORS", "http://127.0.0.1:3000"),
    )
    server.serve_forever()
