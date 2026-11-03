"""The repair loop: patches are applied and re-tested, attempts are bounded, and no
failure is ever turned into a fake success."""

import json
from typing import Any

from nfactory_worker.agents import LLM
from nfactory_worker.agents.base import read_input
from nfactory_worker.agents.demo import respond
from nfactory_worker.brief import Brief
from nfactory_worker.providers.fake import FakeProvider
from nfactory_worker.recipes import Check, Recipe, RenderedProject
from nfactory_worker.recipes.checks import pytest_check

BROKEN_TEST = "def test_math():\n    assert 1 + 1 == 3\n"
FIXED_TEST = "def test_math():\n    assert 1 + 1 == 2\n"


class BrokenRecipe:
    kind = "broken"
    version = "1"

    def render(self, brief: Brief) -> RenderedProject:
        files: dict[str, str | bytes] = {
            "pyproject.toml": '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n',
            "tests/test_math.py": BROKEN_TEST,
        }
        checks: tuple[Check, ...] = (pytest_check(),)
        return RenderedProject(files=files, checks=checks)


def recipes(_kind: str) -> Recipe:
    return BrokenRecipe()


def llm_with_debugger(patches: list[dict[str, str]]) -> LLM:
    def responder(messages: list[dict[str, Any]]) -> str | None:
        agent, _payload = read_input(messages)
        if agent == "debugger":
            return json.dumps({"cause": "maths", "proposed_fix": "fix", "patches": patches})
        return respond(messages)

    return LLM(FakeProvider(responder=responder), "scripted", "m", demo=True)


async def test_demo_debugger_without_patch_fails_the_run_at_once(harness) -> None:
    result = await execute(harness, harness.deps(recipes=recipes))
    assert result.outcome == "FAILED"
    assert len(harness.events("repair.started")) == 1
    assert "review" not in harness.reporter.started


async def test_a_good_patch_is_applied_and_the_tests_rerun(harness) -> None:
    llm = llm_with_debugger([{"path": "tests/test_math.py", "content": FIXED_TEST}])
    result = await execute(harness, harness.deps(llm=llm, recipes=recipes))
    assert result.outcome == "COMPLETED"
    assert harness.reporter.attempts["tests"] == 2


async def test_repairs_stop_after_the_maximum(harness) -> None:
    llm = llm_with_debugger([{"path": "tests/test_math.py", "content": BROKEN_TEST}])
    result = await execute(harness, harness.deps(llm=llm, recipes=recipes, max_repairs=3))
    assert result.outcome == "FAILED"
    assert len(harness.events("repair.started")) == 3
    assert harness.reporter.attempts["tests"] == 4  # first run + 3 repairs


async def test_patch_outside_the_workspace_is_refused(harness) -> None:
    llm = llm_with_debugger([{"path": "../escape.py", "content": "x"}])
    result = await execute(harness, harness.deps(llm=llm, recipes=recipes))
    assert result.outcome == "FAILED"
    assert not (harness.base / "workspaces" / "escape.py").exists()
    assert "Unsafe path" in (result.error or "")


async def test_each_repair_is_traced_for_the_timeline(harness) -> None:
    llm = llm_with_debugger([{"path": "tests/test_math.py", "content": FIXED_TEST}])
    result = await execute(harness, harness.deps(llm=llm, recipes=recipes))

    assert result.outcome == "COMPLETED"
    (applied,) = harness.events("repair.applied")
    assert applied | {"failure": ""} == {
        "attempt": 1,
        "step": "tests",
        "cause": "maths",
        "files": ["tests/test_math.py"],
        "failure": "",
    }
    assert "test_math" in applied["failure"]
    (trace,) = harness.reporter.outputs["tests"]["repairs"]
    assert (trace["attempt"], trace["files"], trace["cause"]) == (
        1,
        ["tests/test_math.py"],
        "maths",
    )


async def test_a_run_that_gives_up_keeps_its_repair_history(harness) -> None:
    llm = llm_with_debugger([{"path": "tests/test_math.py", "content": BROKEN_TEST}])
    result = await execute(harness, harness.deps(llm=llm, recipes=recipes, max_repairs=2))

    assert result.outcome == "FAILED"
    assert [e["attempt"] for e in harness.events("repair.applied")] == [1, 2]
    (abandoned,) = harness.events("repair.abandoned")
    assert abandoned["attempt"] == 3 and abandoned["step"] == "tests"
    assert [r["attempt"] for r in harness.reporter.failed_outputs["tests"]["repairs"]] == [1, 2]


async def execute(harness, deps):  # type: ignore[no-untyped-def]
    from nfactory_worker.pipeline import execute_run

    return await execute_run(deps, harness.input("api", "broken", "x"))
