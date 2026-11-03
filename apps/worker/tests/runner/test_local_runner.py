"""The local runner executes allow-listed commands inside a workspace, with a timeout
and a scrubbed environment."""

import sys
from pathlib import Path

import pytest

from nfactory_worker.runner import CommandNotAllowedError, LocalRunner


@pytest.fixture
def runner(tmp_path: Path) -> LocalRunner:
    (tmp_path / "run_1").mkdir()
    return LocalRunner(tmp_path, python=sys.executable)


async def test_runs_python_in_the_workspace_directory(runner: LocalRunner, tmp_path: Path) -> None:
    result = await runner.run("run_1", ("python", "-c", "import os; print(os.getcwd())"), 30)
    assert result.exit_code == 0
    assert Path(result.stdout.strip()) == tmp_path / "run_1"
    assert not result.timed_out


async def test_non_zero_exit_is_reported(runner: LocalRunner) -> None:
    result = await runner.run("run_1", ("python", "-c", "import sys; sys.exit(3)"), 30)
    assert result.exit_code == 3


async def test_timeout_kills_the_command(runner: LocalRunner) -> None:
    result = await runner.run("run_1", ("python", "-c", "import time; time.sleep(30)"), 1)
    assert result.timed_out
    assert result.exit_code != 0


async def test_only_allow_listed_executables_run(runner: LocalRunner) -> None:
    with pytest.raises(CommandNotAllowedError):
        await runner.run("run_1", ("cmd", "/c", "dir"), 30)


async def test_unknown_workspace_is_refused(runner: LocalRunner) -> None:
    with pytest.raises(CommandNotAllowedError):
        await runner.run("../run_1", ("python", "-c", "pass"), 30)


async def test_environment_is_scrubbed_of_secrets(
    runner: LocalRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-not-leak")
    code = "import os; print(os.environ.get('OPENAI_API_KEY', 'absent'))"
    result = await runner.run("run_1", ("python", "-c", code), 30)
    assert result.stdout.strip() == "absent"


async def test_huge_output_is_truncated(runner: LocalRunner) -> None:
    result = await runner.run("run_1", ("python", "-c", "print('x' * 500_000)"), 30)
    assert len(result.stdout) < 100_000
    assert result.stdout.endswith("[sortie tronquée]")


async def test_powershell_and_node_are_allowed_tools(tmp_path: Path) -> None:
    (tmp_path / "run_1").mkdir()
    runner = LocalRunner(tmp_path, python=sys.executable, tools={"node": sys.executable})

    result = await runner.run("run_1", ("node", "-c", "print('as node')"), 30)

    assert result.ok and result.stdout.strip() == "as node"


async def test_a_tool_missing_on_this_machine_fails_the_check_clearly(tmp_path: Path) -> None:
    (tmp_path / "run_1").mkdir()
    runner = LocalRunner(tmp_path, python=sys.executable, tools={})

    result = await runner.run("run_1", ("pwsh", "-File", "x.ps1"), 30)

    assert result.exit_code == 127 and not result.ok
    assert "pwsh" in result.stderr and "introuvable" in result.stderr


async def test_the_preinstalled_web_toolchain_location_reaches_the_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "run_1").mkdir()
    monkeypatch.setenv("NFACTORY_WEB_DEPS", "/opt/deps")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-never-passed")
    runner = LocalRunner(tmp_path, python=sys.executable)
    code = "import os; print(os.environ.get('NFACTORY_WEB_DEPS'), os.environ.get('OPENAI_API_KEY'))"

    result = await runner.run("run_1", ("python", "-c", code), 30)

    assert result.stdout.strip() == "/opt/deps None"
