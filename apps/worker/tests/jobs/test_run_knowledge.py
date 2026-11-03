"""A real run searches its project's knowledge base (tasks 3.4, 3.5), in the database."""

import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.services.identity import LOCAL_WORKSPACE_ID, ensure_local_identity
from nfactory_core.config import Settings
from nfactory_core.knowledge import Scope, ingest
from nfactory_core.models import EventRecord, Project, Run
from nfactory_worker.jobs import process_run
from nfactory_worker.runner import LocalRunner

pytestmark = pytest.mark.integration

Sessions = async_sessionmaker[AsyncSession]


@pytest.fixture
async def sessions(migrated_database_url: str) -> AsyncIterator[Sessions]:
    engine = create_async_engine(migrated_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await ensure_local_identity(session)
        await session.commit()
    yield factory
    await engine.dispose()


async def _project(sessions: Sessions, title: str) -> str:
    async with sessions() as session:
        project = Project(workspace_id=LOCAL_WORKSPACE_ID, title=title, type="document")
        session.add(project)
        await session.commit()
        return project.id


async def _run(sessions: Sessions, tmp_path: Path, project_id: str, request: str) -> str:
    async with sessions() as session:
        run = Run(project_id=project_id, request=request, state="QUEUED")
        session.add(run)
        await session.commit()
        run_id = run.id
    settings = Settings(
        artifact_root=str(tmp_path / "artifacts"), workspace_root=str(tmp_path / "workspaces")
    )
    runner = LocalRunner(tmp_path / "workspaces", python=sys.executable)
    await process_run(run_id, sessions=sessions, settings=settings, runner=runner, retry_delay_s=0)
    return run_id


async def _retrieved(sessions: Sessions, run_id: str) -> list[dict[str, object]]:
    async with sessions() as session:
        rows = await session.scalars(
            select(EventRecord).where(
                EventRecord.run_id == run_id, EventRecord.type == "knowledge.retrieved"
            )
        )
        return [row.payload_redacted for row in rows]


async def test_a_run_cites_its_projects_documents_only(sessions: Sessions, tmp_path: Path) -> None:
    mine, other = await _project(sessions, "Licences"), await _project(sessions, "Paie")
    async with sessions() as session:
        await ingest(
            session,
            Scope(LOCAL_WORKSPACE_ID, mine),
            "licences.md",
            b"# Renouvellement\n\nRenouveler chaque licence 30 jours avant.\n",
        )
        await ingest(
            session,
            Scope(LOCAL_WORKSPACE_ID, other),
            "paie.md",
            b"# Renouvellement paie\n\nLe renouvellement des licences de paie.\n",
        )
        await session.commit()

    run_id = await _run(sessions, tmp_path, mine, "Procédure de renouvellement des licences")

    (event,) = await _retrieved(sessions, run_id)
    paths = [s["path"] for s in event["sources"]]  # type: ignore[index]
    assert paths == ["licences.md"]
    assert event["sources"][0]["start_line"] == 1  # type: ignore[index]
    async with sessions() as session:
        run = await session.get_one(Run, run_id)
        assert run.state == "COMPLETED"


async def test_a_project_without_documents_searches_nothing(
    sessions: Sessions, tmp_path: Path
) -> None:
    project = await _project(sessions, "Vide")

    run_id = await _run(sessions, tmp_path, project, "Note de cadrage")

    assert await _retrieved(sessions, run_id) == []
