"""Coding-agent tasks through the paired bridge (task 4.3): the API relays repositories the
user authorized on their machine and the user's Codex tasks, with explicit consent. What
the bridge answers is validated again and redacted; the bridge token never comes back."""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.bootstrap import prepare_data
from app.main import create_app
from app.queue import MemoryQueue
from app.services.local_runtimes import BridgeRefused, BridgeUnreachable
from app.wakeups import PollingWakeups
from nfactory_core.config import Settings

pytestmark = pytest.mark.integration

CODE = "ABCD-EFGH"
TOKEN = "bridge-token-0123456789-abcdefghijklmnopqrstuvwxyz"
TASK = {
    "id": "t_0123456789ab",
    "runtime": "codex",
    "repo_id": "nfactory-test",
    "branch": "nfactory/nfactory-test/t_0123456789ab",
    "base": "3eff134" + "0" * 33,
    "status": "succeeded",
    "events": [
        {"type": "started"},
        {
            "type": "command",
            "command": "OPENAI_API_KEY=sk-live-0123456789abcdefgh pytest",
            "status": "completed",
            "exit_code": 0,
        },
        {"type": "file_change", "changes": [{"path": "calc.py", "kind": "update"}]},
        {"type": "message", "text": "Fonction multiply ajoutée."},
        {"type": "completed", "usage": {"input_tokens": 10, "output_tokens": 5}},
    ],
    "manifest": [{"path": "calc.py", "change": "modified"}],
    "diff": "+def multiply(a, b):\n",
    "diff_truncated": False,
    "error": "",
    "created_at": 1_800_000_000.0,
    "unexpected": "dropped",
}


PUBLICATION: dict[str, Any] = {
    "repo": "Ruldane/nfactory-test",
    "commit": "c" * 40,
    "state": "pr_created",
    "pushed": True,
    "pr": {
        "number": 1,
        "url": "https://github.com/Ruldane/nfactory-test/pull/1",
        "state": "OPEN",
        "draft": True,
        "head": "c" * 40,
        "merged": False,
    },
    "verified_at": 1_800_000_100.0,
}


class FakeBridge:
    def __init__(self) -> None:
        self.up = True
        self.started: list[dict[str, Any]] = []
        self.actions: list[tuple[str, str]] = []
        self.tokens: list[str] = []
        self.status = "succeeded"
        self.published: list[dict[str, Any]] = []

    async def health(self) -> dict[str, Any]:
        if not self.up:
            raise BridgeUnreachable
        return {"status": "ok", "paired": True, "version": "0.1.0"}

    async def pair(self, code: str) -> str:
        return TOKEN

    async def runtimes(self, token: str) -> list[dict[str, Any]]:
        return []

    async def unpair(self, token: str) -> None:
        return None

    async def repos(self, token: str) -> list[dict[str, Any]]:
        self.tokens.append(token)
        return [{"id": "nfactory-test", "name": "nfactory-test"}, {"id": "../bad", "name": "x"}]

    async def start_task(self, token: str, body: dict[str, Any]) -> dict[str, Any]:
        if not self.up:
            raise BridgeUnreachable
        self.tokens.append(token)
        if body["repo_id"] == "busy":
            raise BridgeRefused(
                "Une tâche est déjà en cours sur ce poste.", code="busy", status=409
            )
        self.started.append(body)
        return {**TASK, "status": "running"}

    async def publish(self, token: str, task_id: str, body: dict[str, Any]) -> dict[str, Any]:
        self.tokens.append(token)
        self.published.append(body)
        return PUBLICATION

    async def publication(self, token: str, task_id: str) -> dict[str, Any]:
        return {**PUBLICATION, "state": "merged", "pr": {**PUBLICATION["pr"], "merged": True}}

    async def task(self, token: str, task_id: str, action: str | None = None) -> dict[str, Any]:
        self.tokens.append(token)
        if task_id != TASK["id"]:
            raise BridgeRefused("Tâche inconnue.", code="not_found", status=404)
        self.actions.append((task_id, action or "get"))
        if action == "collect":
            return {**TASK, "runtime": "claude", "status": "succeeded"}
        return {**TASK, "status": self.status}


@pytest.fixture
def bridge() -> FakeBridge:
    return FakeBridge()


@pytest.fixture
def queue() -> MemoryQueue:
    return MemoryQueue()


