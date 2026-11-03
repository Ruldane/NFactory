import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def test_health_is_ok_and_reveals_nothing_sensitive(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_reports_each_dependency(client: AsyncClient) -> None:
    # The test app points at an unreachable Redis on purpose.
    response = await client.get("/api/v1/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["database"]["ok"] is True
    assert body["checks"]["pgvector"]["ok"] is True
    assert body["checks"]["redis"]["ok"] is False


async def test_unknown_route_returns_structured_error(client: AsyncClient) -> None:
    response = await client.get("/api/v1/nope")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
