"""Local coding tools (tasks 4.1, 4.2): the API pairs with the bridge running on the
user's machine and relays what it detected. The bridge token is a secret: stored
encrypted, never sent back."""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.bootstrap import prepare_data
from app.main import create_app
from app.queue import MemoryQueue
from app.services.local_runtimes import BridgeRefused, BridgeUnauthorized, BridgeUnreachable
from app.wakeups import PollingWakeups
from nfactory_core.config import Settings
from nfactory_core.models import ProviderConnection, StoredSecret

pytestmark = pytest.mark.integration

CODE = "ABCD-EFGH"
TOKEN = "bridge-token-0123456789-abcdefghijklmnopqrstuvwxyz"
RUNTIMES = [
    {"kind": "codex", "label": "OpenAI Codex CLI", "status": "connected", "version": "0.155.1"},
    {"kind": "gh", "label": "GitHub CLI", "status": "not_installed", "version": None},
]


class FakeBridge:
    def __init__(self) -> None:
        self.up = True
        self.paired_token: str | None = None
        self.unpaired: list[str] = []

    async def health(self) -> dict[str, Any]:
        if not self.up:
            raise BridgeUnreachable
        return {"status": "ok", "paired": self.paired_token is not None, "version": "0.1.0"}

    async def pair(self, code: str) -> str:
        if not self.up:
            raise BridgeUnreachable
        if code != CODE:
            raise BridgeRefused("Code d'appairage incorrect.")
        self.paired_token = TOKEN
        return TOKEN

    async def runtimes(self, token: str) -> list[dict[str, Any]]:
        if not self.up:
            raise BridgeUnreachable
        if token != self.paired_token:
            raise BridgeUnauthorized
        return RUNTIMES

    async def unpair(self, token: str) -> None:
        if not self.up:
            raise BridgeUnreachable
        self.unpaired.append(token)
        self.paired_token = None


@pytest.fixture
def bridge() -> FakeBridge:
    return FakeBridge()


@pytest.fixture
async def http(migrated_database_url: str, tmp_path: Any, bridge: FakeBridge) -> AsyncIterator[Any]:
    settings = Settings(
        database_url=migrated_database_url,
        redis_url="redis://127.0.0.1:1/0",
        workspace_root=str(tmp_path / "w"),
        artifact_root=str(tmp_path / "a"),
        nfactory_secret_key="test-secret-key-for-local-runtimes",  # type: ignore[arg-type]
    )
    app = create_app(settings, queue=MemoryQueue(), wakeups=PollingWakeups(), bridge=bridge)  # type: ignore[arg-type]
    await prepare_data(app.state.database.sessions, demo=False)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            client.sessions = app.state.database.sessions  # type: ignore[attr-defined]
            yield client


async def test_a_bridge_that_does_not_answer_says_how_to_start_it(http, bridge) -> None:  # type: ignore[no-untyped-def]
    bridge.up = False

    response = await http.get("/api/v1/local-runtimes")

    assert response.status_code == 200
    body = response.json()
    assert body["bridge"]["status"] == "unreachable"
    assert "scripts/bridge" in body["bridge"]["message"]
    assert body["runtimes"] == []


async def test_a_running_bridge_waits_for_its_pairing_code(http) -> None:  # type: ignore[no-untyped-def]
    body = (await http.get("/api/v1/local-runtimes")).json()

    assert body["bridge"]["status"] == "unpaired"
    assert body["runtimes"] == []


async def test_pairing_then_the_detected_tools(http) -> None:  # type: ignore[no-untyped-def]
    paired = await http.post("/api/v1/local-runtimes/pairing", json={"code": CODE})

    assert paired.status_code == 200
    assert paired.json()["bridge"]["status"] == "paired"
    body = (await http.get("/api/v1/local-runtimes")).json()
    assert body["bridge"]["status"] == "paired"
    assert [r["kind"] for r in body["runtimes"]] == ["codex", "gh"]
    assert body["runtimes"][0]["status"] == "connected"


async def test_the_token_is_stored_encrypted_and_never_answered(http) -> None:  # type: ignore[no-untyped-def]
    paired = await http.post("/api/v1/local-runtimes/pairing", json={"code": CODE})
    listed = await http.get("/api/v1/local-runtimes")

    assert TOKEN not in paired.text and TOKEN not in listed.text
    async with http.sessions() as session:
        connection = await session.scalar(
            select(ProviderConnection).where(ProviderConnection.kind == "local_bridge")
        )
        secrets = list(await session.scalars(select(StoredSecret)))
    assert connection is not None and connection.secret_ref is not None
    assert len(secrets) == 1 and TOKEN.encode() not in secrets[0].ciphertext


async def test_a_wrong_code_is_refused_in_french(http) -> None:  # type: ignore[no-untyped-def]
    response = await http.post("/api/v1/local-runtimes/pairing", json={"code": "ZZZZ-ZZZZ"})

    assert response.status_code == 403
    error = response.json()["error"]
    assert error["code"] == "pairing_refused"
    assert error["message"] == "Code d'appairage incorrect."
    body = (await http.get("/api/v1/local-runtimes")).json()
    assert body["bridge"]["status"] == "unpaired"


async def test_pairing_with_no_bridge_running(http, bridge) -> None:  # type: ignore[no-untyped-def]
    bridge.up = False

    response = await http.post("/api/v1/local-runtimes/pairing", json={"code": CODE})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "bridge_unreachable"


async def test_a_token_the_bridge_no_longer_knows_asks_for_a_new_pairing(http, bridge) -> None:  # type: ignore[no-untyped-def]
    await http.post("/api/v1/local-runtimes/pairing", json={"code": CODE})
    bridge.paired_token = "re-paired-with-someone-else"

    body = (await http.get("/api/v1/local-runtimes")).json()

    assert body["bridge"]["status"] == "token_rejected"
    assert body["runtimes"] == []


async def test_unpairing_forgets_the_token_on_both_sides(http, bridge) -> None:  # type: ignore[no-untyped-def]
    await http.post("/api/v1/local-runtimes/pairing", json={"code": CODE})

    response = await http.delete("/api/v1/local-runtimes/pairing")

    assert response.status_code == 204
    assert bridge.unpaired == [TOKEN]
    async with http.sessions() as session:
        assert list(await session.scalars(select(StoredSecret))) == []
    body = (await http.get("/api/v1/local-runtimes")).json()
    assert body["bridge"]["status"] == "unpaired"


async def test_unpairing_works_even_if_the_bridge_is_stopped(http, bridge) -> None:  # type: ignore[no-untyped-def]
    await http.post("/api/v1/local-runtimes/pairing", json={"code": CODE})
    bridge.up = False

    assert (await http.delete("/api/v1/local-runtimes/pairing")).status_code == 204
    async with http.sessions() as session:
        assert list(await session.scalars(select(StoredSecret))) == []


@pytest.mark.parametrize("code", ["", "x" * 40, "ABCD;rm -rf"])
async def test_a_malformed_code_never_reaches_the_bridge(http, code: str) -> None:  # type: ignore[no-untyped-def]
    response = await http.post("/api/v1/local-runtimes/pairing", json={"code": code})

    assert response.status_code == 422