@pytest.fixture
async def http(
    migrated_database_url: str, tmp_path: Any, bridge: FakeBridge, queue: MemoryQueue
) -> AsyncIterator[Any]:
    settings = Settings(
        database_url=migrated_database_url,
        redis_url="redis://127.0.0.1:1/0",
        workspace_root=str(tmp_path / "w"),
        artifact_root=str(tmp_path / "a"),
        nfactory_secret_key="test-secret-key-for-agent-tasks",  # type: ignore[arg-type]
    )
    app = create_app(settings, queue=queue, wakeups=PollingWakeups(), bridge=bridge)  # type: ignore[arg-type]
    await prepare_data(app.state.database.sessions, demo=False)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


async def paired(http: Any) -> None:
    assert (
        await http.post("/api/v1/local-runtimes/pairing", json={"code": CODE})
    ).status_code == 200


START = {"runtime": "codex", "repo_id": "nfactory-test", "task": "Ajoute multiply", "consent": True}


async def test_an_unpaired_bridge_has_no_tasks(http) -> None:  # type: ignore[no-untyped-def]
    response = await http.get("/api/v1/local-runtimes/repos")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "bridge_unpaired"


async def test_repositories_are_relayed_with_valid_ids_only(http) -> None:  # type: ignore[no-untyped-def]
    await paired(http)

    response = await http.get("/api/v1/local-runtimes/repos")

    repo = {"id": "nfactory-test", "name": "nfactory-test", "github": None}
    assert response.json() == {"repos": [repo]}


async def test_a_task_starts_only_with_consent(http, bridge) -> None:  # type: ignore[no-untyped-def]
    await paired(http)

    refused = await http.post("/api/v1/local-runtimes/tasks", json={**START, "consent": False})
    started = await http.post("/api/v1/local-runtimes/tasks", json=START)

    assert refused.status_code == 422
    assert started.status_code == 202
    assert started.json()["status"] == "running"
    assert bridge.started == [START]


@pytest.mark.parametrize(
    ("policy", "code"), [("eu_only", "eu_only_violation"), ("local_only", "local_only_violation")]
)
async def test_the_data_policy_keeps_coding_agents_off(
    http, bridge, policy: str, code: str
) -> None:  # type: ignore[no-untyped-def]
    await paired(http)
    assert (await http.put("/api/v1/routing", json={policy: True})).status_code == 200

    codex = await http.post("/api/v1/local-runtimes/tasks", json=START)
    claude = await http.post("/api/v1/local-runtimes/tasks", json={**START, "runtime": "claude"})

    assert (codex.status_code, codex.json()["error"]["code"]) == (409, code)
    assert claude.status_code == 409
    assert bridge.started == []


async def test_the_task_view_is_bounded_and_redacted(http) -> None:  # type: ignore[no-untyped-def]
    await paired(http)

    response = await http.get(f"/api/v1/local-runtimes/tasks/{TASK['id']}")

    body = response.json()
    assert response.status_code == 200
    assert "unexpected" not in body
    assert "sk-live-0123456789abcdefgh" not in response.text
    assert body["manifest"] == [{"path": "calc.py", "change": "modified"}]
    assert [e["type"] for e in body["events"]][-1] == "completed"
    assert TOKEN not in response.text


async def test_cancel_and_discard_are_relayed(http, bridge) -> None:  # type: ignore[no-untyped-def]
    await paired(http)

    await http.post(f"/api/v1/local-runtimes/tasks/{TASK['id']}/cancel")
    await http.post(f"/api/v1/local-runtimes/tasks/{TASK['id']}/discard")

    assert bridge.actions == [(TASK["id"], "cancel"), (TASK["id"], "discard")]
    assert set(bridge.tokens) == {TOKEN}


async def test_a_bridge_refusal_keeps_its_code_and_french_message(http) -> None:  # type: ignore[no-untyped-def]
    await paired(http)

    busy = await http.post("/api/v1/local-runtimes/tasks", json={**START, "repo_id": "busy"})
    missing = await http.get("/api/v1/local-runtimes/tasks/t_ffffffffffff")

    assert busy.status_code == 409
    assert busy.json()["error"] == {
        "code": "busy",
        "message": "Une tâche est déjà en cours sur ce poste.",
        "details": None,
    }
    assert missing.status_code == 404


@pytest.mark.parametrize("task_id", ["../x", "t_1;rm", "T_ABC"])
async def test_task_ids_are_checked_before_the_bridge(http, bridge, task_id: str) -> None:  # type: ignore[no-untyped-def]
    await paired(http)

    response = await http.get(f"/api/v1/local-runtimes/tasks/{task_id}")

    assert response.status_code in (404, 422)
    assert bridge.actions == []


async def test_a_stopped_bridge_is_a_clear_error(http, bridge) -> None:  # type: ignore[no-untyped-def]
    await paired(http)
    bridge.up = False

    response = await http.post("/api/v1/local-runtimes/tasks", json=START)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "bridge_unreachable"


