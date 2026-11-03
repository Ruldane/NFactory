"""Runs over HTTP: launch, follow, cancel, and read what they produced."""

import hashlib
import json
from typing import Any

import pytest
from httpx import AsyncClient

from app.queue import MemoryQueue
from nfactory_core.pipeline import step_names

pytestmark = pytest.mark.integration

REQUEST = {"request": "Une API pour suivre les licences logicielles"}


async def new_project(client: AsyncClient, type: str = "api") -> str:
    body = {"title": "Licences", "type": type, "description": ""}
    return (await client.post("/api/v1/projects", json=body)).json()["id"]


async def launch(client: AsyncClient, project_id: str, **headers: str) -> Any:
    return await client.post(f"/api/v1/projects/{project_id}/runs", json=REQUEST, headers=headers)


def sse_events(text: str) -> list[dict[str, Any]]:
    events = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        fields = dict(
            line.split(": ", 1) for line in block.splitlines() if ": " in line and line[0] != ":"
        )
        if "event" in fields:
            events.append({**fields, "data": json.loads(fields["data"])})
    return events


async def test_launching_a_run_queues_it_with_every_pipeline_step(
    client: AsyncClient, queue: MemoryQueue
) -> None:
    project_id = await new_project(client)

    response = await launch(client, project_id)

    assert response.status_code == 201
    run = response.json()
    assert run["id"].startswith("run_") and run["state"] == "QUEUED"
    assert run["recipe"] == "python-api"
    assert [s["name"] for s in run["steps"]] == list(step_names())
    assert {s["state"] for s in run["steps"]} == {"PENDING"}
    assert queue.enqueued == [run["id"]]
    assert len(run["trace_id"]) == 32  # one trace id per run, followed by the worker
    assert run["budget"]["max_llm_calls"] > 0

    fetched = (await client.get(f"/api/v1/runs/{run['id']}")).json()
    assert fetched["request"] == REQUEST["request"]
    assert fetched["project"]["id"] == project_id


async def test_an_excel_run_plans_no_architect(client: AsyncClient) -> None:
    run = (await launch(client, await new_project(client, "excel"))).json()

    steps = {s["name"]: s for s in run["steps"]}
    assert steps["architect"]["state"] == "SKIPPED"
    assert "architecte n'est pas appelé" in steps["architect"]["output"]["skipped"]
    assert steps["build"]["agent_role"] == "automation"

    cancelled = (await client.post(f"/api/v1/runs/{run['id']}/cancel")).json()
    states = {s["name"]: s["state"] for s in cancelled["steps"]}
    assert states["architect"] == "SKIPPED"  # never planned: cancelling does not rewrite it


async def test_same_idempotency_key_returns_the_same_run(
    client: AsyncClient, queue: MemoryQueue
) -> None:
    project_id = await new_project(client)

    first = await launch(client, project_id, **{"Idempotency-Key": "clic-1"})
    again = await launch(client, project_id, **{"Idempotency-Key": "clic-1"})

    assert first.status_code == 201 and again.status_code == 200
    assert again.json()["id"] == first.json()["id"]
    assert len(queue.enqueued) == 1


async def test_type_not_built_yet_is_refused_with_its_phase(client: AsyncClient) -> None:
    project_id = await new_project(client, type="feature")

    response = await launch(client, project_id)

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "recipe_unavailable"
    assert "phase 4" in error["message"]


async def test_without_demo_mode_or_provider_the_run_is_refused(
    no_model_client: AsyncClient, queue: MemoryQueue
) -> None:
    # No silent fallback to an external provider (spec §8).
    project_id = await new_project(no_model_client)

    response = await launch(no_model_client, project_id)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "no_model_configured"
    assert queue.enqueued == []


async def test_queue_down_fails_the_run_instead_of_leaving_it_queued(
    client: AsyncClient, queue: MemoryQueue
) -> None:
    queue.broken = True
    project_id = await new_project(client)

    response = await launch(client, project_id)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "queue_unavailable"
    project = (await client.get(f"/api/v1/projects/{project_id}")).json()
    assert project["latest_run"]["state"] == "FAILED"


async def test_cancelling_a_queued_run_stops_it_for_good(client: AsyncClient) -> None:
    run = (await launch(client, await new_project(client))).json()

    response = await client.post(f"/api/v1/runs/{run['id']}/cancel")

    assert response.status_code == 200
    cancelled = response.json()
    assert cancelled["state"] == "CANCELLED" and cancelled["finished_at"]
    assert {s["state"] for s in cancelled["steps"]} == {"CANCELLED"}

    again = await client.post(f"/api/v1/runs/{run['id']}/cancel")
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "run_finished"


