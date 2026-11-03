"""The bridge's task routes: token required, explicit consent to start, ids only."""

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
from nfactory_bridge.tasks import TaskRefused

VIEW = {"id": "t_1", "status": "running", "branch": "nfactory/app/t_1"}


class FakeTasks:
    def __init__(self) -> None:
        self.started: list[tuple[str, str]] = []
        self.cancelled: list[str] = []
        self.discarded: list[str] = []

    def start_codex(self, repo_id: str, task: str) -> dict[str, Any]:
        if repo_id == "busy":
            raise TaskRefused("busy", "Une tâche est déjà en cours sur ce poste.")
        self.started.append((repo_id, task))
        return VIEW

    def get(self, task_id: str) -> dict[str, Any]:
        if task_id != "t_1":
            raise TaskRefused("not_found", "Tâche inconnue.")
        return VIEW

    def cancel(self, task_id: str) -> dict[str, Any]:
        self.cancelled.append(task_id)
        return VIEW

    def discard(self, task_id: str) -> dict[str, Any]:
        self.discarded.append(task_id)
        return {**VIEW, "status": "discarded"}

    def start_handoff(self, repo_id: str, task: str) -> dict[str, Any]:
        self.started.append((repo_id, task))
        return {**VIEW, "runtime": "claude", "status": "awaiting_user"}

    def collect(self, task_id: str) -> dict[str, Any]:
        return {**VIEW, "runtime": "claude", "status": "succeeded"}

    def snapshot(self, task_id: str) -> dict[str, Any]:
        return {"id": task_id, "files": [{"path": "calc.py", "data": "eA=="}]}


class FakeRepos:
    def public(self) -> list[dict[str, str]]:
        return [{"id": "app", "name": "app"}]


class Client:
    def __init__(self, port: int, token: str | None) -> None:
        self.port, self.token = port, token

    def call(self, method: str, path: str, body: Any = None, token: str | None = "") -> tuple:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}", data=data, method=method
        )
        request.add_header("Content-Type", "application/json")
        bearer = self.token if token == "" else token
        if bearer:
            request.add_header("Authorization", f"Bearer {bearer}")
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read() or b"null")
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"null")


@pytest.fixture
def tasks() -> FakeTasks:
    return FakeTasks()


@pytest.fixture
def client(tmp_path: Path, tasks: FakeTasks) -> Iterator[Client]:
    pairing = Pairing(tmp_path / "bridge.json")
    server = make_server(
        "127.0.0.1", 0, pairing=pairing, detect=lambda: [], tasks=tasks, repos=FakeRepos()
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    status, body = Client(port, None).call("POST", "/pair", {"code": pairing.new_code()})
    assert status == 200
    yield Client(port, body["token"])
    server.shutdown()
    server.server_close()


def test_repos_lists_ids_and_names(client: Client) -> None:
    assert client.call("GET", "/repos") == (200, {"repos": [{"id": "app", "name": "app"}]})


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/repos"), ("POST", "/tasks"), ("GET", "/tasks/t_1"), ("POST", "/tasks/t_1/cancel")],
)
def test_every_task_route_needs_the_token(client: Client, method: str, path: str) -> None:
    status, _ = client.call(method, path, {"consent": True}, token=None)

    assert status == 401


def test_a_codex_task_starts_with_explicit_consent(client: Client, tasks: FakeTasks) -> None:
    body = {"runtime": "codex", "repo_id": "app", "task": "Ajoute un test", "consent": True}

    status, view = client.call("POST", "/tasks", body)

    assert status == 202
    assert view == VIEW
    assert tasks.started == [("app", "Ajoute un test")]


@pytest.mark.parametrize("consent", [None, False, "true", 1])
def test_no_task_starts_without_consent(client: Client, tasks: FakeTasks, consent: Any) -> None:
    body = {"runtime": "codex", "repo_id": "app", "task": "x", "consent": consent}

    status, error = client.call("POST", "/tasks", body)

    assert status == 403
    assert error["error"]["code"] == "consent_required"
    assert tasks.started == []


def test_an_unknown_runtime_is_refused(client: Client) -> None:
    body = {"runtime": "shell", "repo_id": "app", "task": "x", "consent": True}

    status, _ = client.call("POST", "/tasks", body)

    assert status == 400


def test_a_refused_task_keeps_its_code(client: Client) -> None:
    body = {"runtime": "codex", "repo_id": "busy", "task": "x", "consent": True}

    status, error = client.call("POST", "/tasks", body)

    assert status == 409
    assert error["error"]["code"] == "busy"


def test_a_task_is_read_cancelled_and_discarded_by_id(client: Client, tasks: FakeTasks) -> None:
    assert client.call("GET", "/tasks/t_1") == (200, VIEW)
    assert client.call("POST", "/tasks/t_1/cancel")[0] == 200
    assert client.call("POST", "/tasks/t_1/discard")[1]["status"] == "discarded"
    assert tasks.cancelled == ["t_1"] and tasks.discarded == ["t_1"]


def test_an_unknown_task_is_404(client: Client) -> None:
    status, error = client.call("GET", "/tasks/t_other")

    assert status == 404
    assert error["error"]["code"] == "not_found"


def test_a_long_french_task_fits_in_a_request(client: Client, tasks: FakeTasks) -> None:
    body = {"runtime": "codex", "repo_id": "app", "task": "é" * 4_000, "consent": True}

    assert client.call("POST", "/tasks", body)[0] == 202


def test_a_claude_handoff_also_needs_consent(client: Client, tasks: FakeTasks) -> None:
    body = {"runtime": "claude", "repo_id": "app", "task": "Ajoute un test"}

    assert client.call("POST", "/tasks", body)[0] == 403
    status, view = client.call("POST", "/tasks", {**body, "consent": True})

    assert status == 202
    assert view["status"] == "awaiting_user"
    assert tasks.started == [("app", "Ajoute un test")]


def test_a_handoff_is_collected_then_its_files_are_read(client: Client) -> None:
    assert client.call("POST", "/tasks/t_1/collect")[1]["status"] == "succeeded"
    status, snapshot = client.call("GET", "/tasks/t_1/snapshot")

    assert status == 200
    assert snapshot["files"] == [{"path": "calc.py", "data": "eA=="}]
    assert client.call("GET", "/tasks/t_1/snapshot", token=None)[0] == 401
    assert client.call("POST", "/tasks/t_1/snapshot")[0] == 405
