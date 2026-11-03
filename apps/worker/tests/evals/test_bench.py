"""Provider comparison (task 5.5, spec F35): the same eval cases on several engines, side
by side, with figures that say where they come from. A real engine is only one the user
connected and tested in Moteurs IA; the bench opens it like a run does."""

import json
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.services.identity import LOCAL_WORKSPACE_ID, ensure_local_identity
from nfactory_core.config import Settings
from nfactory_core.models import ModelCatalogEntry, ProviderConnection
from nfactory_core.secrets import SecretStore
from nfactory_worker.agents.demo import respond
from nfactory_worker.evals.bench import build_comparison, render_comparison_html
from nfactory_worker.evals.cases import Case, Expect
from nfactory_worker.evals.checks import score
from nfactory_worker.evals.engines import EngineError, open_engine, parse_engine
from nfactory_worker.evals.run import EvalEnv, run_case
from nfactory_worker.runner import LocalRunner

MASTER = "bench-tests-master-key-0123456789abcdef"
KEY = "sk-bench-test-0123456789abcdefghijklmn"
CHAT = "https://api.openai.com/v1/chat/completions"

Sessions = async_sessionmaker[AsyncSession]


def test_an_engine_is_demo_or_a_provider_and_a_model() -> None:
    assert parse_engine("demo").label == "demo"
    spec = parse_engine("openai_api:gpt-test")
    assert (spec.provider, spec.model, spec.label) == (
        "openai_api",
        "gpt-test",
        "openai_api:gpt-test",
    )
    for bad in ("openai_api", "openai_api:", "nope:model", "codex_local:gpt"):
        with pytest.raises(EngineError):
            parse_engine(bad)


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
        session.add(
            ModelCatalogEntry(
                provider_kind="openai_api",
                model_id="gpt-test",
                capabilities={"pricing": {"input_per_mtok": 1.0, "output_per_mtok": 2.0}},
            )
        )
        await session.commit()
    yield factory
    await engine.dispose()


def settings() -> Settings:
    return Settings(nfactory_secret_key=MASTER, nfactory_demo_mode=False)  # type: ignore[arg-type]


@pytest.mark.integration
async def test_an_engine_not_connected_is_refused(sessions: Sessions) -> None:
    async with sessions() as session:
        with pytest.raises(EngineError, match="n'est pas connecté"):
            await open_engine(
                parse_engine("anthropic_api:m"), session, LOCAL_WORKSPACE_ID, settings()
            )


def openai_brain(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    return httpx.Response(
        200,
        json={
            "model": body["model"],
            "choices": [
                {"message": {"content": respond(body["messages"])}, "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 500},
        },
    )


CASE = Case(
    id="excel-depenses",
    suite="excel",
    project_type="excel",
    request="Un classeur Excel de suivi des dépenses, avec catégorie, montant et date.",
    title="Dépenses",
    tags=(),
    parent_request=None,
    knowledge=(),
    expect=Expect(min_tests=7),
)


@pytest.mark.integration
@respx.mock
async def test_a_connected_engine_runs_the_case_and_its_cost_is_measured(
    sessions: Sessions, tmp_path: Path
) -> None:
    chat = respx.post(CHAT).mock(side_effect=openai_brain)
    async with sessions() as session:
        engines = await open_engine(
            parse_engine("openai_api:gpt-test"), session, LOCAL_WORKSPACE_ID, settings()
        )
    assert engines.fallback == "none"  # a bench never waits for a human decision
    env = EvalEnv(
        base=tmp_path,
        runner=LocalRunner(tmp_path / "workspaces", python=sys.executable),
        engines=engines,
    )

    run = await run_case(CASE, env)

    assert run.outcome == "COMPLETED", run.error
    assert all(c.ok for c in score(run)), [c for c in score(run) if not c.ok]
    metrics = run.metrics()
    assert chat.call_count == metrics["llm_calls"] > 0
    assert metrics["input_tokens"] == 1000 * metrics["llm_calls"]
    assert metrics["output_tokens"] == 500 * metrics["llm_calls"]
    # 1 $ per million input tokens, 2 $ per million output tokens.
    assert metrics["cost_usd"] == pytest.approx(metrics["llm_calls"] * (0.001 + 0.001))


def report(
    label: str, provider: str, cases: list[dict[str, Any]], cost: float | None
) -> dict[str, Any]:
    return {
        "engine": {"label": label, "provider": provider, "model": "m", "demo": provider == "fake"},
        "totals": {"cases": len(cases)},
        "figures": {
            "pass_rate": {"value": 0.5, "source": "s"},
            "latency_p50_s": {"value": 1.0, "source": "s"},
            "latency_p95_s": {"value": 2.0, "source": "s"},
            "cost_usd": {"value": cost, "source": "s"},
            "llm_calls": {"value": 4, "source": "s"},
            "security_findings": {"value": 0, "source": "s"},
        },
        "cases": cases,
    }


def case(case_id: str, status: str, tokens: int | None = 10) -> dict[str, Any]:
    return {
        "id": case_id,
        "status": status,
        "metrics": {"input_tokens": tokens, "output_tokens": tokens, "duration_s": 1.0},
    }


def test_the_comparison_lines_engines_up_without_inventing_figures() -> None:
    demo = report("demo", "fake", [case("a", "passed"), case("b", "failed")], 0.0)
    real = report("openai_api:m", "openai_api", [case("a", "passed", None)], None)

    comparison = build_comparison([demo, real], meta={"version": "abc"})

    rows = {row["engine"]: row for row in comparison["engines"]}
    assert rows["demo"]["demo"] is True and rows["openai_api:m"]["demo"] is False
    assert rows["demo"]["cost_usd"] == 0.0
    assert rows["openai_api:m"]["cost_usd"] is None  # no price known: not 0
    assert rows["demo"]["input_tokens"] == 20
    assert rows["openai_api:m"]["input_tokens"] is None  # a call without usage
    assert comparison["matrix"] == [
        {"case": "a", "results": {"demo": "passed", "openai_api:m": "passed"}},
        {"case": "b", "results": {"demo": "failed", "openai_api:m": None}},
    ]
    assert set(comparison["sources"]) >= {"cost_usd", "input_tokens", "pass_rate"}
    page = render_comparison_html(comparison)
    assert "openai_api:m" in page and "Non mesuré" in page and "moteur démo" in page
