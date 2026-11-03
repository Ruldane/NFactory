"""Overview metrics of spec §14.1 (task 5.1): each figure is a query over runs, events and
approvals, scoped to the caller's workspace and to the chosen filters."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient

from nfactory_core.models import Approval, EventRecord, Project, Run, Workspace
from nfactory_core.models.identity import User

pytestmark = pytest.mark.integration

NOW = datetime.now(UTC)


def call(provider: str, model: str, agent: str, duration: float, cost: float | None) -> dict:
    return {
        "agent": agent,
        "provider": provider,
        "model": model,
        "input_tokens": 100,
        "output_tokens": 20,
        "duration_s": duration,
        "cost_usd": cost,
    }


@pytest.fixture
async def factory(client: AsyncClient) -> AsyncClient:
    sessions = client._transport.app.state.database.sessions  # type: ignore[attr-defined]
    events: list[tuple[str, str, dict[str, Any]]] = []
    async with sessions() as session:
        session.add(User(id="usr_other", local_identity="other", display_name="Autre"))
        session.add(Workspace(id="wks_other", name="Autre", owner_id="usr_other"))
        await session.flush()
        session.add_all(
            [
                Project(id="proj_api", workspace_id="wks_local", title="API", type="api"),
                Project(id="proj_xls", workspace_id="wks_local", title="Excel", type="excel"),
                Project(id="proj_far", workspace_id="wks_other", title="Ailleurs", type="api"),
            ]
        )
        await session.flush()

        def run(run_id: str, project: str, state: str, cost: float | None, age_days: int = 0):
            created = NOW - timedelta(days=age_days, minutes=10)
            session.add(
                Run(
                    id=run_id,
                    project_id=project,
                    request="r",
                    state=state,
                    cost_estimate_usd=cost,
                    created_at=created,
                    started_at=created,
                    finished_at=created + timedelta(minutes=2),
                )
            )

        run("run_first", "proj_api", "COMPLETED", 0.10)
        run("run_repaired", "proj_api", "COMPLETED", 0.30)
        run("run_failed", "proj_xls", "FAILED", None)
        run("run_old", "proj_api", "COMPLETED", 1.00, age_days=40)
        run("run_far", "proj_far", "COMPLETED", 5.00)
        await session.flush()

        events += [
            ("run_first", "agent.progress", call("anthropic", "m1", "requirements", 1.0, 0.05)),
            ("run_first", "agent.progress", call("anthropic", "m1", "coder", 3.0, 0.05)),
            ("run_first", "security.scanned", {"files": 4, "findings": 1}),
            ("run_first", "test.passed", {"passed": 3}),
            ("run_repaired", "test.failed", {"failed": 1}),
            ("run_repaired", "repair.started", {"attempt": 1}),
            ("run_repaired", "agent.progress", call("anthropic", "m1", "debugger", 2.0, None)),
            ("run_repaired", "repair.applied", {"attempt": 1}),
            ("run_repaired", "test.passed", {"passed": 3}),
            ("run_failed", "security.scanned", {"files": 2, "findings": 2}),
            ("run_failed", "test.failed", {"failed": 2}),
            ("run_failed", "repair.started", {"attempt": 1}),
            (
                "run_failed",
                "provider.failed",
                {"role": "coder", "provider": "openai", "model": "m2"},
            ),
            ("run_failed", "repair.abandoned", {}),
            ("run_old", "agent.progress", call("anthropic", "m1", "coder", 9.0, 1.0)),
            ("run_far", "agent.progress", call("anthropic", "m1", "coder", 9.0, 5.0)),
            ("run_far", "test.passed", {}),
        ]
        for n, (run_id, kind, payload) in enumerate(events):
            session.add(
                EventRecord(id=f"evt_m{n}", run_id=run_id, type=kind, payload_redacted=payload)
            )
        session.add(
            Approval(run_id="run_failed", action_type="plan", summary="s", status="approved")
        )
        session.add(Approval(run_id="run_far", action_type="plan", summary="s", status="approved"))
        await session.commit()
    return client


async def summary(http: AsyncClient, **params: Any) -> dict[str, Any]:
    response = await http.get("/api/v1/dashboard/summary", params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def test_the_factory_metrics_are_computed_from_runs_and_events(factory: AsyncClient) -> None:
    data = await summary(factory, days=30)

    assert data["filters"] == {"days": 30, "project_type": None}
    assert data["runs"]["total"] == 3  # the 40-day-old run and the other workspace are out
    metrics = data["metrics"]
    assert metrics["end_to_end_delivery_rate"] == pytest.approx(2 / 3)
    assert metrics["first_pass_test_rate"] == pytest.approx(1 / 3)
    assert metrics["repair_success_rate"] == pytest.approx(1 / 2)
    assert metrics["human_intervention_count"] == 1
    assert metrics["cost_per_successful_delivery"] == pytest.approx(0.40 / 2)
    assert metrics["critical_policy_violation_count"] == 1  # a delivered run with a finding
    # Nothing records these moments yet: unknown, never a fake zero.
    assert metrics["time_to_preview_seconds"] is None
    assert metrics["time_to_draft_pr_seconds"] is None


async def test_provider_and_agent_metrics_come_from_the_call_events(factory: AsyncClient) -> None:
    data = await summary(factory, days=30)

    providers = {(p["provider"], p["model"]): p for p in data["providers"]}
    claude = providers[("anthropic", "m1")]
    assert claude["calls"] == 3 and claude["failures"] == 0
    assert claude["latency_p50_s"] == pytest.approx(2.0)
    assert claude["latency_p95_s"] == pytest.approx(2.9)
    assert claude["input_tokens"] == 300 and claude["output_tokens"] == 60
    assert claude["cost_usd"] == pytest.approx(0.10)
    assert claude["cost_complete"] is False  # one call had no known price
    other = providers[("openai", "m2")]
    assert other["calls"] == 0 and other["failures"] == 1 and other["latency_p50_s"] is None

    agents = {a["agent"]: a for a in data["agents"]}
    assert agents["coder"]["calls"] == 1 and agents["coder"]["failures"] == 1
    assert agents["debugger"]["calls"] == 1


async def test_the_project_type_filter_applies_to_every_figure(factory: AsyncClient) -> None:
    data = await summary(factory, project_type="excel")

    assert data["runs"]["total"] == 1
    assert data["metrics"]["end_to_end_delivery_rate"] == 0.0
    assert data["metrics"]["repair_success_rate"] == 0.0
    assert data["metrics"]["cost_per_successful_delivery"] is None  # no delivery
    assert [(p["provider"], p["failures"]) for p in data["providers"]] == [("openai", 1)]
    assert [r["id"] for r in data["recent_runs"]] == ["run_failed"]


async def test_an_empty_factory_measures_nothing(client: AsyncClient) -> None:
    data = await summary(client)

    assert data["filters"] == {"days": None, "project_type": None}
    assert all(value in (None, 0) for value in data["metrics"].values()), data["metrics"]
    assert data["metrics"]["end_to_end_delivery_rate"] is None
    assert data["providers"] == [] and data["agents"] == []


@pytest.mark.parametrize("params", [{"days": 0}, {"days": 400}, {"project_type": "../x"}])
async def test_invalid_filters_are_refused(client: AsyncClient, params: dict[str, Any]) -> None:
    response = await client.get("/api/v1/dashboard/summary", params=params)

    assert response.status_code == 422


async def test_values_that_are_not_numbers_are_left_out(client: AsyncClient) -> None:
    # Events recorded before the redaction fix of task 4.3 hold "***REDACTED***" tokens.
    sessions = client._transport.app.state.database.sessions  # type: ignore[attr-defined]
    async with sessions() as session:
        session.add(Project(id="proj_old", workspace_id="wks_local", title="Vieux", type="api"))
        await session.flush()
        session.add(Run(id="run_redacted", project_id="proj_old", request="r", state="COMPLETED"))
        await session.flush()
        broken = call("anthropic", "m1", "coder", 1.5, None) | {
            "input_tokens": "***REDACTED***",
            "output_tokens": "***REDACTED***",
        }
        session.add(
            EventRecord(
                id="evt_red", run_id="run_redacted", type="agent.progress", payload_redacted=broken
            )
        )
        session.add(
            EventRecord(
                id="evt_scan",
                run_id="run_redacted",
                type="security.scanned",
                payload_redacted={"findings": "x"},
            )
        )
        await session.commit()

    data = await summary(client)

    [row] = data["providers"]
    assert row["calls"] == 1 and row["latency_p50_s"] == pytest.approx(1.5)
    assert row["input_tokens"] is None and row["output_tokens"] is None  # unknown, not 0
    assert data["metrics"]["critical_policy_violation_count"] == 0
