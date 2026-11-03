"""The preview proxy: /preview/<run>/<path> -> the run's preview container, nothing else."""

import http.client
import socket
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, ClassVar

import pytest

from nfactory_sandbox.preview_proxy import make_proxy


class Upstream(BaseHTTPRequestHandler):
    seen: ClassVar[list[dict[str, Any]]] = []

    def do_GET(self) -> None:
        self._answer()

    def do_POST(self) -> None:
        self._answer(self.rfile.read(int(self.headers.get("Content-Length") or 0)))

    def _answer(self, body: bytes = b"") -> None:
        Upstream.seen.append({"path": self.path, "headers": dict(self.headers), "body": body})
        data = b"<html>app</html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Set-Cookie", "session=x")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args: Any) -> None:
        pass


@pytest.fixture
def proxy() -> Iterator[int]:
    Upstream.seen = []
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    threading.Thread(target=upstream.serve_forever, daemon=True).start()
    port = upstream.server_address[1]
    # Tests resolve every preview host to the fake upstream.
    server = make_proxy(
        "127.0.0.1",
        0,
        resolve=lambda workspace: ("127.0.0.1", port) if workspace == "run_1" else None,
        frame_ancestors="http://127.0.0.1:3000",
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[1]
    server.shutdown()
    upstream.shutdown()


def request(
    port: int,
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
) -> http.client.HTTPResponse:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    connection.request(method, path, body=body, headers=headers or {})
    return connection.getresponse()


def test_requests_reach_the_run_preview_without_the_prefix(proxy: int) -> None:
    response = request(proxy, "GET", "/preview/run_1/assets/app.js?v=2")

    assert response.status == 200 and response.read() == b"<html>app</html>"
    assert Upstream.seen[0]["path"] == "/assets/app.js?v=2"


def test_bodies_are_forwarded(proxy: int) -> None:
    response = request(
        proxy, "POST", "/preview/run_1/api/items", {"Content-Type": "application/json"}, b'{"a": 1}'
    )

    assert response.status == 200
    assert Upstream.seen[0]["body"] == b'{"a": 1}'


def test_credentials_never_cross_the_proxy(proxy: int) -> None:
    response = request(
        proxy, "GET", "/preview/run_1/", {"Cookie": "dash=1", "Authorization": "Bearer t"}
    )

    sent = {k.lower() for k in Upstream.seen[0]["headers"]}
    assert "cookie" not in sent and "authorization" not in sent
    assert response.getheader("Set-Cookie") is None


def test_only_the_dashboard_may_frame_a_preview(proxy: int) -> None:
    response = request(proxy, "GET", "/preview/run_1/")

    assert response.getheader("Content-Security-Policy") == "frame-ancestors http://127.0.0.1:3000"


@pytest.mark.parametrize(
    "path", ["/", "/preview/", "/preview/../etc/x", "/preview/run_9/", "/other/run_1/"]
)
def test_anything_else_is_refused(proxy: int, path: str) -> None:
    response = request(proxy, "GET", path)

    assert response.status in (404, 502)
    assert Upstream.seen == []


def test_a_stopped_preview_explains_itself(proxy: int) -> None:
    response = request(proxy, "GET", "/preview/run_2/")

    assert response.status == 502
    assert "Aperçu arrêté" in response.read().decode("utf-8")


def test_a_preview_still_starting_is_waited_for() -> None:
    # The container exists but its app is not listening yet: the gateway waits for it.
    Upstream.seen = []
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = make_proxy(
        "127.0.0.1",
        0,
        resolve=lambda workspace: ("127.0.0.1", port),
        frame_ancestors="http://127.0.0.1:3000",
        startup_wait_s=10,
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def start_late() -> None:
        time.sleep(1.5)
        upstream = ThreadingHTTPServer(("127.0.0.1", port), Upstream)
        threading.Thread(target=upstream.serve_forever, daemon=True).start()

    threading.Thread(target=start_late, daemon=True).start()
    try:
        response = request(server.server_address[1], "GET", "/preview/run_1/")
        assert response.status == 200
    finally:
        server.shutdown()
