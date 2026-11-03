import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

NEW_PROJECT = {"title": "API de stock", "type": "api", "description": "CRUD des articles"}


async def test_create_then_get_project(client: AsyncClient) -> None:
    created = await client.post("/api/v1/projects", json=NEW_PROJECT)

    assert created.status_code == 201
    project = created.json()
    assert project["id"].startswith("proj_")
    assert project["is_demo"] is False

    fetched = await client.get(f"/api/v1/projects/{project['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "API de stock"


async def test_create_rejects_unknown_type(client: AsyncClient) -> None:
    response = await client.post("/api/v1/projects", json={**NEW_PROJECT, "type": "rocket"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_list_is_paginated_and_filterable(demo_client: AsyncClient) -> None:
    page = (await demo_client.get("/api/v1/projects", params={"limit": 2})).json()
    assert page["total"] >= 4
    assert len(page["items"]) == 2

    excel = (await demo_client.get("/api/v1/projects", params={"type": "excel"})).json()
    assert excel["items"]
    assert {p["type"] for p in excel["items"]} == {"excel"}


async def test_project_detail_includes_latest_run(demo_client: AsyncClient) -> None:
    response = await demo_client.get("/api/v1/projects/proj_demo_kpi")

    latest = response.json()["latest_run"]
    assert latest["state"] == "FAILED"
    assert latest["error"]


async def test_patch_updates_only_allowed_fields(client: AsyncClient) -> None:
    project = (await client.post("/api/v1/projects", json=NEW_PROJECT)).json()

    ok = await client.patch(f"/api/v1/projects/{project['id']}", json={"title": "Stock v2"})
    assert ok.status_code == 200
    assert ok.json()["title"] == "Stock v2"

    forbidden = await client.patch(f"/api/v1/projects/{project['id']}", json={"is_demo": True})
    assert forbidden.status_code == 422


async def test_project_outside_my_workspaces_is_not_found(client: AsyncClient) -> None:
    # Unknown or foreign IDs look the same: no information leak.
    response = await client.get("/api/v1/projects/proj_belongs_to_someone_else")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
