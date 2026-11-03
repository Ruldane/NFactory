"""Supervisor routes for previews: authenticated and validated like /run."""

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from typing import Any

import pytest

from nfactory_sandbox.previews import PreviewBusy
from nfactory_sandbox.server import BadRequest, Config, make_server

TOKEN = "test-token-123"


class FakePreviews:
    def __init__(self) -> None:
        self.started: list[tuple[str, list[str]]] = []
        self.stopped: list[str] = []
        self.busy = False

    def start(self, workspace: str, argv: list[str]) -> dict[str, Any]:
        if workspace != "run_1":
            raise BadRequest("unknown workspace")
        if self.busy:
            raise PreviewBusy("2 aperçus déjà ouverts")
        self.started.append((workspace, argv))
        return {"host": "nfactory-preview-run_1", "expires_in_s": 900}

    def status(self, workspace: str) -> dict[str, Any]:
        return {"running": bool(self.started)}

    def stop(self, workspace: str) -> None:
        self.stopped.append(workspace)


class NoExecutor:
    def ready(self) -> bool:
        return True

    def run(self, workspace: str, argv: list[str], timeout_s: int) -> dict[str, Any]:
        raise AssertionError("not used")


@pytest.fixture
def previews() -> FakePreviews:
    return FakePreviews()


@pytest.fixture
def base(previews: FakePreviews) -> Iterator[str]:
    httpd = make_server("127.0.0.1", 0, Config(TOKEN, NoExecutor(), previews=previews))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def call(url: str, method: str, body: Any = None, token: str = TOKEN) -> tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"null")


def test_a_preview_starts_with_an_allow_listed_command(base: str, previews: FakePreviews) -> None:
    status, body = call(
        f"{base}/previews", "POST", {"workspace": "run_1", "argv": ["python", "tools/preview.py"]}
    )

    assert (status, body["host"]) == (200, "nfactory-preview-run_1")
    assert previews.started == [("run_1", ["python", "tools/preview.py"])]


@pytest.mark.parametrize(
    "body",
    [
        {"workspace": "run_1", "argv": ["sh", "-c", "x"]},
        {"workspace": "../x", "argv": ["python", "a.py"]},
        {"workspace": "run_1", "argv": []},
    ],
)
def test_an_invalid_preview_request_is_refused(
    base: str, previews: FakePreviews, body: dict[str, Any]
) -> None:
    status, _ = call(f"{base}/previews", "POST", body)

    assert status == 400 and previews.started == []


def test_previews_need_the_token(base: str, previews: FakePreviews) -> None:
    body = {"workspace": "run_1", "argv": ["python", "a.py"]}

    assert call(f"{base}/previews", "POST", body, token="wrong")[0] == 401
    assert call(f"{base}/previews/run_1", "GET", token="wrong")[0] == 401
    assert call(f"{base}/previews/run_1", "DELETE", token="wrong")[0] == 401
    assert previews.started == [] and previews.stopped == []


def test_too_many_previews_answers_busy(base: str, previews: FakePreviews) -> None:
    previews.busy = True

    status, body = call(
        f"{base}/previews", "POST", {"workspace": "run_1", "argv": ["python", "a.py"]}
    )

    assert status == 503 and "aperçus" in body["error"]


def test_status_and_stop(base: str, previews: FakePreviews) -> None:
    assert call(f"{base}/previews/run_1", "GET") == (200, {"running": False})

    assert call(f"{base}/previews/run_1", "DELETE")[0] == 200
    assert previews.stopped == ["run_1"]
    assert call(f"{base}/previews/..%2Fx", "DELETE")[0] == 400
