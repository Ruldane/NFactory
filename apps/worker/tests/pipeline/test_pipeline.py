"""End-to-end pipeline behaviour, demo mode, real recipes and real commands."""

import io
import sys
import zipfile
from pathlib import Path

import pytest

from nfactory_core.pipeline import step_names
from nfactory_worker.brief import Brief
from nfactory_worker.pipeline import execute_run
from nfactory_worker.recipes import Check, RenderedProject
from nfactory_worker.runner import LocalRunner, parse_junit


async def test_api_run_completes_every_step_in_order(harness) -> None:
    result = await execute_run(
        harness.deps(), harness.input("api", "python-api", "API pour l'inventaire du matériel")
    )

    assert result.outcome == "COMPLETED"
    assert harness.reporter.finished_steps() == list(step_names())
    tests = harness.reporter.outputs["tests"]
    assert tests["report"]["passed"] >= 8 and tests["report"]["failed"] == 0
    assert "EXPLICATION.md" in harness.reporter.outputs["package"]["files"]
    assert "preview" not in harness.reporter.outputs["package"]  # nothing to preview
    assert harness.events("test.passed")


@pytest.mark.parametrize(
    ("project_type", "recipe", "request_text", "extension"),
    [
        ("excel", "excel-automation", "Rapport KPI hebdo depuis deux CSV", ".xlsx"),
        ("document", "document", "Procédure de sauvegarde du NAS", ".docx"),
    ],
)
async def test_non_code_runs_deliver_their_file(
    harness, project_type: str, recipe: str, request_text: str, extension: str
) -> None:
    result = await execute_run(harness.deps(), harness.input(project_type, recipe, request_text))

    assert result.outcome == "COMPLETED"
    names = [artifact.filename for artifact in harness.reporter.artifacts]
    assert any(name.endswith(extension) for name in names)
    assert any(name.endswith(".zip") for name in names)


async def test_zip_is_reproducible_and_its_tests_pass_outside_nfactory(
    harness, tmp_path: Path
) -> None:
    await execute_run(harness.deps(), harness.input("api", "python-api", "API des licences"))
    zip_artifact = next(a for a in harness.reporter.artifacts if a.filename.endswith(".zip"))
    data = Path(zip_artifact.path).read_bytes()  # noqa: ASYNC240 - test setup

    # Packaging the same workspace again yields identical bytes.
    second = type(harness)(tmp_path / "again")
    await execute_run(second.deps(), harness.input("api", "python-api", "API des licences"))
    again = next(a for a in second.reporter.artifacts if a.filename.endswith(".zip"))
    assert again.checksum == zip_artifact.checksum

    target = tmp_path / "unzipped" / "run_x"
    zipfile.ZipFile(io.BytesIO(data)).extractall(target)
    runner = LocalRunner(target.parent, python=sys.executable)
    junit = ".nfactory/junit.xml"
    result = await runner.run(
        "run_x",
        ("python", "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={junit}"),
        300,
    )
    assert result.ok, result.stdout
    assert parse_junit((target / junit).read_text(encoding="utf-8")).ok


async def test_cancellation_stops_before_the_next_step(harness) -> None:
    harness.control.cancel_after("requirements")
    result = await execute_run(harness.deps(), harness.input("api", "python-api", "API"))

    assert result.outcome == "CANCELLED"
    assert harness.reporter.finished_steps() == ["requirements"]
    assert "plan" not in harness.reporter.started


async def test_unavailable_recipe_fails_cleanly(harness) -> None:
    result = await execute_run(harness.deps(), harness.input("api", "cli-tool", "Outil CLI"))
    assert result.outcome == "FAILED"
    assert "cli-tool" in (result.error or "")


class _TwoSuites:
    """A project tested by two checks, each writing its own JUnit report."""

    kind = "two-suites"
    version = "0.0.1"

    def render(self, brief: Brief) -> RenderedProject:
        def suite(name: str, count: int) -> tuple[str, str, Check]:
            body = "".join(f"def test_{i}():\n    assert True\n\n" for i in range(count))
            junit = f".nfactory/junit-{name}.xml"
            argv = ("python", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                    f"--junitxml={junit}", f"{name}/test_{name}.py")  # fmt: skip
            return f"{name}/test_{name}.py", body, Check(name, "tests", argv, 120, junit)

        first, second = suite("one", 2), suite("two", 3)
        return RenderedProject(
            files={first[0]: first[1], second[0]: second[1]}, checks=(first[2], second[2])
        )


async def test_reports_of_several_test_checks_add_up(harness) -> None:
    recipe = _TwoSuites()
    result = await execute_run(
        harness.deps(recipes=lambda _kind: recipe), harness.input("api", recipe.kind, "API")
    )

    assert result.outcome == "COMPLETED", result.error
    report = harness.reporter.outputs["tests"]["report"]
    assert (report["passed"], report["total"], report["ok"]) == (5, 5, True)