async def test_event_stream_replays_history_and_resumes_after_last_event_id(
    client: AsyncClient,
) -> None:
    run = (await launch(client, await new_project(client))).json()
    await client.post(f"/api/v1/runs/{run['id']}/cancel")  # finished: the stream ends

    full = sse_events((await client.get(f"/api/v1/runs/{run['id']}/events")).text)

    assert [e["event"] for e in full] == ["run.created", "run.cancelled"]
    assert full[0]["data"]["payload"]["state"] == "QUEUED"
    resumed = await client.get(
        f"/api/v1/runs/{run['id']}/events", headers={"Last-Event-ID": full[0]["id"]}
    )
    assert [e["event"] for e in sse_events(resumed.text)] == ["run.cancelled"]


async def test_files_and_artifacts_of_a_run(client: AsyncClient, storage: Any) -> None:
    run = (await launch(client, await new_project(client))).json()
    # What the worker leaves behind: a workspace and a stored artifact.
    workspace = storage.workspaces / run["id"]
    (workspace / "app").mkdir(parents=True)
    (workspace / "app" / "main.py").write_bytes(b"print('ok')\n")
    (workspace / "rapport.xlsx").write_bytes(b"PK\x03\x04binary")
    data = b"zip-bytes"
    await _store_artifact(client, run["id"], storage, "licences.zip", data)

    files = (await client.get(f"/api/v1/runs/{run['id']}/files")).json()
    assert files["files"] == ["app/main.py", "rapport.xlsx"]

    content = (
        await client.get(f"/api/v1/runs/{run['id']}/files/content", params={"path": "app/main.py"})
    ).json()
    assert content == {
        "path": "app/main.py",
        "content": "print('ok')\n",
        "binary": False,
        "size": 12,
    }
    binary = (
        await client.get(f"/api/v1/runs/{run['id']}/files/content", params={"path": "rapport.xlsx"})
    ).json()
    assert binary["binary"] is True and binary["content"] is None

    artifacts = (await client.get(f"/api/v1/runs/{run['id']}/artifacts")).json()["items"]
    assert [a["filename"] for a in artifacts] == ["licences.zip"]
    download = await client.get(artifacts[0]["download_url"])
    assert download.status_code == 200
    assert download.content == data
    assert "licences.zip" in download.headers["content-disposition"]


@pytest.mark.parametrize("path", ["../secret.txt", "/etc/passwd", "C:/Windows/win.ini", ""])
async def test_file_paths_cannot_escape_the_workspace(
    client: AsyncClient, storage: Any, path: str
) -> None:
    run = (await launch(client, await new_project(client))).json()
    (storage.workspaces / run["id"]).mkdir(parents=True)

    response = await client.get(f"/api/v1/runs/{run['id']}/files/content", params={"path": path})

    assert response.status_code in {400, 422}


async def test_unknown_run_and_artifact_are_not_found(client: AsyncClient) -> None:
    for url in (
        "/api/v1/runs/run_nope",
        "/api/v1/runs/run_nope/events",
        "/api/v1/runs/run_nope/files",
        "/api/v1/runs/run_nope/artifacts",
        "/api/v1/artifacts/art_nope/download",
    ):
        response = await client.get(url)
        assert response.status_code == 404, url
        assert response.json()["error"]["code"] == "not_found"


async def _store_artifact(
    client: AsyncClient, run_id: str, storage: Any, filename: str, data: bytes
) -> None:
    """Write an artifact the way the worker does: file on disk plus a database row."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from nfactory_core.models import Artifact, Run

    target = storage.artifacts / run_id / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    app = client._transport.app  # type: ignore[attr-defined]
    sessions: async_sessionmaker = app.state.database.sessions  # type: ignore[type-arg]
    async with sessions() as session:
        run = await session.get_one(Run, run_id)
        session.add(
            Artifact(
                project_id=run.project_id,
                run_id=run_id,
                filename=filename,
                mime="application/zip",
                storage_key=f"{run_id}/{filename}",
                checksum="sha256:" + hashlib.sha256(data).hexdigest(),
                size=len(data),
            )
        )
        await session.commit()
