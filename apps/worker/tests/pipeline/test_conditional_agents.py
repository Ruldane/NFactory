"""Conditional agents (spec §5): a run calls only the models its project type needs."""

import shutil
from pathlib import Path

import pytest

from nfactory_worker.pipeline import execute_run

# The frontend toolchain installed locally (npm ci in apps/sandbox/web-deps).
WEB_DEPS = Path(__file__).resolve().parents[3] / "sandbox" / "web-deps" / "node_modules"
HAS_WEB_TOOLS = bool(shutil.which("node")) and WEB_DEPS.is_dir()


def _agents_called(harness) -> list[str]:  # type: ignore[no-untyped-def]
    return [payload["agent"] for payload in harness.events("agent.progress")]


async def test_an_excel_run_does_not_call_the_architect(harness) -> None:  # type: ignore[no-untyped-def]
    result = await execute_run(
        harness.deps(), harness.input("excel", "excel-automation", "Rapport KPI hebdo")
    )

    assert result.outcome == "COMPLETED"
    assert "architect" not in _agents_called(harness)
    assert "architect" not in harness.reporter.started
    assert "architect" in harness.reporter.skipped


async def test_an_api_run_calls_the_architect(harness) -> None:  # type: ignore[no-untyped-def]
    result = await execute_run(
        harness.deps(), harness.input("api", "python-api", "API pour l'inventaire du matériel")
    )

    assert result.outcome == "COMPLETED"
    assert "architect" in _agents_called(harness)
    assert harness.reporter.skipped == {}


@pytest.mark.skipif(not HAS_WEB_TOOLS, reason="node ou apps/sandbox/web-deps/node_modules absent")
async def test_a_webapp_run_reports_backend_and_frontend_tests_together(
    harness,
    monkeypatch,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("NFACTORY_WEB_DEPS", str(WEB_DEPS))

    result = await execute_run(
        harness.deps(),
        harness.input("webapp", "webapp-react-fastapi", "Gestion des licences IT"),
    )

    assert result.outcome == "COMPLETED", result.error
    assert "architect" in _agents_called(harness)
    report = harness.reporter.outputs["tests"]["report"]
    assert report["passed"] >= 14 and report["failed"] == 0  # pytest + vitest, added up
    preview = harness.reporter.outputs["package"]["preview"]
    assert preview == {"argv": ["python", "tools/preview.py"], "port": 8000}
