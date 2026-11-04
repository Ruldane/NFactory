"""Deleting a project (ADR-0015): its runs, deliverables, documents and vectors go with it.
The worker's nightly sweep then removes the files no row points to."""

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.context import get_user_id
from app.services.identity import LOCAL_USER_ID, LOCAL_WORKSPACE_ID
from nfactory_core.models import (
    Artifact,
    AuditLog,
    Document,
    DocumentChunk,
    Membership,
    Project,
    Run,
    Workspace,
)
from nfactory_core.models.identity import User

pytestmark = pytest.mark.integration


@pytest.fixture
def sessions(client: AsyncClient):  # type: ignore[no-untyped-def]
    return client._transport.app.state.database.sessions  # type: ignore[attr-defined]


async def add_project(
    sessions, project_id: str, *, state: str = "COMPLETED", workspace_id: str = LOCAL_WORKSPACE_ID
) -> None:  # type: ignore[no-untyped-def]
    async with sessions() as session:
        session.add(Project(id=project_id, workspace_id=workspace_id, title="Stock", type="api"))
        await session.flush()
        run_id = f"run_{project_id}"
        session.add(Run(id=run_id, project_id=project_id, request="API", state=state))
        await session.flush()
        session.add(
            Artifact(
                project_id=project_id,
                run_id=run_id,
                filename="livrable.zip",
                mime="application/zip",
                storage_key=f"{run_id}/livrable.zip",
                checksum="sha256:00",
                size=1,
            )
        )
        document = Document(
            id=f"doc_{project_id}",
            workspace_id=workspace_id,
            project_id=project_id,
            source="upload",
            path="notes.md",
            checksum="sha256:11",
        )
        session.add(document)
        await session.flush()
        session.add(DocumentChunk(document_id=document.id, ordinal=0, content="Inventaire"))
        await session.commit()


async def count(sessions, model: type, *where: object) -> int:  # type: ignore[no-untyped-def]
    async with sessions() as session:
        return await session.scalar(select(func.count()).select_from(model).where(*where)) or 0


async def test_a_project_goes_with_everything_it_holds(client: AsyncClient, sessions) -> None:  # type: ignore[no-untyped-def]
    await add_project(sessions, "proj_stock")

    response = await client.delete("/api/v1/projects/proj_stock")

    assert response.status_code == 204
    assert (await client.get("/api/v1/projects/proj_stock")).status_code == 404
    assert await count(sessions, Run, Run.project_id == "proj_stock") == 0
    assert await count(sessions, Artifact, Artifact.project_id == "proj_stock") == 0
    assert await count(sessions, Document, Document.project_id == "proj_stock") == 0
    assert await count(sessions, DocumentChunk, DocumentChunk.document_id == "doc_proj_stock") == 0
    async with sessions() as session:
        entry = await session.scalar(select(AuditLog).where(AuditLog.action == "project.deleted"))
    assert entry is not None and entry.target == "proj_stock"
    assert entry.redacted_details == {"runs": 1}


async def test_a_project_with_an_active_run_is_kept(client: AsyncClient, sessions) -> None:  # type: ignore[no-untyped-def]
    await add_project(sessions, "proj_busy", state="RUNNING")

    response = await client.delete("/api/v1/projects/proj_busy")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "project_busy"
    assert await count(sessions, Project, Project.id == "proj_busy") == 1


async def test_a_project_of_another_workspace_is_a_404(client: AsyncClient, sessions) -> None:  # type: ignore[no-untyped-def]
    async with sessions() as session:
        session.add(Workspace(id="wks_other", name="Autre", owner_id=LOCAL_USER_ID))
        await session.commit()
    await add_project(sessions, "proj_far", workspace_id="wks_other")
    async with sessions() as session:  # the local user is not a member of it
        assert await session.get(Membership, ("wks_other", LOCAL_USER_ID)) is None

    response = await client.delete("/api/v1/projects/proj_far")

    assert response.status_code == 404
    assert await count(sessions, Project, Project.id == "proj_far") == 1


async def test_a_developer_cannot_delete_a_project(client: AsyncClient, sessions) -> None:  # type: ignore[no-untyped-def]
    await add_project(sessions, "proj_dev")
    async with sessions() as session:
        session.add(User(id="usr_dev", local_identity="dev", display_name="Dev"))
        await session.flush()
        session.add(
            Membership(workspace_id=LOCAL_WORKSPACE_ID, user_id="usr_dev", role="developer")
        )
        await session.commit()
    app = client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[get_user_id] = lambda: "usr_dev"
    try:
        response = await client.delete("/api/v1/projects/proj_dev")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
