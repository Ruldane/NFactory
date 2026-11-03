import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.demo import seed_demo
from nfactory_core.models import Approval, EventRecord, Project, Run, RunStep

pytestmark = pytest.mark.integration


async def _count(session: AsyncSession, model: type) -> int:
    return await session.scalar(select(func.count()).select_from(model)) or 0


async def test_seed_creates_demo_projects_with_runs(db_session: AsyncSession) -> None:
    await seed_demo(db_session)

    projects = (await db_session.scalars(select(Project))).all()
    assert len(projects) >= 4
    assert all(p.is_demo for p in projects)
    assert {p.type for p in projects} >= {"webapp", "api", "excel", "powershell"}
    assert await _count(db_session, Run) == len(projects)


async def test_seed_is_idempotent(db_session: AsyncSession) -> None:
    await seed_demo(db_session)
    first = [await _count(db_session, m) for m in (Project, Run, RunStep, EventRecord, Approval)]

    await seed_demo(db_session)
    second = [await _count(db_session, m) for m in (Project, Run, RunStep, EventRecord, Approval)]

    assert first == second


async def test_failed_demo_run_is_honest(db_session: AsyncSession) -> None:
    # A failed run must show why it failed, never look "ready".
    await seed_demo(db_session)

    failed = (await db_session.scalars(select(Run).where(Run.state == "FAILED"))).all()
    assert failed
    for run in failed:
        assert run.error
        steps = (await db_session.scalars(select(RunStep).where(RunStep.run_id == run.id))).all()
        assert any(s.state == "FAILED" for s in steps)
        tests = next(s for s in steps if s.name == "tests")
        # Its repair history, as a real run records it (repair_log).
        assert [r["attempt"] for r in tests.output["repairs"]] == [1, 2, 3]


async def test_pending_approval_belongs_to_waiting_run(db_session: AsyncSession) -> None:
    await seed_demo(db_session)

    approval = await db_session.scalar(select(Approval).where(Approval.status == "pending"))
    assert approval is not None
    run = await db_session.get(Run, approval.run_id)
    assert run is not None and run.state == "APPROVAL_PENDING"
