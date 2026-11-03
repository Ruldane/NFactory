"""The checks step scans for secrets (A10): a finding fails the step, goes through the
repair loop like any failed check, and its value never leaves the workspace."""

import json
from typing import Any

from nfactory_worker.agents import LLM
from nfactory_worker.agents.base import read_input
from nfactory_worker.agents.demo import respond
from nfactory_worker.brief import Brief
from nfactory_worker.pipeline import execute_run
from nfactory_worker.providers.fake import FakeProvider
from nfactory_worker.recipes import Check, Recipe, RenderedProject
from nfactory_worker.recipes.checks import pytest_check

LEAKED = "AKIA" + "R" * 16
CLEAN = "import os\n\nKEY = os.environ.get('CLOUD_KEY', '')\n"


class LeakyRecipe:
    kind = "leaky"
    version = "1"

    def render(self, brief: Brief) -> RenderedProject:
        files: dict[str, str | bytes] = {
            "pyproject.toml": '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n',
            "app/config.py": f"KEY = '{LEAKED}'\n",
            "tests/test_ok.py": "def test_ok():\n    assert True\n",
        }
        checks: tuple[Check, ...] = (pytest_check(),)
        return RenderedProject(files=files, checks=checks)


def recipes(_kind: str) -> Recipe:
    return LeakyRecipe()


def scripted(seen: list[dict[str, Any]], patches: list[dict[str, str]]) -> LLM:
    def responder(messages: list[dict[str, Any]]) -> str | None:
        agent, payload = read_input(messages)
        if agent == "debugger":
            seen.append(payload)
            return json.dumps({"cause": "secret", "proposed_fix": "env", "patches": patches})
        if agent == "reviewer":
            seen.append(payload)
        return respond(messages)

    return LLM(FakeProvider(responder=responder), "scripted", "m", demo=True)


async def test_a_planted_secret_is_found_then_repaired(harness) -> None:
    seen: list[dict[str, Any]] = []
    llm = scripted(seen, [{"path": "app/config.py", "content": CLEAN}])

    result = await execute_run(
        harness.deps(llm=llm, recipes=recipes), harness.input("api", "leaky", "x")
    )

    assert result.outcome == "COMPLETED", result.error
    debugger_input, reviewer_input = seen
    assert "app/config.py:1" in json.dumps(debugger_input["failures"])
    assert LEAKED not in json.dumps(harness.reporter.events)
    assert LEAKED not in json.dumps(debugger_input)
    checks = harness.reporter.outputs["checks"]["checks"]
    assert checks[0]["name"] == "Recherche de secrets" and checks[0]["ok"] is True
    assert reviewer_input["security"] == {"secrets": 0}
    assert [r["step"] for r in reviewer_input["repairs"]] == ["checks"]


async def test_an_unrepaired_secret_fails_the_run_without_showing_it(harness) -> None:
    result = await execute_run(harness.deps(recipes=recipes), harness.input("api", "leaky", "x"))

    assert result.outcome == "FAILED"
    assert "clé d'accès AWS" in (result.error or "")
    assert LEAKED not in (result.error or "")
    assert "tests" not in harness.reporter.started  # nothing runs on top of a leak
