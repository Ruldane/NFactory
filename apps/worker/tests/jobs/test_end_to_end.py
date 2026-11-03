"""A run launched over HTTP, executed by the worker job, read back over HTTP.

Only Redis is replaced (MemoryQueue): database, recipes, checks and storage are real.
"""

import sys
import zipfile
from collections.abc import AsyncIterator
from io import BytesIO
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.bootstrap import prepare_data
from app.main import create_app
from app.queue import MemoryQueue
from app.wakeups import PollingWakeups
from nfactory_core.config import Settings
from nfactory_core.roster import plan_steps
from nfactory_worker.jobs import process_run
from nfactory_worker.runner import LocalRunner

pytestmark = pytest.mark.integration


@pytest.fixture
def settings(migrated_database_url: str, tmp_path: Path) -> Settings:
    return Settings(
        database_url=migrated_database_url,
        redis_url="redis://127.0.0.1:1/0",
        workspace_root=str(tmp_path / "workspaces"),
        artifact_root=str(tmp_path / "artifacts"),
    )


@pytest.fixture
async def api(settings: Settings) -> AsyncIterator[tuple[AsyncClient, MemoryQueue, object]]:
    queue = MemoryQueue()
    app = create_app(settings, queue=queue, wakeups=PollingWakeups())
    await prepare_data(app.state.database.sessions, demo=False)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as http:
            yield http, queue, app.state.database.sessions


@pytest.mark.parametrize(
    ("project_type", "request_text", "deliverable"),
    [
        ("excel", "Rapport hebdomadaire des heures par équipe", ".xlsx"),
        ("document", "Procédure de sauvegarde des postes", ".docx"),
    ],
)
async def test_run_from_http_request_to_downloadable_deliverable(
    api: tuple[AsyncClient, MemoryQueue, object],
    settings: Settings,
    project_type: str,
    request_text: str,
    deliverable: str,
) -> None:
    http, queue, sessions = api
    project = (
        await http.post(
            "/api/v1/projects", json={"title": "Livrable", "type": project_type, "description": ""}
        )
    ).json()
    run = (
        await http.post(f"/api/v1/projects/{project['id']}/runs", json={"request": request_text})
    ).json()

    # What the ARQ worker does with the queued id.
    assert queue.enqueued == [run["id"]]
    await process_run(
        run["id"],
        sessions=sessions,  # type: ignore[arg-type]
        settings=settings,
        runner=LocalRunner(Path(settings.workspace_root), python=sys.executable),
    )

    done = (await http.get(f"/api/v1/runs/{run['id']}")).json()
    assert done["state"] == "COMPLETED", done["error"]
    # Every planned step ran; the architect is not called for a non-application (spec §5).
    states = {s["name"]: s["state"] for s in done["steps"]}
    assert states == {
        step.name: "SUCCEEDED" if step.active else "SKIPPED" for step in plan_steps(project_type)
    }
    assert states["architect"] == "SKIPPED"

    events = (await http.get(f"/api/v1/runs/{run['id']}/events")).text
    assert "event: test.passed" in events and "event: run.completed" in events

    files = (await http.get(f"/api/v1/runs/{run['id']}/files")).json()["files"]
    assert "EXPLICATION.md" in files

    artifacts = (await http.get(f"/api/v1/runs/{run['id']}/artifacts")).json()["items"]
    names = [a["filename"] for a in artifacts]
    assert any(n.endswith(".zip") for n in names) and any(n.endswith(deliverable) for n in names)
    office = next(a for a in artifacts if a["filename"].endswith(deliverable))
    download = await http.get(office["download_url"])
    assert download.status_code == 200
    # xlsx and docx are ZIP containers: a valid one opens.
    assert zipfile.ZipFile(BytesIO(download.content)).namelist()
