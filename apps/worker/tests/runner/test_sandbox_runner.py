"""SandboxRunner talks to the real supervisor HTTP layer and honours the Runner contract.

The supervisor's executor is replaced by a local subprocess here; the containers
themselves are tested in apps/sandbox/tests/test_isolation.py.
"""

import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from nfactory_worker.runner import CommandNotAllowedError, SandboxError, SandboxRunner

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "sandbox"))
from nfactory_sandbox.server import BadRequest, Config, make_server

TOKEN = "runner-token-0123456789"


class LocalExecutor:
    def __init__(self, root: Path) -> None:
        self._root = root

    def ready(self) -> bool:
        return True

    def run(self, workspace: str, argv: list[str], timeout_s: int) -> dict[str, Any]:
        if not (self._root / workspace).is_dir():
            raise BadRequest("unknown workspace")
        command = [sys.executable, *argv[1:]] if argv[0] == "python" else argv
        started = time.monotonic()
        done = subprocess.run(
            command, cwd=self._root / workspace, capture_output=True, text=True, check=False
        )
        return {
            "exit_code": done.returncode,
            "stdout": done.stdout,
            "stderr": done.stderr,
            "duration_s": time.monotonic() - started,
            "timed_out": False,
        }


@pytest.fixture
def sandbox_url(tmp_path: Path) -> Iterator[str]:
    (tmp_path / "run_1").mkdir()
    httpd = make_server("127.0.0.1", 0, Config(token=TOKEN, executor=LocalExecutor(tmp_path)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


async def test_runs_commands_through_the_sandbox(sandbox_url: str) -> None:
    runner = SandboxRunner(sandbox_url, TOKEN)
    result = await runner.run("run_1", ("python", "-c", "print('ok')"), 10)
    assert result.ok and result.stdout.strip() == "ok"


async def test_disallowed_command_is_refused_before_any_request(sandbox_url: str) -> None:
    with pytest.raises(CommandNotAllowedError):
        await SandboxRunner(sandbox_url, TOKEN).run("run_1", ("bash", "-c", "id"), 10)


async def test_wrong_token_is_an_explicit_error(sandbox_url: str) -> None:
    with pytest.raises(SandboxError, match="401"):
        await SandboxRunner(sandbox_url, "nope").run("run_1", ("python", "-V"), 10)


async def test_unreachable_sandbox_is_an_explicit_error() -> None:
    with pytest.raises(SandboxError):
        await SandboxRunner("http://127.0.0.1:1", TOKEN).run("run_1", ("python", "-V"), 10)
