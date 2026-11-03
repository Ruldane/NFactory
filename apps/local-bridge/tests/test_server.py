"""The bridge's HTTP layer: loopback only, paired token required, no browser, no shell."""

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from nfactory_bridge.pairing import Pairing
from nfactory_bridge.server import make_server

RUNTIMES = [{"kind": "codex", "status": "connected"}]


class Bridge:
    def __init__(self, tmp_path: Path) -> None:
        self.pairing = Pairing(tmp_path / "bridge.json")
        self.detections = 0

        def detect() -> list[dict[str, Any]]:
            self.detections += 1
            return RUNTIMES

        self.server = make_server("127.0.0.1", 0, pairing=self.pairing, detect=detect)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def call(
        self,
        method: str,
        path: str,
        body: Any = None,
        token: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, Any]:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", data=data, method=method
        )
        request.add_header("Content-Type", "application/json")
        if token is not None:
            request.add_header("Authorization", f"Bearer {token}")
        for key, value in (headers or {}).items():
            request.add_header(key, value)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                raw = response.read()
                return response.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            return exc.code, json.loads(raw) if raw else None

    def paired_token(self) -> str:
        code = self.pairing.new_code()
        status, body = self.call("POST", "/pair", {"code": code})
        assert status == 200
        return str(body["token"])


@pytest.fixture
def bridge(tmp_path: Path) -> Iterator[Bridge]:
    running = Bridge(tmp_path)
    yield running
    running.server.shutdown()
    running.server.server_close()


@pytest.mark.parametrize("host", ["0.0.0.0", "", "::", "192.168.1.10", "host.docker.internal"])
def test_it_never_listens_beyond_loopback(tmp_path: Path, host: str) -> None:
    with pytest.raises(ValueError, match="loopback"):
        make_server(host, 0, pairing=Pairing(tmp_path / "b.json"), detect=lambda: [])


def test_health_answers_without_a_token_and_says_nothing_more(bridge: Bridge) -> None:
    status, body = bridge.call("GET", "/health")

    assert status == 200
    assert body["status"] == "ok" and body["paired"] is False
    assert set(body) == {"status", "paired", "version"}


def test_runtimes_are_refused_without_the_paired_token(bridge: Bridge) -> None:
    assert bridge.call("GET", "/runtimes")[0] == 401
    bridge.paired_token()
    status, body = bridge.call("GET", "/runtimes", token="not-the-token")

    assert status == 401
    assert body["error"]["code"] == "unauthorized"
    assert bridge.detections == 0


def test_the_paired_token_reads_the_runtimes(bridge: Bridge) -> None:
    token = bridge.paired_token()

    status, body = bridge.call("GET", "/runtimes", token=token)

    assert status == 200 and body == {"runtimes": RUNTIMES}
    assert bridge.call("GET", "/health")[1]["paired"] is True


def test_a_wrong_code_is_refused(bridge: Bridge) -> None:
    bridge.pairing.new_code()

    status, body = bridge.call("POST", "/pair", {"code": "AAAA-BBBB"})

    assert status == 403 and body["error"]["code"] == "pairing_refused"
    assert "token" not in body


def test_a_browser_is_refused_even_with_the_token(bridge: Bridge) -> None:
    # Any web page may try to reach 127.0.0.1: the bridge only talks to the API server.
    token = bridge.paired_token()

    status, body = bridge.call(
        "GET", "/runtimes", token=token, headers={"Origin": "https://evil.example"}
    )

    assert status == 403 and body["error"]["code"] == "browser_refused"


def test_a_foreign_host_name_is_refused(bridge: Bridge) -> None:
    # DNS rebinding: a page on evil.example resolved to 127.0.0.1 still sends its own Host.
    token = bridge.paired_token()

    status, _ = bridge.call(
        "GET", "/runtimes", token=token, headers={"Host": f"evil.example:{bridge.port}"}
    )

    assert status == 421


def test_the_api_container_host_name_is_accepted(bridge: Bridge) -> None:
    token = bridge.paired_token()
    headers = {"Host": f"host.docker.internal:{bridge.port}"}

    assert bridge.call("GET", "/runtimes", token=token, headers=headers)[0] == 200


def test_unpairing_needs_the_token_then_forgets_it(bridge: Bridge) -> None:
    token = bridge.paired_token()
    assert bridge.call("DELETE", "/pair")[0] == 401

    assert bridge.call("DELETE", "/pair", token=token)[0] == 204

    assert bridge.call("GET", "/runtimes", token=token)[0] == 401


def test_unknown_routes_and_methods(bridge: Bridge) -> None:
    token = bridge.paired_token()

    assert bridge.call("GET", "/exec", token=token)[0] == 404
    assert bridge.call("POST", "/runtimes", {"argv": ["calc"]}, token=token)[0] == 405


def test_a_large_body_is_refused(bridge: Bridge) -> None:
    status, _ = bridge.call("POST", "/pair", {"code": "x" * 20_000})

    assert status == 413
