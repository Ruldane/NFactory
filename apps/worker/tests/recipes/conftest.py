"""Shared helper: render a recipe into a real workspace and run all its checks.

Recipes that need PowerShell or Node run with the local tools when this machine has
them, otherwise inside the real sandbox image with the confinement of Compose. With
neither, the test is skipped and says why: it never passes without running.
"""

import asyncio
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

from nfactory_core.workspace import Workspace
from nfactory_worker.recipes.base import Check, RenderedProject
from nfactory_worker.runner import (
    CommandResult,
    LocalRunner,
    Runner,
    TestReport,
    merge_reports,
    parse_junit,
)

SANDBOX_IMAGE = os.environ.get("NFACTORY_SANDBOX_IMAGE", "nfactory-sandbox:latest")
# The frontend toolchain installed locally (npm ci in apps/sandbox/web-deps), if any.
LOCAL_WEB_DEPS = Path(__file__).resolve().parents[3] / "sandbox" / "web-deps" / "node_modules"


@dataclass
class Execution:
    workspace: Workspace
    results: list[tuple[Check, CommandResult]]
    report: TestReport | None

    def failures(self) -> list[str]:
        return [
            f"{check.name}: exit={result.exit_code}\n{result.stdout}\n{result.stderr}"
            for check, result in self.results
            if not result.ok
        ]


async def execute(rendered: RenderedProject, base: Path, runner: Runner) -> Execution:
    workspace = Workspace.create(base, "run_test")
    workspace.write_files(rendered.files)
    results = []
    reports = []
    for check in rendered.ordered_checks():
        result = await runner.run("run_test", check.argv, check.timeout_s)
        results.append((check, result))
        if check.junit_path and workspace.resolve(check.junit_path).is_file():
            reports.append(parse_junit(workspace.read_text(check.junit_path)))
    return Execution(workspace, results, merge_reports(reports) if reports else None)


class ImageRunner:
    """Runs each command in the sandbox image, confined like the Compose service."""

    def __init__(self, root: Path, image: str) -> None:
        self._root = root
        self._image = image

    async def run(self, workspace: str, argv: tuple[str, ...], timeout_s: int) -> CommandResult:
        command = [
            "docker", "run", "--rm", "--read-only", "--tmpfs", "/tmp:size=256m",
            "--network", "none", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true", "--pids-limit", "256",
            "--memory", "1g", "--cpus", "1",
            "-e", "NO_COLOR=1",
            "-v", f"{self._root}:/data/workspaces", "-w", f"/data/workspaces/{workspace}",
            self._image, *argv,
        ]  # fmt: skip
        started = time.monotonic()
        done = await asyncio.to_thread(
            subprocess.run,
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s + 60,
            check=False,
        )
        return CommandResult(
            argv, done.returncode, done.stdout, done.stderr, time.monotonic() - started
        )


def _image_available(image: str) -> bool:
    if not shutil.which("docker"):
        return False
    inspect = ["docker", "image", "inspect", "--format", "{{.Id}}", image]
    return subprocess.run(inspect, capture_output=True, check=False).returncode == 0


def _local_ready(tools: set[str]) -> bool:
    if not all(shutil.which(tool) for tool in tools):
        return False
    if "node" not in tools:
        return True
    return bool(os.environ.get("NFACTORY_WEB_DEPS")) or LOCAL_WEB_DEPS.is_dir()


def runner_for(tools: set[str], base: Path) -> Runner:
    if _local_ready(tools):
        if "node" in tools:
            os.environ.setdefault("NFACTORY_WEB_DEPS", str(LOCAL_WEB_DEPS))
        return LocalRunner(base, python=sys.executable)
    if _image_available(SANDBOX_IMAGE):
        return ImageRunner(base, SANDBOX_IMAGE)
    pytest.skip(
        f"{', '.join(sorted(tools))} absent de ce poste et image {SANDBOX_IMAGE} introuvable "
        "(docker compose build sandbox)"
    )


@pytest.fixture
def run_recipe(tmp_path: Path):  # type: ignore[no-untyped-def]
    """Python-only recipes: the local interpreter is enough."""

    async def _run(rendered: RenderedProject) -> Execution:
        return await execute(rendered, tmp_path, LocalRunner(tmp_path, python=sys.executable))

    return _run


@pytest.fixture
def run_with_tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """Recipes that need pwsh / node: local tools, else the sandbox image."""
    monkeypatch.setenv("NFACTORY_WEB_DEPS", os.environ.get("NFACTORY_WEB_DEPS", ""))
    if not os.environ["NFACTORY_WEB_DEPS"]:
        monkeypatch.delenv("NFACTORY_WEB_DEPS")

    async def _run(rendered: RenderedProject, tools: set[str]) -> Execution:
        return await execute(rendered, tmp_path, runner_for(tools, tmp_path))

    return _run