async def test_a_claude_handoff_is_prepared_with_consent_then_collected(http, bridge) -> None:  # type: ignore[no-untyped-def]
    await paired(http)
    handoff = {**START, "runtime": "claude"}

    assert (
        await http.post("/api/v1/local-runtimes/tasks", json={**handoff, "consent": False})
    ).status_code == 422
    started = await http.post("/api/v1/local-runtimes/tasks", json=handoff)
    collected = await http.post(f"/api/v1/local-runtimes/tasks/{TASK['id']}/collect")

    assert started.status_code == 202
    assert bridge.started == [handoff]
    assert collected.json()["runtime"] == "claude"
    assert bridge.actions[-1] == (TASK["id"], "collect")


async def _finish_check(http, check_id: str) -> None:  # type: ignore[no-untyped-def]
    from nfactory_core.models import AgentCheck

    async with http._transport.app.state.database.sessions() as session:
        check = await session.get_one(AgentCheck, check_id)
        check.status = "passed"
        check.report = {"passed": 3, "failed": 0, "errors": 0, "skipped": 0, "failures": []}
        await session.commit()


async def test_a_finished_task_is_queued_for_a_sandbox_check(http, queue) -> None:  # type: ignore[no-untyped-def]
    await paired(http)

    response = await http.post(f"/api/v1/local-runtimes/tasks/{TASK['id']}/checks")

    check = response.json()
    assert response.status_code == 202
    assert check["status"] == "queued"
    assert check["task_id"] == TASK["id"] and check["repo_id"] == "nfactory-test"
    assert queue.agent_checks == [check["id"]]
    read = await http.get(f"/api/v1/local-runtimes/checks/{check['id']}")
    assert read.status_code == 200 and read.json()["id"] == check["id"]


async def test_a_running_task_cannot_be_checked_yet(http, bridge, queue) -> None:  # type: ignore[no-untyped-def]
    await paired(http)
    bridge.status = "running"

    response = await http.post(f"/api/v1/local-runtimes/tasks/{TASK['id']}/checks")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "task_not_finished"
    assert queue.agent_checks == []


async def test_an_unknown_check_is_404(http) -> None:  # type: ignore[no-untyped-def]
    response = await http.get("/api/v1/local-runtimes/checks/agc_doesnotexist")

    assert response.status_code == 404


PUBLISH = {"approve": True, "title": "Ajoute multiply"}


async def test_publishing_needs_approval(http, bridge) -> None:  # type: ignore[no-untyped-def]
    await paired(http)

    response = await http.post(
        f"/api/v1/local-runtimes/tasks/{TASK['id']}/publish", json={**PUBLISH, "approve": False}
    )

    assert response.status_code == 422
    assert bridge.published == []


async def test_an_approved_publish_sends_a_pr_body_with_the_verified_tests(
    http, bridge, queue
) -> None:  # type: ignore[no-untyped-def]
    await paired(http)
    check = (await http.post(f"/api/v1/local-runtimes/tasks/{TASK['id']}/checks")).json()
    await _finish_check(http, check["id"])

    response = await http.post(f"/api/v1/local-runtimes/tasks/{TASK['id']}/publish", json=PUBLISH)

    assert response.status_code == 200
    assert response.json()["state"] == "pr_created"
    sent = bridge.published[0]
    assert sent["approve"] is True and sent["title"] == "Ajoute multiply"
    assert "calc.py" in sent["body"]
    assert "3 réussis" in sent["body"] and "0 en échec" in sent["body"]
    assert "brouillon" in sent["body"]


async def test_a_publish_is_recorded_in_the_audit_log(http) -> None:  # type: ignore[no-untyped-def]
    await paired(http)
    await http.post(f"/api/v1/local-runtimes/tasks/{TASK['id']}/publish", json=PUBLISH)

    from sqlalchemy import select

    from nfactory_core.models import AuditLog

    async with http._transport.app.state.database.sessions() as session:  # type: ignore[attr-defined]
        rows = (await session.scalars(select(AuditLog))).all()
    entry = next(row for row in rows if row.action == "agent_task.publish")
    assert entry.target == TASK["id"] and entry.decision == "approved"
    assert entry.redacted_details["repo"] == "Ruldane/nfactory-test"


async def test_the_publication_is_verified_again_on_read(http) -> None:  # type: ignore[no-untyped-def]
    await paired(http)

    response = await http.get(f"/api/v1/local-runtimes/tasks/{TASK['id']}/publication")

    assert response.json()["state"] == "merged"
    assert response.json()["pr"]["merged"] is True
