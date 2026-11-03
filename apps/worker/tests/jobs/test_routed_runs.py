"""Routed runs (task 2.8): the worker calls the engines frozen in the run, through the
real adapters (provider servers mocked with respx), and never switches engine alone."""

import json
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.services.identity import LOCAL_WORKSPACE_ID, ensure_local_identity
from nfactory_core.config import Settings
from nfactory_core.models import Approval, EventRecord, Project, ProviderConnection, Run, RunStep
from nfactory_core.routing import ROLES
from nfactory_core.secrets import SecretStore
from nfactory_worker.agents.demo import respond
from nfactory_worker.jobs import NoModelConfiguredError, build_engines, process_run
from nfactory_worker.runner import LocalRunner

pytestmark = pytest.mark.integration

Sessions = async_sessionmaker[AsyncSession]
MASTER = "worker-tests-master-key-0123456789abcdef"
KEY = "sk-worker-test-0123456789abcdefghijkl"
CHAT = "https://api.openai.com/v1/chat/completions"
PRICE = {"input_per_mtok": 1.0, "output_per_mtok": 2.0, "cached_input_per_mtok": None}


@pytest.fixture
async def sessions(migrated_database_url: str) -> AsyncIterator[Sessions]:
    engine = create_async_engine(migrated_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await ensure_local_identity(session)
        session.add(
            ProviderConnection(
                workspace_id=LOCAL_WORKSPACE_ID,
                kind="openai_api",
                display_name="OpenAI",
                status="connected",
                secret_ref=await SecretStore(MASTER).put(session, LOCAL_WORKSPACE_ID, KEY),
            )
        )
        await session.commit()
    yield factory
    await engine.dispose()


def routed(fallback: str = "ask_user", pricing: dict[str, Any] | None = PRICE) -> dict[str, Any]:
    route = {"provider": "openai_api", "model": "model-x", "pricing": pricing}
    return {
        "mode": "routed",
        "routes": {role: dict(route) for role in ROLES},
        "fallback": fallback,
        "local_only": False,
    }


def settings_for(tmp_path: Path) -> Settings:
    return Settings(
        artifact_root=str(tmp_path / "artifacts"),
        workspace_root=str(tmp_path / "workspaces"),
        nfactory_secret_key=MASTER,  # type: ignore[arg-type]
        nfactory_demo_mode=False,
    )


async def new_run(sessions: Sessions, provider_config: dict[str, Any]) -> str:
    async with sessions() as session:
        project = Project(workspace_id=LOCAL_WORKSPACE_ID, title="Note", type="document")
        session.add(project)
        await session.flush()
        run = Run(
            project_id=project.id,
            request="Note de cadrage du projet de stock",
            state="QUEUED",
            provider_config=provider_config,
        )
        session.add(run)
        await session.commit()
        return run.id


async def run_job(sessions: Sessions, tmp_path: Path, run_id: str) -> None:
    settings = settings_for(tmp_path)
    await process_run(
        run_id,
        sessions=sessions,
        settings=settings,
        runner=LocalRunner(Path(settings.workspace_root), python=sys.executable),
        retry_delay_s=0,
    )


def openai_brain(request: httpx.Request) -> httpx.Response:
    """An OpenAI-shaped server answering with the demo brain."""
    assert request.headers["authorization"] == f"Bearer {KEY}"
    body = json.loads(request.content)
    return httpx.Response(
        200,
        json={
            "model": body["model"],
            "choices": [
                {"message": {"content": respond(body["messages"])}, "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        },
    )


@respx.mock
async def test_a_routed_run_uses_its_provider_and_records_a_measured_cost(
    sessions: Sessions, tmp_path: Path
) -> None:
    chat = respx.post(CHAT).mock(side_effect=openai_brain)
    run_id = await new_run(sessions, routed())

    await run_job(sessions, tmp_path, run_id)

    async with sessions() as session:
        run = await session.get_one(Run, run_id)
        events = list(
            await session.scalars(select(EventRecord).where(EventRecord.run_id == run_id))
        )
    assert run.state == "COMPLETED", run.error
    calls = chat.call_count
    assert calls >= 4  # a document needs no architect (spec §5)
    assert run.cost_estimate_usd == pytest.approx(calls * (100 * 1.0 + 50 * 2.0) / 1e6)
    progress = [e.payload_redacted for e in events if e.type == "agent.progress"]
    assert {p["provider"] for p in progress} == {"openai_api"}
    assert "architect" not in {p["agent"] for p in progress}
    assert all(KEY not in json.dumps(e.payload_redacted) for e in events)


@respx.mock
async def test_an_unpriced_model_leaves_the_cost_unmeasured(
    sessions: Sessions, tmp_path: Path
) -> None:
    respx.post(CHAT).mock(side_effect=openai_brain)
    run_id = await new_run(sessions, routed(pricing=None))

    await run_job(sessions, tmp_path, run_id)

    async with sessions() as session:
        run = await session.get_one(Run, run_id)
    assert run.state == "COMPLETED"
    assert run.cost_estimate_usd is None


@respx.mock
async def test_an_exhausted_quota_pauses_the_run_for_the_user(
    sessions: Sessions, tmp_path: Path
) -> None:
    respx.post(CHAT).mock(
        return_value=httpx.Response(429, json={"error": {"code": "insufficient_quota"}})
    )
    run_id = await new_run(sessions, routed("ask_user"))

    await run_job(sessions, tmp_path, run_id)

    async with sessions() as session:
        run = await session.get_one(Run, run_id)
        steps = list(await session.scalars(select(RunStep).where(RunStep.run_id == run_id)))
        approvals = list(await session.scalars(select(Approval).where(Approval.run_id == run_id)))
        types = list(
            await session.scalars(select(EventRecord.type).where(EventRecord.run_id == run_id))
        )
    assert run.state == "APPROVAL_PENDING"
    assert run.finished_at is None
    [approval] = approvals
    assert approval.action_type == "provider_fallback" and approval.status == "pending"
    assert approval.details["role"] == "requirements"
    assert approval.details["provider"] == "openai_api"
    assert approval.details["kind"] == "quota"
    assert "quota" in approval.summary
    assert {s.state for s in steps if s.name != "architect"} == {"PENDING"}
    assert "approval.requested" in types and "run.failed" not in types


@respx.mock
async def test_with_fallback_none_the_run_fails_with_the_provider_reason(
    sessions: Sessions, tmp_path: Path
) -> None:
    respx.post(CHAT).mock(return_value=httpx.Response(401, json={"error": {"message": "no"}}))
    run_id = await new_run(sessions, routed("none"))

    await run_job(sessions, tmp_path, run_id)

    async with sessions() as session:
        run = await session.get_one(Run, run_id)
    assert run.state == "FAILED"
    assert (run.error or "").startswith("OpenAI : clé refusée")


async def test_engines_come_from_the_frozen_routing(sessions: Sessions, tmp_path: Path) -> None:
    async with sessions() as session:
        engines = await build_engines(session, routed(), LOCAL_WORKSPACE_ID, settings_for(tmp_path))

    llm = engines.for_role("reviewer")
    assert (llm.provider_name, llm.model, llm.demo) == ("openai_api", "model-x", False)
    assert llm.pricing is not None and llm.pricing.output_per_mtok == 2.0
    assert engines.fallback == "ask_user"


async def test_a_run_without_engines_outside_demo_mode_is_refused(
    sessions: Sessions, tmp_path: Path
) -> None:
    # No silent fallback to any provider (spec §8).
    async with sessions() as session:
        with pytest.raises(NoModelConfiguredError):
            await build_engines(session, {}, LOCAL_WORKSPACE_ID, settings_for(tmp_path))


@respx.mock
async def test_no_table_holds_the_key_after_a_run(sessions: Sessions, tmp_path: Path) -> None:
    """Leak test (task 2.6): only the encrypted `secrets` row knows the key."""
    respx.post(CHAT).mock(side_effect=openai_brain)
    run_id = await new_run(sessions, routed())

    await run_job(sessions, tmp_path, run_id)

    async with sessions() as session:
        tables = list(
            await session.scalars(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            )
        )
        for table in tables:
            query = f"SELECT string_agg(t::text, ' ') FROM \"{table}\" t"
            dump = await session.scalar(text(query))
            assert KEY not in (dump or ""), table
    assert "events" in tables and "secrets" in tables
