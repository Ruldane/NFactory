import pytest
from httpx import AsyncClient

from nfactory_core.pipeline import step_names

pytestmark = pytest.mark.integration


async def test_summary_on_empty_factory(client: AsyncClient) -> None:
    summary = (await client.get("/api/v1/dashboard/summary")).json()

    assert summary["demo_data"] is False
    assert summary["projects"] == 0
    assert summary["runs"]["total"] == 0
    # No finished run yet: rates are unknown, not 0 %.
    assert summary["success_rate"] is None
    assert summary["avg_duration_seconds"] is None


async def test_summary_reflects_demo_database(demo_client: AsyncClient) -> None:
    summary = (await demo_client.get("/api/v1/dashboard/summary")).json()

    assert summary["demo_data"] is True
    assert summary["projects"] == 4
    assert summary["runs"] == {
        "total": 4,
        "active": 1,
        "completed": 2,
        "partial": 0,
        "failed": 1,
        "cancelled": 0,
    }
    # 2 completed out of 3 finished runs.
    assert summary["success_rate"] == pytest.approx(2 / 3)
    assert summary["approvals_pending"] == 1
    assert summary["cost_estimate_usd"] == pytest.approx(0.42 + 0.11 + 0.18)
    assert len(summary["recent_runs"]) == 4
    assert summary["recent_runs"][0]["project_title"]


async def test_recent_runs_carry_their_ordered_steps(demo_client: AsyncClient) -> None:
    # The overview draws each run as a conveyor of stations, from real step data.
    summary = (await demo_client.get("/api/v1/dashboard/summary")).json()
    failed = next(r for r in summary["recent_runs"] if r["state"] == "FAILED")

    names = [s["name"] for s in failed["steps"]]
    assert names == list(step_names())
    tests_at = names.index("tests")
    assert [s["state"] for s in failed["steps"]][tests_at:] == [
        "FAILED",
        "SKIPPED",
        "SKIPPED",
        "SKIPPED",
    ]
