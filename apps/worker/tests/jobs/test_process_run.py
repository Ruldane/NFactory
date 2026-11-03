"""The worker job drives a run stored in Postgres: states, steps, events, artifacts."""

import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.services.identity import LOCAL_WORKSPACE_ID, ensure_local_identity
from nfactory_core.config import Settings
from nfactory_core.models import Artifact, EventRecord, Project, Run, RunStep
from nfactory_core.pipeline import step_names
from nfactory_worker.jobs import process_run
from nfactory_worker.recipes import get_recipe
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


async def new_run(
    sessions: Sessions,
    project_type: str,
    request: str,
    state: str = "QUEUED",
    **run_fields: Any,
) -> str:
    async with sessions() as session:
        project = Project(workspace_id=LOCAL_WORKSPACE_ID, title="Projet test", type=project_type)
        session.add(project)
        await session.flush()
        run = Run(project_id=project.id, request=request, state=state, **run_fields)
        session.add(run)
        await session.commit()
        return run.id


def settings_for(tmp_path: Path) -> Settings:
    return Settings(
        artifact_root=str(tmp_path / "artifacts"), workspace_root=str(tmp_path / "workspaces")
    )


async def run_job(
    sessions: Sessions, tmp_path: Path, run_id: str, recipes: Any = get_recipe
) -> None:
    settings = settings_for(tmp_path)
    await process_run(
        run_id,
        sessions=sessions,
        settings=settings,
        runner=LocalRunner(Path(settings.workspace_root), python=sys.executable),
        recipes=recipes,
    )


async def load(sessions: Sessions, run_id: str) -> tuple[Run, list[RunStep], list[EventRecord]]:
    async with sessions() as session:
        run = await session.get_one(Run, run_id)
        steps = list(
            await session.scalars(
                select(RunStep).where(RunStep.run_id == run_id).order_by(RunStep.position)
            )
        )
        events = list(
            await session.scalars(
                select(EventRecord).where(EventRecord.run_id == run_id).order_by(EventRecord.seq)
            )
        )
        return run, steps, events


async def test_completed_run_is_fully_recorded(sessions: Sessions, tmp_path: Path) -> None:
    run_id = await new_run(sessions, "api", "API pour l'inventaire du matériel")

    await run_job(sessions, tmp_path, run_id)

    run, steps, events = await load(sessions, run_id)
    assert run.state == "COMPLETED"
    assert run.started_at and run.finished_at and run.error is None
    assert run.cost_estimate_usd == 0.0  # demo model: nothing billed
    assert [s.name for s in steps] == list(step_names())
    assert {s.state for s in steps} == {"SUCCEEDED"}
    assert steps[0].output["brief"]["entity"]["plural"] == "equipements"
    types = [e.type for e in events]
    assert types[0] == "run.started" and types[-1] == "run.completed"
    assert "test.passed" in types
    async with sessions() as session:
        artifacts = list(await session.scalars(select(Artifact).where(Artifact.run_id == run_id)))
    assert [a.filename for a in artifacts] == ["projet-test.zip"]
    assert artifacts[0].checksum.startswith("sha256:")
    assert (tmp_path / "artifacts" / artifacts[0].storage_key).is_file()


async def test_run_budget_and_trace_id_come_from_the_stored_run(
    sessions: Sessions, tmp_path: Path
) -> None:
    run_id = await new_run(
        sessions,
        "excel",
        "Suivi des heures",
        budget={"max_llm_calls": 2},
        trace_id="0123456789abcdef0123456789abcdef",
    )

    await run_job(sessions, tmp_path, run_id)

    run, _steps, events = await load(sessions, run_id)
    assert run.state == "FAILED"
    assert "Budget" in (run.error or "")
    agent_events = [e for e in events if e.type == "agent.progress"]
    assert len(agent_events) == 2
    trace_ids = {e.payload_redacted["trace_id"] for e in agent_events}
    assert trace_ids == {"0123456789abcdef0123456789abcdef"}


async def test_failed_run_records_the_cause_and_skips_the_rest(
    sessions: Sessions, tmp_path: Path
) -> None:
    run_id = await new_run(sessions, "feature", "Fonctionnalité")  # recipe planned, not built

    await run_job(sessions, tmp_path, run_id)

    run, steps, events = await load(sessions, run_id)
    assert run.state == "FAILED"
    assert "existing-github-feature" in (run.error or "")
    assert steps[0].state == "FAILED"
    assert {s.state for s in steps[1:]} == {"SKIPPED"}
    assert events[-1].type == "run.failed"


async def test_run_cancelled_by_the_user_mid_way_stops(sessions: Sessions, tmp_path: Path) -> None:
    run_id = await new_run(sessions, "document", "Procédure de sauvegarde")

    async def user_clicks_cancel_after(step: str) -> None:
        if step == "build":
            async with sessions() as session:
                await session.execute(update(Run).where(Run.id == run_id).values(state="CANCELLED"))
                await session.commit()

    settings = settings_for(tmp_path)
    await process_run(
        run_id,
        sessions=sessions,
        settings=settings,
        runner=LocalRunner(Path(settings.workspace_root), python=sys.executable),
        after_step=user_clicks_cancel_after,
    )

    run, steps, events = await load(sessions, run_id)
    assert run.state == "CANCELLED"
    by_name = {s.name: s.state for s in steps}
    assert by_name["build"] == "SUCCEEDED"
    assert by_name["checks"] == by_name["package"] == "CANCELLED"
    assert events[-1].type == "run.cancelled"


async def test_run_already_finished_is_left_untouched(sessions: Sessions, tmp_path: Path) -> None:
    run_id = await new_run(sessions, "api", "API", state="CANCELLED")

    await run_job(sessions, tmp_path, run_id)

    run, _steps, events = await load(sessions, run_id)
    assert run.state == "CANCELLED" and run.started_at is None
    assert events == []


async def test_a_child_run_starts_from_its_parents_delivered_brief(
    sessions: Sessions, tmp_path: Path
) -> None:
    parent_id = await new_run(sessions, "api", "Une API d'annuaire des contacts")
    await run_job(sessions, tmp_path, parent_id)
    parent, parent_steps, _ = await load(sessions, parent_id)
    assert parent.state == "COMPLETED"
    async with sessions() as session:
        child = Run(
            project_id=parent.project_id,
            parent_run_id=parent_id,
            request="Ajoute un filtre par département",
            state="QUEUED",
        )
        session.add(child)
        await session.commit()
        child_id = child.id

    await run_job(sessions, tmp_path, child_id)

    run, steps, events = await load(sessions, child_id)
    assert run.state == "COMPLETED", run.error
    by_name = {s.name: s for s in steps}
    delivered = next(s for s in parent_steps if s.name == "requirements").output["brief"]
    fields = [f["name"] for f in by_name["requirements"].output["brief"]["entity"]["fields"]]
    assert fields == [*(f["name"] for f in delivered["entity"]["fields"]), "departement"]
    assert by_name["package"].output["changes"]["parent_run_id"] == parent_id
    assert "changes.computed" in [e.type for e in events]
    async with sessions() as session:
        names = await session.scalars(select(Artifact.filename).where(Artifact.run_id == child_id))
        assert "modifications.diff" in list(names)
