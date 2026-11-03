"""The webapp-react-fastapi recipe: FastAPI backend + React frontend, both really tested
(spec §12.1, scenario A)."""

import asyncio
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from openpyxl import load_workbook

from nfactory_worker.brief import Brief, EntitySpec, FieldSpec
from nfactory_worker.recipes import Preview
from nfactory_worker.recipes.webapp_react_fastapi import FRONTEND_VERSIONS, WebappRecipe

LICENCES = Brief(
    title="Gestionnaire de licences IT",
    summary="Suivre les licences logicielles et leurs dates d'expiration.",
    project_type="webapp",
    entity=EntitySpec(
        name="licence",
        plural="licences",
        label="Licence",
        fields=[
            FieldSpec(name="logiciel", label="Logiciel", type="str"),
            FieldSpec(name="postes", label="Postes", type="int"),
            FieldSpec(name="cout_annuel", label="Coût annuel", type="float"),
            FieldSpec(name="expire_le", label="Expire le", type="date"),
            FieldSpec(name="active", label="Active", type="bool"),
        ],
    ),
)
WEB_DEPS = Path(__file__).resolve().parents[3] / "sandbox" / "web-deps" / "package.json"


def test_render_ships_backend_frontend_and_delivery_files() -> None:
    files = WebappRecipe().render(LICENCES).files

    assert {
        "README.md",
        ".env.example",
        "compose.yaml",
        "backend/Dockerfile",
        "backend/app/main.py",
        "backend/tests/test_licences.py",
        "frontend/Dockerfile",
        "frontend/nginx.conf",
        "frontend/package.json",
        "frontend/index.html",
        "frontend/src/App.jsx",
        "frontend/src/App.test.jsx",
        "frontend/src/entity.json",
        "tools/link-frontend-deps.mjs",
    } <= files.keys()
    assert not any("password" in str(content).lower() for content in files.values())


def test_checks_cover_lint_build_and_both_test_suites() -> None:
    rendered = WebappRecipe().render(LICENCES)

    assert [c.stage for c in rendered.ordered_checks()] == [
        "static", "build", "build", "tests", "tests",
    ]  # fmt: skip
    junits = [c.junit_path for c in rendered.checks if c.junit_path]
    assert len(junits) == 2 and len(set(junits)) == 2


def test_frontend_pins_exactly_the_sandbox_toolchain() -> None:
    sandbox = json.loads(WEB_DEPS.read_text(encoding="utf-8"))
    files = WebappRecipe().render(LICENCES).files
    frontend = json.loads(str(files["frontend/package.json"]))

    pinned = {**sandbox["dependencies"], **sandbox["devDependencies"]}
    assert FRONTEND_VERSIONS == pinned
    assert {**frontend["dependencies"], **frontend["devDependencies"]} == pinned


def test_brief_text_reaches_the_frontend_as_data_only() -> None:
    hostile = LICENCES.model_copy(
        update={"title": '</title><script>alert("x")</script>', "summary": "`${process.exit(1)}`"}
    )
    files = WebappRecipe().render(hostile).files

    assert "<script>alert" not in str(files["frontend/index.html"])
    entity = json.loads(str(files["frontend/src/entity.json"]))
    assert entity["title"] == hostile.title
    assert all(hostile.summary not in str(content) for path, content in files.items()
               if path.endswith((".jsx", ".js", ".mjs")))  # fmt: skip


async def test_generated_app_builds_and_both_suites_pass(run_with_tools) -> None:  # type: ignore[no-untyped-def]
    execution = await run_with_tools(WebappRecipe().render(LICENCES), {"node"})

    assert execution.failures() == []
    assert execution.report is not None and execution.report.ok
    assert execution.report.passed >= 17  # backend pytest (with the export) + frontend vitest
    assert execution.workspace.resolve("frontend/dist/index.html").is_file()


def test_the_webapp_exports_its_list_to_excel() -> None:
    files = WebappRecipe().render(LICENCES).files

    assert "backend/app/export.py" in files and "backend/tests/test_export.py" in files
    assert "openpyxl" in str(files["backend/pyproject.toml"])
    main = str(files["backend/app/main.py"])
    # Before the CRUD router: else /licences/{id} would catch /licences/export.xlsx.
    assert main.index("include_router(export_router)") < main.index("include_router(router)")
    assert "Exporter en Excel" in str(files["frontend/src/App.jsx"])


def test_a_plain_api_has_no_excel_export() -> None:
    from nfactory_worker.recipes.python_api import PythonApiRecipe

    files = PythonApiRecipe().render(LICENCES).files

    assert "app/export.py" not in files
    assert "export_router" not in str(files["app/main.py"])


def test_the_webapp_declares_its_preview() -> None:
    rendered = WebappRecipe().render(LICENCES)

    assert rendered.preview == Preview(argv=("python", "tools/preview.py"), port=8000)
    # Served under /preview/<run>/: assets and API calls must be relative.
    assert 'base: "./"' in str(rendered.files["frontend/vite.config.js"])
    assert "import.meta.env.BASE_URL" in str(rendered.files["frontend/src/api.js"])


@pytest.mark.skipif(not shutil.which("node"), reason="node absent : aperçu testé dans la stack")
async def test_the_preview_serves_the_built_app_and_its_api(run_with_tools) -> None:  # type: ignore[no-untyped-def]
    execution = await run_with_tools(WebappRecipe().render(LICENCES), {"node"})
    assert execution.failures() == []
    await asyncio.to_thread(_serve_and_check, execution.workspace.root)


def _serve_and_check(root: Path) -> None:
    """Start tools/preview.py on the built workspace, then use the page and its API."""
    port = _free_port()
    env = {**os.environ, "PORT": str(port), "DATABASE_URL": f"sqlite:///{root / 'preview.db'}"}
    server = subprocess.Popen([sys.executable, "tools/preview.py"], cwd=root, env=env)
    try:
        base = f"http://127.0.0.1:{port}"
        page = _get_when_up(f"{base}/")
        assert '<div id="root">' in page and "./assets/" in page
        created = httpx.post(f"{base}/api/licences", json=_licence(), timeout=10)
        assert created.status_code == 201, created.text
        assert len(httpx.get(f"{base}/api/licences", timeout=10).json()) == 1
        exported = httpx.get(f"{base}/api/licences/export.xlsx", timeout=10)
        assert exported.status_code == 200
        sheet = load_workbook(io.BytesIO(exported.content)).active
        assert sheet is not None
        rows = list(sheet.iter_rows(values_only=True))
        assert rows[0] == ("N°", "Logiciel", "Postes", "Coût annuel", "Expire le", "Active")
        assert rows[1][1:] == ("Tableur", 3, 99.5, datetime(2027, 1, 31), "Oui")
    finally:
        server.terminate()
        server.wait(10)


def _licence() -> dict[str, object]:
    return {
        "logiciel": "Tableur",
        "postes": 3,
        "cout_annuel": 99.5,
        "expire_le": "2027-01-31",
        "active": True,
    }


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _get_when_up(url: str) -> str:
    deadline = time.monotonic() + 30
    while True:
        try:
            response = httpx.get(url, timeout=2)
            if response.status_code == 200:
                return response.text
        except httpx.HTTPError:
            if time.monotonic() > deadline:
                raise
        time.sleep(0.3)
