"""Pipeline test harness: real recipes, real runner, in-memory reporting."""

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from nfactory_worker.agents import LLM, Engines, demo_llm
from nfactory_worker.artifacts import LocalArtifactStore
from nfactory_worker.pipeline import (
    Knowledge,
    MemoryControl,
    MemoryReporter,
    PipelineDeps,
    RunInput,
)
from nfactory_worker.recipes import Recipe, get_recipe
from nfactory_worker.runner import LocalRunner


class Harness:
    def __init__(self, base: Path) -> None:
        self.base = base
        self.reporter = MemoryReporter()
        self.control = MemoryControl(self.reporter)

    def deps(
        self,
        llm: LLM | None = None,
        engines: Engines | None = None,
        recipes: Callable[[str], Recipe] = get_recipe,
        max_repairs: int = 3,
        max_llm_calls: int = 80,
        max_steps: int = 100,
        knowledge: Knowledge | None = None,
    ) -> PipelineDeps:
        return PipelineDeps(
            engines=engines or Engines.single(llm or demo_llm()),
            retry_delay_s=0,
            runner=LocalRunner(self.base / "workspaces", python=sys.executable),
            workspace_root=self.base / "workspaces",
            artifacts=LocalArtifactStore(self.base / "artifacts"),
            reporter=self.reporter,
            control=self.control,
            recipes=recipes,
            max_repairs=max_repairs,
            max_llm_calls=max_llm_calls,
            max_steps=max_steps,
            knowledge=knowledge,
        )

    @staticmethod
    def demo() -> LLM:
        return demo_llm()

    @staticmethod
    def input(
        project_type: str,
        recipe: str,
        request: str,
        title: str = "Projet",
        trace_id: str = "trace_test",
    ) -> RunInput:
        return RunInput(
            run_id="run_test",
            project_id="proj_test",
            project_type=project_type,
            recipe_kind=recipe,
            title=title,
            request=request,
            trace_id=trace_id,
        )

    def events(self, kind: str) -> list[dict[str, Any]]:
        return [
            payload for event_type, payload, _step in self.reporter.events if event_type == kind
        ]


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    return Harness(tmp_path)
