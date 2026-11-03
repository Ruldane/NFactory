"""Sandbox check of an agent's change (task 4.4): the worker copies the task's files from
the bridge into a throwaway workspace and runs the tests there, never on the bridge.
A real pytest runs through LocalRunner; the bridge is a fake snapshot."""

import base64
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.services.identity import LOCAL_WORKSPACE_ID, ensure_local_identity
from nfactory_core.config import Settings
from nfactory_core.local_bridge import KIND
from nfactory_core.models import AgentCheck, ProviderConnection
from nfactory_core.secrets import SecretStore
from nfactory_worker.jobs.agent_checks import BridgeFetchError, check_agent_task, http_snapshot
from nfactory_worker.runner import LocalRunner

pytestmark = pytest.mark.integration

Sessions = async_sessionmaker[AsyncSession]
MASTER = "worker-tests-master-key-0123456789abcdef"
TOKEN = "bridge-token-0123456789"
TASK = "t_0123456789ab"

CALC = "def add(a, b):\n    return a + b\n"
GOOD_TEST = "from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
BAD_TEST = "from calc import add\n\n\ndef test_add_is_wrong():\n    assert add(1, 2) == 4\n"


def snapshot(files: dict[str, str]) -> dict[str, Any]:
    return {
        "id": TASK,
        "files": [
            {"path": path, "data": base64.b64encode(text.encode()).decode()}
            for path, text in files.items()
        ],
    }


@pytest.fixture
async def sessions(migrated_database_url: str) -> AsyncIterator[Sessions]:
    engine = create_async_engine(migrated_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await ensure_local_identity(session)
        await session.commit()
    yield factory
    await engine.dispose()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(nfactory_secret_key=MASTER, workspace_root=str(tmp_path / "ws"))  # type: ignore[arg-type]


async def pair(sessions: Sessions) -> None:
    async with sessions() as session:
        session.add(
            ProviderConnection(
                workspace_id=LOCAL_WORKSPACE_ID,
                kind=KIND,
                display_name="Pont local",
                status="connected",
                secret_ref=await SecretStore(MASTER).put(session, LOCAL_WORKSPACE_ID, TOKEN),
            )
        )
        await session.commit()


async def queued(sessions: Sessions) -> str:
    async with sessions() as session:
        check = AgentCheck(
            workspace_id=LOCAL_WORKSPACE_ID, task_id=TASK, repo_id="nfactory-test", runtime="claude"
        )
        session.add(check)
        await session.commit()
        return check.id


async def run(sessions: Sessions, settings: Settings, files: dict[str, str] | None) -> AgentCheck:
    check_id = await queued(sessions)
    seen: list[tuple[str, str]] = []

    async def fetch(token: str, task_id: str) -> dict[str, Any]:
        seen.append((token, task_id))
        if files is None:
            raise BridgeFetchError("Pont local non joignable.")
        return snapshot(files)

    runner = LocalRunner(Path(settings.workspace_root), python=sys.executable)
    await check_agent_task(sessions, settings, runner, check_id, fetch=fetch)
    async with sessions() as session:
        check = await session.get_one(AgentCheck, check_id)
    # Paired: the stored token, read at the last moment. Unpaired: the bridge is not called.
    assert seen in ([(TOKEN, TASK)], [])
    return check


async def test_passing_tests_pass_the_check(sessions: Sessions, settings: Settings) -> None:
    await pair(sessions)

    check = await run(sessions, settings, {"calc.py": CALC, "tests/test_calc.py": GOOD_TEST})

    assert check.status == "passed"
    assert check.report is not None
    assert check.report["passed"] == 1 and check.report["failed"] == 0
    assert check.report["command"].startswith("python -m pytest")
    assert check.finished_at is not None


async def test_a_failing_test_fails_the_check_and_names_it(
    sessions: Sessions, settings: Settings
) -> None:
    await pair(sessions)

    check = await run(sessions, settings, {"calc.py": CALC, "test_calc.py": BAD_TEST})

    assert check.status == "failed"
    assert check.report is not None
    assert check.report["failed"] == 1
    assert "test_add_is_wrong" in check.report["failures"][0]["name"]


async def test_a_change_without_python_tests_is_not_tested(
    sessions: Sessions, settings: Settings
) -> None:
    await pair(sessions)

    check = await run(sessions, settings, {"README.md": "# x\n"})

    assert check.status == "not_tested"
    assert "pytest" in check.error


async def test_an_unpaired_bridge_is_an_error(sessions: Sessions, settings: Settings) -> None:
    check = await run(sessions, settings, {"calc.py": CALC, "test_calc.py": GOOD_TEST})

    assert check.status == "error"
    assert "pont" in check.error.lower()
    assert check.report is None


async def test_an_unreachable_bridge_is_an_error(sessions: Sessions, settings: Settings) -> None:
    await pair(sessions)

    check = await run(sessions, settings, None)

    assert check.status == "error"
    assert "joignable" in check.error


async def test_a_path_escaping_the_workspace_is_refused(
    sessions: Sessions, settings: Settings, tmp_path: Path
) -> None:
    await pair(sessions)

    check = await run(sessions, settings, {"../escaped.py": "x = 1\n", "test_a.py": GOOD_TEST})

    assert check.status == "error"
    assert not (tmp_path / "escaped.py").exists()


async def test_the_throwaway_workspace_is_removed(sessions: Sessions, settings: Settings) -> None:
    await pair(sessions)

    check = await run(sessions, settings, {"calc.py": CALC, "test_calc.py": GOOD_TEST})

    assert check.status == "passed"
    assert not (Path(settings.workspace_root) / check.id).exists()


@respx.mock
async def test_the_snapshot_is_read_from_the_bridge_with_the_token() -> None:
    route = respx.get(f"http://bridge.test/tasks/{TASK}/snapshot").mock(
        return_value=httpx.Response(200, json=snapshot({"a.py": "x"}))
    )

    data = await http_snapshot("http://bridge.test/")(TOKEN, TASK)

    assert data["files"][0]["path"] == "a.py"
    assert route.calls.last.request.headers["Authorization"] == f"Bearer {TOKEN}"


@respx.mock
async def test_bridge_refusals_become_french_messages() -> None:
    url = f"http://bridge.test/tasks/{TASK}/snapshot"
    respx.get(url).mock(return_value=httpx.Response(401))
    with pytest.raises(BridgeFetchError, match="réassociez"):
        await http_snapshot("http://bridge.test")(TOKEN, TASK)

    respx.get(url).mock(
        return_value=httpx.Response(
            409, json={"error": {"code": "too_large", "message": "Dépôt trop volumineux."}}
        )
    )
    with pytest.raises(BridgeFetchError, match="trop volumineux"):
        await http_snapshot("http://bridge.test")(TOKEN, TASK)

    respx.get(url).mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(BridgeFetchError, match="joignable"):
        await http_snapshot("http://bridge.test")(TOKEN, TASK)
