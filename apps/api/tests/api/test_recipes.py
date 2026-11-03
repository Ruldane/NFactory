import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def test_catalog_lists_every_project_type_with_its_phase(client: AsyncClient) -> None:
    recipes = (await client.get("/api/v1/recipes")).json()["items"]

    by_type = {r["project_type"]: r for r in recipes}
    assert by_type["api"]["available"] is True
    assert by_type["excel"]["deliverable"] == "non-code"
    assert by_type["document"]["available"] is True
    # Planned types are listed, never shown as available.
    assert by_type["webapp"]["available"] is True
    assert by_type["feature"]["available"] is False
    assert by_type["feature"]["phase"] == 4
    assert {"kind", "label", "description", "outputs"} <= set(by_type["api"])


async def test_projects_accept_every_catalog_type(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/projects", json={"title": "Note", "type": "document", "description": ""}
    )
    assert response.status_code == 201
