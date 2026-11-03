"""The minimal Docker Engine client of the supervisor (standard library only)."""

import json
import struct
from typing import Any

import pytest

from nfactory_sandbox.engine import API_VERSION, DockerEngine, EngineError, demux


def frame(stream: int, data: bytes) -> bytes:
    return struct.pack(">BxxxI", stream, len(data)) + data


def test_demux_splits_stdout_and_stderr_frames() -> None:
    raw = frame(1, b"un ") + frame(2, b"oups") + frame(1, "deux é".encode())

    assert demux(raw) == ("un deux é", "oups")


def test_demux_tolerates_a_truncated_last_frame() -> None:
    raw = frame(1, b"complet") + struct.pack(">BxxxI", 1, 100) + b"coupe"

    assert demux(raw) == ("completcoupe", "")


class FakeTransport:
    def __init__(self, replies: dict[tuple[str, str], tuple[int, bytes]]) -> None:
        self.replies = replies
        self.requests: list[tuple[str, str, Any, float | None]] = []

    def __call__(
        self, method: str, path: str, body: Any = None, timeout: float | None = None
    ) -> tuple[int, bytes]:
        self.requests.append((method, path, body, timeout))
        route = path.split("?")[0]
        if (method, route) not in self.replies:
            raise AssertionError(f"unexpected {method} {route}")
        return self.replies[(method, route)]


V = f"/v{API_VERSION}"


def test_create_returns_the_container_id_and_sends_the_spec() -> None:
    transport = FakeTransport({("POST", f"{V}/containers/create"): (201, b'{"Id": "abc"}')})

    assert DockerEngine(transport).create({"Image": "x"}) == "abc"
    assert transport.requests[0][2] == {"Image": "x"}


def test_wait_returns_the_exit_code_within_the_timeout() -> None:
    transport = FakeTransport(
        {("POST", f"{V}/containers/abc/wait"): (200, json.dumps({"StatusCode": 2}).encode())}
    )

    assert DockerEngine(transport).wait("abc", timeout_s=5) == 2
    assert transport.requests[0][3] == 5


def test_kill_and_remove_ignore_a_container_already_gone() -> None:
    transport = FakeTransport(
        {
            ("POST", f"{V}/containers/abc/kill"): (409, b'{"message": "not running"}'),
            ("DELETE", f"{V}/containers/abc"): (404, b'{"message": "no such container"}'),
        }
    )
    engine = DockerEngine(transport)

    engine.kill("abc")
    engine.remove("abc")
    assert transport.requests[1][1].endswith("?force=1&v=1")


def test_an_engine_refusal_raises_with_its_message() -> None:
    transport = FakeTransport(
        {("POST", f"{V}/containers/create"): (400, b'{"message": "bad spec"}')}
    )

    with pytest.raises(EngineError, match="bad spec"):
        DockerEngine(transport).create({})


def test_logs_are_read_from_both_streams() -> None:
    raw = frame(1, b"ok") + frame(2, b"warn")
    transport = FakeTransport({("GET", f"{V}/containers/abc/logs"): (200, raw)})

    assert DockerEngine(transport).logs("abc") == ("ok", "warn")
    assert "stdout=1&stderr=1" in transport.requests[0][1]


def test_oom_killed_reads_the_container_state() -> None:
    state = {"State": {"OOMKilled": True}}
    transport = FakeTransport(
        {("GET", f"{V}/containers/abc/json"): (200, json.dumps(state).encode())}
    )

    assert DockerEngine(transport).oom_killed("abc") is True


def test_leftovers_are_listed_by_label() -> None:
    listed = json.dumps([{"Id": "old1"}, {"Id": "old2"}]).encode()
    transport = FakeTransport({("GET", f"{V}/containers/json"): (200, listed)})

    assert DockerEngine(transport).leftovers("nfactory.sandbox=1") == ["old1", "old2"]
    assert "nfactory.sandbox%3D1" in transport.requests[0][1]


def test_a_container_can_be_named() -> None:
    transport = FakeTransport({("POST", f"{V}/containers/create"): (201, b'{"Id": "abc"}')})

    DockerEngine(transport).create({"Image": "x"}, name="nfactory-preview-run_1")

    assert transport.requests[0][1].endswith("/containers/create?name=nfactory-preview-run_1")


@pytest.mark.parametrize(
    ("reply", "running"),
    [
        ((200, b'{"State": {"Running": true}}'), True),
        ((200, b'{"State": {"Running": false}}'), False),
        ((404, b'{"message": "No such container"}'), False),
    ],
)
def test_running_reads_the_container_state(reply: tuple[int, bytes], running: bool) -> None:
    transport = FakeTransport({("GET", f"{V}/containers/abc/json"): reply})

    assert DockerEngine(transport).running("abc") is running
