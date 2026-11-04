"""ARQ worker entry point. Run with: arq nfactory_worker.main.WorkerSettings

Jobs: `ping` (health), `run_factory` (one factory run), `index_knowledge` (the
missing knowledge vectors of a workspace) and `check_agent_task` (test a coding
agent's change in the sandbox). Nightly, `apply_retention` deletes what each workspace
chose not to keep (ADR-0015). Startup prepares the
database session factory and the LangGraph checkpoint tables.
"""

import logging
import sys
from pathlib import Path
from typing import Any

from arq import cron
from arq.connections import RedisSettings
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from nfactory_core.config import Settings, get_settings
from nfactory_core.events import run_channel
from nfactory_core.pipeline import RUN_QUEUE
from nfactory_core.telemetry import tracer_provider
from nfactory_worker.jobs import process_run
from nfactory_worker.jobs.agent_checks import check_agent_task as run_agent_check
from nfactory_worker.jobs.indexing import index_pending_workspaces, index_workspace
from nfactory_worker.jobs.recovery import recover_orphaned_runs, run_lease
from nfactory_worker.jobs.retention import apply_retention as apply_retention_policy
from nfactory_worker.runner import LocalRunner, Runner, SandboxRunner

QUEUE_NAME = RUN_QUEUE
log = logging.getLogger("nfactory.worker")


async def ping(ctx: dict[str, Any]) -> str:
    return "pong"


def checkpoint_url(settings: Settings) -> str:
    """LangGraph's checkpointer speaks libpq URLs, not SQLAlchemy ones."""
    url = make_url(settings.database_url).set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


def make_runner(settings: Settings) -> Runner:
    if settings.nfactory_sandbox_url:
        token = settings.nfactory_sandbox_token.get_secret_value()
        return SandboxRunner(settings.nfactory_sandbox_url, token)
    # Development without the sandbox container: same rules, no OS isolation.
    log.warning("No sandbox configured: generated code runs as local subprocesses.")
    return LocalRunner(Path(settings.workspace_root), python=sys.executable)


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    ctx["engine"] = engine
    ctx["sessions"] = async_sessionmaker(engine, expire_on_commit=False)
    ctx["settings"] = settings
    ctx["runner"] = make_runner(settings)
    provider = tracer_provider(settings.otel_exporter_otlp_endpoint, "nfactory-worker")
    ctx["tracer_provider"] = provider
    ctx["tracer"] = provider.get_tracer("nfactory.worker") if provider else None
    async with AsyncPostgresSaver.from_conn_string(checkpoint_url(settings)) as saver:
        await saver.setup()
    # Runs left RUNNING by a worker that died: resume them now, not after ARQ's timeout.
    await recover_runs(ctx)


async def shutdown(ctx: dict[str, Any]) -> None:
    provider = ctx.get("tracer_provider")
    if provider is not None:
        provider.shutdown()  # flush the last spans
    engine = ctx.get("engine")
    if engine is not None:
        await engine.dispose()


async def run_factory(ctx: dict[str, Any], run_id: str) -> str:
    settings: Settings = ctx["settings"]
    redis = ctx.get("redis")

    async def notify(changed_run_id: str) -> None:
        # Wake up SSE streams; the events table stays the source of truth.
        if redis is not None:
            await redis.publish(run_channel(changed_run_id), "1")

    async with (
        run_lease(ctx["redis"], run_id),
        AsyncPostgresSaver.from_conn_string(checkpoint_url(settings)) as checkpointer,
    ):
        result = await process_run(
            run_id,
            sessions=ctx["sessions"],
            settings=settings,
            runner=ctx["runner"],
            checkpointer=checkpointer,
            notify=notify,
            tracer=ctx.get("tracer"),
        )
    return result.outcome if result else "SKIPPED"


async def index_knowledge(ctx: dict[str, Any], workspace_id: str) -> int:
    report = await index_workspace(ctx["sessions"], workspace_id, ctx["settings"])
    return report.embedded


async def check_agent_task(ctx: dict[str, Any], check_id: str) -> str:
    return await run_agent_check(ctx["sessions"], ctx["settings"], ctx["runner"], check_id)


async def index_pending(ctx: dict[str, Any]) -> list[str]:
    """Catch-up for an indexing job that could not be queued or was dropped."""
    return await index_pending_workspaces(ctx["sessions"], ctx["settings"])


async def recover_runs(ctx: dict[str, Any]) -> list[str]:
    return await recover_orphaned_runs(ctx["sessions"], ctx["redis"])


async def apply_retention(ctx: dict[str, Any]) -> int:
    purge, _sweep = await apply_retention_policy(ctx["sessions"], ctx["settings"])
    return purge.runs


def build_worker_settings(settings: Settings) -> dict[str, Any]:
    return {
        "functions": [ping, run_factory, index_knowledge, check_agent_task],
        "on_startup": startup,
        "on_shutdown": shutdown,
        # Also catches a worker that died while another one keeps running.
        "cron_jobs": [
            cron(recover_runs, second={0}, run_at_startup=False),
            cron(index_pending, second={30}, run_at_startup=True),
            cron(apply_retention, hour={3}, minute={15}, run_at_startup=True),
        ],
        "redis_settings": RedisSettings.from_dsn(settings.redis_url),
        "queue_name": QUEUE_NAME,
        "max_jobs": settings.max_concurrent_runs,
        "job_timeout": settings.default_run_timeout_seconds,
        "max_tries": 3,
        # The job id is the run id: a kept result would block queuing a paused run
        # again after the user's decision. Results live in Postgres anyway.
        "keep_result": 0,
        "health_check_interval": 10,
    }


class WorkerSettings:
    """ARQ reads plain class attributes, so copy the computed settings onto the class."""


for _key, _value in build_worker_settings(get_settings()).items():
    setattr(WorkerSettings, _key, _value)
