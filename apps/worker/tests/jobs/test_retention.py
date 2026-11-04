"""Retention (ADR-0015): the worker purges what a workspace chose not to keep, then
sweeps the files and LangGraph checkpoints whose run no longer exists."""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from langgraph.checkpoint.base import empty_checkpoint
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.services.identity import LOCAL_USER_ID, LOCAL_WORKSPACE_ID, ensure_local_identity
from nfactory_core.models import (
    Artifact,
    AuditLog,
    EventRecord,
    Project,
    Run,
    RunStep,
    User,
    Workspace,
)
from nfactory_core.models.auth import AuthSession, LoginAttempt
from nfactory_worker.jobs.retention import purge_expired, sweep_orphans

pytestmark = pytest.mark.integration

Sessions = async_sessionmaker[AsyncSession]
NOW = datetime(2026, 11, 4, 3, 0, tzinfo=UTC)
OTHER_WORKSPACE = "wks_other"


@pytest.fixture
async def sessions(migrated_database_url: str) -> AsyncIterator[Sessions]:
    engine = create_async_engine(migrated_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await ensure_local_identity(session)
        session.add(Workspace(id=OTHER_WORKSPACE, name="Autre", owner_id=LOCAL_USER_ID))
        await session.commit()
    yield factory
    await engine.dispose()


async def set_policy(sessions: Sessions, workspace_id: str, **retention: int) -> None:
    async with sessions() as session:
        workspace = await session.get_one(Workspace, workspace_id)
        workspace.data_policy = {"retention": retention}
        await session.commit()


async def add_run(
    sessions: Sessions,
    *,
    state: str = "COMPLETED",
    age_days: int,
    workspace_id: str = LOCAL_WORKSPACE_ID,
) -> str:
    """A run finished `age_days` ago, with a step, an event and a deliverable."""
    when = NOW - timedelta(days=age_days)
    async with sessions() as session:
        project = Project(workspace_id=workspace_id, title="Projet", type="api")
        session.add(project)
        await session.flush()
        run_id = f"run_{uuid.uuid4().hex[:20]}"
        session.add(
            Run(
                id=run_id,
                project_id=project.id,
                request="API",
                state=state,
                created_at=when,
                finished_at=when if state in {"COMPLETED", "FAILED", "CANCELLED"} else None,
            )
        )
        await session.flush()
        session.add(RunStep(run_id=run_id, position=0, name="requirements", agent_role="pm"))
        session.add(
            EventRecord(id=f"evt_{uuid.uuid4().hex[:20]}", run_id=run_id, type="run.started")
        )
        session.add(
            Artifact(
                project_id=project.id,
                run_id=run_id,
                filename="livrable.zip",
                mime="application/zip",
                storage_key=f"{run_id}/livrable.zip",
                checksum="sha256:00",
                size=1,
            )
        )
        await session.commit()
        return run_id


async def count(sessions: Sessions, model: type, *where: object) -> int:
    async with sessions() as session:
        return await session.scalar(select(func.count()).select_from(model).where(*where)) or 0


async def test_without_a_policy_nothing_is_deleted(sessions: Sessions) -> None:
    run_id = await add_run(sessions, age_days=4000)

    report = await purge_expired(sessions, now=NOW)

    assert report.runs == 0
    assert await count(sessions, Run, Run.id == run_id) == 1
    assert await count(sessions, AuditLog) == 0


async def test_finished_runs_past_the_policy_go_with_their_rows(sessions: Sessions) -> None:
    await set_policy(sessions, LOCAL_WORKSPACE_ID, runs_days=30)
    old = await add_run(sessions, age_days=31)
    recent = await add_run(sessions, age_days=29)
    old_failed = await add_run(sessions, state="FAILED", age_days=200)

    report = await purge_expired(sessions, now=NOW)

    assert report.runs == 2
    assert await count(sessions, Run, Run.id.in_([old, old_failed])) == 0
    assert await count(sessions, Run, Run.id == recent) == 1
    gone = [old, old_failed]
    assert await count(sessions, RunStep, RunStep.run_id.in_(gone)) == 0
    assert await count(sessions, EventRecord, EventRecord.run_id.in_(gone)) == 0
    assert await count(sessions, Artifact, Artifact.storage_key.like(f"{old}/%")) == 0
    assert await count(sessions, Artifact, Artifact.storage_key.like(f"{recent}/%")) == 1


async def test_an_active_run_is_never_purged(sessions: Sessions) -> None:
    await set_policy(sessions, LOCAL_WORKSPACE_ID, runs_days=7)
    paused = await add_run(sessions, state="APPROVAL_PENDING", age_days=400)
    running = await add_run(sessions, state="RUNNING", age_days=400)

    await purge_expired(sessions, now=NOW)

    assert await count(sessions, Run, Run.id.in_([paused, running])) == 2


async def test_a_policy_only_applies_to_its_own_workspace(sessions: Sessions) -> None:
    await set_policy(sessions, LOCAL_WORKSPACE_ID, runs_days=7)
    elsewhere = await add_run(sessions, age_days=400, workspace_id=OTHER_WORKSPACE)

    await purge_expired(sessions, now=NOW)

    assert await count(sessions, Run, Run.id == elsewhere) == 1


async def test_old_audit_entries_go_and_the_purge_is_audited(sessions: Sessions) -> None:
    await set_policy(sessions, LOCAL_WORKSPACE_ID, runs_days=30, audit_days=180)
    await add_run(sessions, age_days=60)
    async with sessions() as session:
        for days, action in ((181, "old.action"), (10, "recent.action")):
            session.add(
                AuditLog(
                    workspace_id=LOCAL_WORKSPACE_ID,
                    actor_id=LOCAL_USER_ID,
                    action=action,
                    target="x",
                    timestamp=NOW - timedelta(days=days),
                )
            )
        session.add(
            AuditLog(
                workspace_id=OTHER_WORKSPACE,
                action="other.workspace",
                target="x",
                timestamp=NOW - timedelta(days=4000),
            )
        )
        await session.commit()

    report = await purge_expired(sessions, now=NOW)

    assert report.audit_entries == 1
    async with sessions() as session:
        actions = set(await session.scalars(select(AuditLog.action)))
        purge = await session.scalar(select(AuditLog).where(AuditLog.action == "retention.purge"))
    assert actions == {"recent.action", "other.workspace", "retention.purge"}
    assert purge is not None and purge.actor_id is None
    assert purge.workspace_id == LOCAL_WORKSPACE_ID
    assert purge.redacted_details == {"runs": 1, "audit_entries": 1}


async def test_ended_sign_in_state_is_always_deleted(sessions: Sessions) -> None:
    async with sessions() as session:
        session.add(User(id="usr_ada", email="ada@example.fr", display_name="Ada"))
        await session.flush()
        hour = timedelta(hours=1)
        for token, expires, revoked in (
            ("a" * 64, NOW - hour, None),  # expired
            ("b" * 64, NOW + hour, NOW - hour),  # revoked
            ("c" * 64, NOW + hour, None),  # open
        ):
            session.add(
                AuthSession(
                    user_id="usr_ada", token_hash=token, expires_at=expires, revoked_at=revoked
                )
            )
        session.add(LoginAttempt(state="s1", nonce="n", verifier="v", expires_at=NOW - hour))
        session.add(LoginAttempt(state="s2", nonce="n", verifier="v", expires_at=NOW + hour))
        await session.commit()

    report = await purge_expired(sessions, now=NOW)

    assert report.sign_in_rows == 3
    async with sessions() as session:
        assert set(await session.scalars(select(AuthSession.token_hash))) == {"c" * 64}
        assert set(await session.scalars(select(LoginAttempt.state))) == {"s2"}


async def test_the_sweep_removes_run_folders_with_no_run_left(
    sessions: Sessions, tmp_path: Path
) -> None:
    kept = await add_run(sessions, age_days=1)
    artifacts, workspaces = tmp_path / "artifacts", tmp_path / "workspaces"
    for root in (artifacts, workspaces):
        for name in (kept, "run_gone", "agc_check"):
            (root / name).mkdir(parents=True)
            (root / name / "file.txt").write_text("x", encoding="utf-8")
        (root / "run_file_not_folder").write_text("x", encoding="utf-8")

    report = await sweep_orphans(sessions, [artifacts, workspaces])

    assert report.folders == 2
    for root in (artifacts, workspaces):
        names = {p.name for p in root.iterdir()}
        assert names == {kept, "agc_check", "run_file_not_folder"}


async def test_the_sweep_skips_a_missing_root(sessions: Sessions, tmp_path: Path) -> None:
    report = await sweep_orphans(sessions, [tmp_path / "absent"])

    assert report.folders == 0 and report.checkpoints == 0


async def test_the_sweep_drops_checkpoints_of_deleted_runs(
    sessions: Sessions, migrated_database_url: str, tmp_path: Path
) -> None:
    kept = await add_run(sessions, age_days=1)
    libpq = make_url(migrated_database_url).set(drivername="postgresql")
    async with AsyncPostgresSaver.from_conn_string(
        libpq.render_as_string(hide_password=False)
    ) as saver:
        await saver.setup()
        for thread in (kept, "run_gone"):
            config = {"configurable": {"thread_id": thread, "checkpoint_ns": ""}}
            await saver.aput(config, empty_checkpoint(), {}, {})  # type: ignore[arg-type]

    report = await sweep_orphans(sessions, [tmp_path])

    assert report.checkpoints >= 1
    async with sessions() as session:
        threads = set(await session.scalars(text("SELECT DISTINCT thread_id FROM checkpoints")))
    assert threads == {kept}
