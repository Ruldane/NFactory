"""The trace of a run (task 5.2), rebuilt from the database: the run, its stored steps,
then each agent call and check under its step, with durations, tokens and costs."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient

from nfactory_core.models import EventRecord, Project, Run, RunStep, Workspace
from nfactory_core.models.identity import User

pytestmark = pytest.mark.integration

T0 = datetime(2026, 11, 3, 8, 0, tzinfo=UTC)
TRACE = "0123456789abcdef0123456789abcdef"


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


@pytest.fixture
async def traced(client: AsyncClient) -> AsyncClient:
    sessions = client._transport.app.state.database.sessions  # type: ignore[attr-defined]
    async with sessions() as session:
        session.add(User(id="usr_other", local_identity="other", display_name="Autre"))
        session.add(Workspace(id="wks_other", name="Autre", owner_id="usr_other"))
        await session.flush()
        session.add(Project(id="proj_t", workspace_id="wks_local", title="T", type="api"))
        session.add(Project(id="proj_o", workspace_id="wks_other", title="O", type="api"))
        await session.flush()
        session.add(
            Run(
                id="run_t",
                project_id="proj_t",
                request="r",
                state="FAILED",
                trace_id=TRACE,
                cost_estimate_usd=0.03,
                started_at=at(0),
                finished_at=at(20),
            )
        )
        session.add(Run(id="run_o", project_id="proj_o", request="r", state="COMPLETED"))
        await session.flush()
        steps = [
            ("step_plan", 0, "plan", "planner", "SUCCEEDED", at(0), at(5)),
            ("step_checks", 1, "checks", "tester", "FAILED", at(5), at(15)),
            ("step_docs", 2, "docs", "documenter", "SKIPPED", at(15), at(15)),
            ("step_pack", 3, "package", "packager", "PENDING", None, None),
        ]
        for sid, pos, name, role, state, start, end in steps:
            session.add(
                RunStep(
                    id=sid,
                    run_id="run_t",
                    position=pos,
                    name=name,
                    agent_role=role,
                    state=state,
                    attempts=1 if start else 0,
                    started_at=start,
                    ended_at=end,
                )
            )
        await session.flush()
        events: list[tuple[str, str, str, datetime, dict[str, Any]]] = [
            ("step_plan", "agent.progress", "e1", at(4), {
                "agent": "planner", "provider": "anthropic", "model": "m1",
                "input_tokens": 100, "output_tokens": 20, "duration_s": 3.0, "cost_usd": 0.02,
            }),
            ("step_checks", "agent.progress", "e2", at(8), {
                "agent": "debugger", "provider": "anthropic", "model": "m1",
                "input_tokens": "***REDACTED***", "duration_s": 1.0, "cost_usd": None,
            }),
            ("step_checks", "tool.invoked", "e3", at(14), {
                "check": "pytest", "argv": ["python", "-m", "pytest"], "exit_code": 1,
                "duration_s": 2.5, "timed_out": False,
            }),
            ("step_checks", "test.failed", "e4", at(14), {"failed": 1}),
        ]  # fmt: skip
        for step_id, kind, eid, when, payload in events:
            session.add(
                EventRecord(
                    id=f"evt_{eid}",
                    run_id="run_t",
                    step_id=step_id,
                    type=kind,
                    payload_redacted=payload,
                    created_at=when,
                )
            )
        await session.commit()
    return client


async def test_the_trace_is_the_runs_stored_steps_and_calls(traced: AsyncClient) -> None:
    response = await traced.get("/api/v1/runs/run_t/trace")

    assert response.status_code == 200
    trace = response.json()
    assert trace["trace_id"] == TRACE
    spans = {s["name"]: s for s in trace["spans"]}
    assert [s["name"] for s in trace["spans"] if s["kind"] == "step"] == [
        "plan",
        "checks",
        "docs",
        "package",
    ]
    run = spans["run"]
    assert run["parent_id"] is None and run["duration_s"] == 20.0 and run["status"] == "error"
    assert spans["plan"]["parent_id"] == run["id"] and spans["plan"]["status"] == "ok"
    assert spans["docs"]["status"] == "skipped"
    assert spans["package"]["status"] == "pending" and spans["package"]["start"] is None


async def test_calls_sit_under_their_step_with_their_measures(traced: AsyncClient) -> None:
    spans = {s["name"]: s for s in (await traced.get("/api/v1/runs/run_t/trace")).json()["spans"]}

    planner, debugger, check = spans["planner"], spans["debugger"], spans["pytest"]
    assert planner["kind"] == "agent" and planner["parent_id"] == spans["plan"]["id"]
    assert planner["start"].startswith("2026-11-03T08:00:01")  # ended at 4 s, lasted 3 s
    assert planner["duration_s"] == 3.0
    assert (planner["provider"], planner["model"]) == ("anthropic", "m1")
    assert (planner["input_tokens"], planner["output_tokens"], planner["cost_usd"]) == (
        100,
        20,
        0.02,
    )
    assert debugger["input_tokens"] is None and debugger["cost_usd"] is None  # unknown, not 0
    assert check["kind"] == "check" and check["parent_id"] == spans["checks"]["id"]
    assert check["status"] == "error" and check["exit_code"] == 1


async def test_each_step_adds_up_its_calls(traced: AsyncClient) -> None:
    spans = {s["name"]: s for s in (await traced.get("/api/v1/runs/run_t/trace")).json()["spans"]}

    assert spans["plan"]["cost_usd"] == 0.02 and spans["plan"]["calls"] == 1
    assert spans["checks"]["cost_usd"] is None  # its only call had no known price
    assert spans["checks"]["calls"] == 1


async def test_a_run_of_another_workspace_is_not_found(traced: AsyncClient) -> None:
    assert (await traced.get("/api/v1/runs/run_o/trace")).status_code == 404
    assert (await traced.get("/api/v1/runs/run_missing/trace")).status_code == 404
