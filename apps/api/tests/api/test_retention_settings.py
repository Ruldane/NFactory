"""Retention settings (ADR-0015): kept forever by default, durations the owner chooses."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def test_by_default_everything_is_kept(client: AsyncClient) -> None:
    body = (await client.get("/api/v1/settings")).json()

    assert body["retention"] == {"runs_days": None, "audit_days": None}
    assert body["retention_bounds"] == {
        "runs_days": {"min": 7, "max": 3650},
        "audit_days": {"min": 30, "max": 3650},
    }


async def test_chosen_durations_are_kept_and_audited(client: AsyncClient) -> None:
    policy = {"runs_days": 90, "audit_days": 365}

    saved = await client.put("/api/v1/settings/retention", json=policy)

    assert saved.status_code == 200
    assert saved.json()["retention"] == policy
    body = (await client.get("/api/v1/settings")).json()
    assert body["retention"] == policy
    assert body["run_limits"]["max_llm_calls"] == 80  # the other settings are untouched
    entry = (await client.get("/api/v1/audit")).json()["items"][0]
    assert (entry["action"], entry["details"]) == ("settings.retention", policy)


async def test_keep_forever_again_with_null(client: AsyncClient) -> None:
    await client.put("/api/v1/settings/retention", json={"runs_days": 30, "audit_days": None})

    saved = await client.put("/api/v1/settings/retention", json={"runs_days": None})

    assert saved.json()["retention"] == {"runs_days": None, "audit_days": None}


@pytest.mark.parametrize("policy", [{"runs_days": 3}, {"audit_days": 4000}, {"days": 30}])
async def test_out_of_bounds_durations_are_refused(
    client: AsyncClient, policy: dict[str, int]
) -> None:
    response = await client.put("/api/v1/settings/retention", json=policy)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
