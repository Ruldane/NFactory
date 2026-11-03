"""Durability (task 1.9): a worker that dies mid-run resumes from the Postgres
checkpoint instead of starting over."""

import uuid
from collections.abc import AsyncIterator

import psycopg
import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from nfactory_worker.pipeline import execute_run
from nfactory_worker.recipes import Recipe, get_recipe

pytestmark = pytest.mark.integration

ADMIN_URL = "postgresql://nfactory:nfactory_dev_only@127.0.0.1:55432/postgres"


class WorkerCrash(BaseException):
    """Like a killed process: not an Exception, so nothing in the pipeline catches it."""


@pytest.fixture
async def checkpointer() -> AsyncIterator[AsyncPostgresSaver]:
    name = f"nfactory_ckpt_{uuid.uuid4().hex[:10]}"
    async with await psycopg.AsyncConnection.connect(ADMIN_URL, autocommit=True) as admin:
        await admin.execute(f'CREATE DATABASE "{name}"')
    try:
        url = ADMIN_URL.rsplit("/", 1)[0] + f"/{name}"
        async with AsyncPostgresSaver.from_conn_string(url) as saver:
            await saver.setup()
            yield saver
    finally:
        async with await psycopg.AsyncConnection.connect(ADMIN_URL, autocommit=True) as admin:
            await admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


async def test_crashed_run_resumes_at_the_interrupted_step(harness, checkpointer) -> None:  # type: ignore[no-untyped-def]
    calls = {"build": 0}

    def crashing_once(kind: str) -> Recipe:
        recipe = get_recipe(kind)
        if harness.reporter.started[-1:] == ["build"]:
            calls["build"] += 1
            if calls["build"] == 1:
                raise WorkerCrash
        return recipe

    deps = harness.deps(recipes=crashing_once)
    run = harness.input("api", "python-api", "API des licences")

    with pytest.raises(WorkerCrash):
        await execute_run(deps, run, checkpointer)
    assert harness.reporter.started == ["requirements", "plan", "architect", "build"]

    result = await execute_run(deps, run, checkpointer)

    assert result.outcome == "COMPLETED"
    # Earlier steps were not run again; build was retried from its checkpoint.
    assert harness.reporter.attempts["requirements"] == 1
    assert harness.reporter.attempts["build"] == 2


async def test_finished_run_is_not_executed_twice(harness, checkpointer) -> None:  # type: ignore[no-untyped-def]
    run = harness.input("document", "document", "Note de cadrage")
    first = await execute_run(harness.deps(), run, checkpointer)
    started = len(harness.reporter.started)

    again = await execute_run(harness.deps(), run, checkpointer)

    assert again == first
    assert len(harness.reporter.started) == started


async def test_paused_run_resumes_at_the_failed_step_on_the_new_engine(
    harness, checkpointer
) -> None:  # type: ignore[no-untyped-def]
    """Task 2.8: after the user picks a replacement, finished steps are kept."""
    from nfactory_core.providers import ProviderError
    from nfactory_worker.agents import Engines

    class QuotaGone:
        async def complete(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise ProviderError("quota", provider="openai_api", status=429)

    demo = harness.demo()
    broken = type(demo)(QuotaGone(), "openai_api", "model-x", demo=False)  # type: ignore[arg-type]
    first = Engines({**Engines.single(demo).llms, "reviewer": broken}, fallback="ask_user")
    run = harness.input("document", "document", "Note de cadrage")

    paused = await execute_run(harness.deps(engines=first), run, checkpointer)
    assert paused.outcome == "APPROVAL_PENDING"
    assert paused.pause and paused.pause["role"] == "reviewer"

    result = await execute_run(harness.deps(engines=Engines.single(demo)), run, checkpointer)

    assert result.outcome == "COMPLETED"
    assert harness.reporter.attempts["requirements"] == 1
    assert harness.reporter.attempts["review"] == 2
