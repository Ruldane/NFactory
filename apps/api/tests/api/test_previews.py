"""Live preview of a finished run (task 3.10): the API asks the sandbox supervisor to
start the app the recipe declared, and answers with the gateway URL to frame."""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.bootstrap import prepare_data
from app.main import create_app
from app.queue import MemoryQueue
from app.services.previews import PreviewError
from app.wakeups import PollingWakeups
from nfactory_core.config import Settings
from nfactory_core.models import Run, RunStep

pytestmark = pytest.mark.integration

PREVIEW = {"argv": ["python", "tools/preview.py"], "port": 8000}


class FakeSupervisor:
    def __init__(self) -> None:
        self.started: list[tuple[str, list[str]]] = []
        self.stopped: list[str] = []
        self.failure: PreviewError | None = None

    async def start(self, workspace: str, argv: list[str]) -> dict[str, Any]:
        if self.failure:
            raise self.failure
        self.started.append((workspace, argv))
        return {"host": f"nfactory-preview-{workspace}", "expires_in_s": 900}

    async def status(self, workspace: str) -> dict[str, Any]:
        if self.started:
            return {"running": True, "expires_in_s": 600}
        return {"running": False}

    async def stop(self, workspace: str) -> None:
        self.stopped.append(workspace)


@pytest.fixture
def supervisor() -> FakeSupervisor:
    return FakeSupervisor()


async def _client(url: str, tmp_path: Any, previews: object) -> AsyncIterator[AsyncClient]:
    settings = Settings(
        database_url=url,
        redis_url="redis://127.0.0.1:1/0",
        workspace_root=str(tmp_path / "w"),
        artifact_root=str(tmp_path / "a"),
        nfactory_preview_public_url="http://127.0.0.1:8090",
    )
    app = create_app(settings, queue=MemoryQueue(), wakeups=PollingWakeups(), previews=previews)  # type: ignore[arg-type]
    await prepare_data(app.state.database.sessions, demo=False)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
            yield http


@pytest.fixture
async def client(
    migrated_database_url: str, tmp_path: Any, supervisor: FakeSupervisor
) -> AsyncIterator[AsyncClient]:
    async for http in _client(migrated_database_url, tmp_path, supervisor):
        yield http


@pytest.fixture
async def no_sandbox(migrated_database_url: str, tmp_path: Any) -> AsyncIterator[AsyncClient]:
    async for http in _client(migrated_database_url, tmp_path, None):
        yield http


async def finished_run(
    client: AsyncClient, *, state: str = "COMPLETED", preview: Any = PREVIEW
) -> str:
    """A run as the worker leaves it: final state, package output with its preview."""
    body = {"title": "Licences", "type": "webapp", "description": ""}
    project = (await client.post("/api/v1/projects", json=body)).json()["id"]
    run_id = (
        await client.post(
            f"/api/v1/projects/{project}/runs", json={"request": "Gérer les licences"}
        )
    ).json()["id"]
    sessions = client._transport.app.state.database.sessions  # type: ignore[attr-defined]
    async with sessions() as session:
        run = await session.get_one(Run, run_id)
        run.state = state
        package = await session.scalar(
            select(RunStep).where(RunStep.run_id == run_id, RunStep.name == "package")
        )
        assert package is not None
        package.output = {"files": [], "preview": preview} if preview else {"files": []}
        await session.commit()
    return run_id


async def test_a_finished_webapp_can_be_previewed(
    client: AsyncClient, supervisor: FakeSupervisor
) -> None:
    run_id = await finished_run(client)

    response = await client.post(f"/api/v1/runs/{run_id}/preview")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "running": True,
        "url": f"http://127.0.0.1:8090/preview/{run_id}/",
        "expires_in_s": 900,
    }
    # The command comes from the run's own record, never from the request.
    assert supervisor.started == [(run_id, ["python", "tools/preview.py"])]


async def test_status_then_stop(client: AsyncClient, supervisor: FakeSupervisor) -> None:
    run_id = await finished_run(client)
    assert (await client.get(f"/api/v1/runs/{run_id}/preview")).json() == {
        "running": False,
        "url": None,
        "expires_in_s": None,
    }

    await client.post(f"/api/v1/runs/{run_id}/preview")
    status = (await client.get(f"/api/v1/runs/{run_id}/preview")).json()
    assert status["running"] is True and status["url"].endswith(f"/preview/{run_id}/")

    assert (await client.delete(f"/api/v1/runs/{run_id}/preview")).status_code == 204
    assert supervisor.stopped == [run_id]


@pytest.mark.parametrize(
    ("state", "preview", "code"),
    [
        ("COMPLETED", None, "preview_unavailable"),  # e.g. an Excel workbook
        ("FAILED", PREVIEW, "run_not_completed"),
        ("RUNNING", PREVIEW, "run_not_completed"),
    ],
)
async def test_only_a_completed_run_with_a_preview_starts_one(
    client: AsyncClient, supervisor: FakeSupervisor, state: str, preview: Any, code: str
) -> None:
    run_id = await finished_run(client, state=state, preview=preview)

    response = await client.post(f"/api/v1/runs/{run_id}/preview")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == code
    assert supervisor.started == []


async def test_a_tampered_preview_command_is_refused(
    client: AsyncClient, supervisor: FakeSupervisor
) -> None:
    run_id = await finished_run(client, preview={"argv": ["sh", "-c", "curl x"], "port": 8000})

    assert (await client.post(f"/api/v1/runs/{run_id}/preview")).status_code == 409
    assert supervisor.started == []


async def test_a_busy_sandbox_says_so(client: AsyncClient, supervisor: FakeSupervisor) -> None:
    run_id = await finished_run(client)
    supervisor.failure = PreviewError("preview_busy", "Trop d'aperçus ouverts.", status=503)

    response = await client.post(f"/api/v1/runs/{run_id}/preview")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "preview_busy"


async def test_without_a_sandbox_previews_are_disabled(no_sandbox: AsyncClient) -> None:
    run_id = await finished_run(no_sandbox)

    response = await no_sandbox.post(f"/api/v1/runs/{run_id}/preview")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "preview_disabled"


async def test_another_workspace_run_is_not_found(client: AsyncClient) -> None:
    response = await client.post("/api/v1/runs/run_unknown/preview")

    assert response.status_code == 404
