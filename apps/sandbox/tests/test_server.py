"""The sandbox supervisor's HTTP layer: authenticated, validated, bounded."""

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any

import pytest

from nfactory_sandbox.engine import EngineError
from nfactory_sandbox.server import BadRequest, Config, make_server

TOKEN = "test-token-123"


class FakeExecutor:
    def __init__(self) -> None:
        self.runs: list[tuple[str, list[str], int]] = []
        self.gate: threading.Event | None = None
        self.entered = threading.Event()
        self.failure: Exception | None = None
        self.is_ready = True

    def ready(self) -> bool:
        return self.is_ready

    def run(self, workspace: str, argv: list[str], timeout_s: int) -> dict[str, Any]:
        if workspace != "run_1":
            raise BadRequest("unknown workspace")
        if self.failure:
            raise self.failure
        self.entered.set()
        if self.gate:
            self.gate.wait(10)
        self.runs.append((workspace, argv, timeout_s))
        return {"exit_code": 0, "stdout": "ok", "stderr": "", "duration_s": 0.1, "timed_out": False}


@pytest.fixture
def executor() -> FakeExecutor:
    return FakeExecutor()


@pytest.fixture
def sandbox(executor: FakeExecutor) -> Iterator[str]:
    config = Config(token=TOKEN, executor=executor, max_parallel=1, queue_wait_s=0.5)
    httpd = make_server("127.0.0.1", 0, config)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def post(url: str, body: dict[str, Any], token: str | None = TOKEN) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(url + "/run", data=json.dumps(body).encode(), method="POST")
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"{}")


def health(url: str) -> int:
    try:
        with urllib.request.urlopen(url + "/health", timeout=5) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


def test_health_needs_no_token_and_reflects_the_engine(
    sandbox: str, executor: FakeExecutor
) -> None:
    assert health(sandbox) == 200
    executor.is_ready = False
    assert health(sandbox) == 503


def test_an_allowed_command_reaches_the_executor(sandbox: str, executor: FakeExecutor) -> None:
    status, body = post(sandbox, {"workspace": "run_1", "argv": ["pwsh", "-File", "x.ps1"]})

    assert status == 200 and body["exit_code"] == 0
    assert executor.runs == [("run_1", ["pwsh", "-File", "x.ps1"], 120)]


@pytest.mark.parametrize("token", [None, "wrong"])
def test_requests_without_the_token_are_rejected(sandbox: str, token: str | None) -> None:
    status, _ = post(sandbox, {"workspace": "run_1", "argv": ["python", "-V"]}, token=token)
    assert status == 401


@pytest.mark.parametrize("pad", [0, 60_000])
def test_refusal_is_always_a_clean_401(sandbox: str, pad: int) -> None:
    # The server must read the body before refusing: closing on unread data resets the
    # connection on Windows, and the client then sees an abort instead of the 401.
    body = {"workspace": "run_1", "argv": ["python", "-V"], "pad": "x" * pad}
    for _ in range(300):
        status, _ = post(sandbox, body, token="wrong")
        assert status == 401


@pytest.mark.parametrize(
    "body",
    [
        {"workspace": "run_1", "argv": ["sh", "-c", "id"]},
        {"workspace": "../etc", "argv": ["python", "-V"]},
        {"workspace": "missing", "argv": ["python", "-V"]},
        {"workspace": "run_1", "argv": []},
        {"workspace": "run_1", "argv": ["python", 3]},
        {"workspace": "run_1", "argv": ["python", "-V"], "timeout_s": 10_000},
    ],
)
def test_invalid_requests_are_refused(
    sandbox: str, executor: FakeExecutor, body: dict[str, Any]
) -> None:
    status, response = post(sandbox, body)
    assert status == 400
    assert "error" in response
    assert executor.runs == []


def test_an_engine_failure_is_a_502_not_a_result(sandbox: str, executor: FakeExecutor) -> None:
    executor.failure = EngineError("docker down")

    status, body = post(sandbox, {"workspace": "run_1", "argv": ["python", "-V"]})

    assert status == 502
    assert "docker down" not in json.dumps(body)  # engine details stay in the supervisor log


def test_commands_beyond_the_parallel_limit_get_a_503(sandbox: str, executor: FakeExecutor) -> None:
    executor.gate = threading.Event()
    first: list[int] = []
    busy = threading.Thread(
        target=lambda: first.append(post(sandbox, {"workspace": "run_1", "argv": ["python"]})[0])
    )
    busy.start()
    try:
        assert executor.entered.wait(10)  # the first command holds the only slot
        status, body = post(sandbox, {"workspace": "run_1", "argv": ["python", "-V"]})
    finally:
        executor.gate.set()
        busy.join(10)

    assert status == 503 and body["error"] == "busy"
    assert first == [200]
