"""Runs commands as local subprocesses. Used by tests and by dev setups without the
sandbox container. It enforces the same rules as the sandbox, minus OS isolation.
"""

import asyncio
import os
import re
import shutil
import subprocess
import time
from collections.abc import Mapping
from pathlib import Path

from nfactory_worker.runner.types import (
    ALLOWED_EXECUTABLES,
    MISSING_TOOL_EXIT,
    TOOL_ENV,
    CommandNotAllowedError,
    CommandResult,
    truncate,
)

_WORKSPACE = re.compile(r"^[A-Za-z0-9_-]+$")
# Variables a Python child needs on each OS. Everything else (API keys...) is dropped.
_KEPT_ENV = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "LANG")


def _installed_tools() -> dict[str, str]:
    found = {name: shutil.which(name) for name in ALLOWED_EXECUTABLES - {"python"}}
    return {name: path for name, path in found.items() if path}


class LocalRunner:
    """`tools` maps pwsh / node to their path; by default they are looked up on PATH."""

    def __init__(self, root: Path, python: str, tools: Mapping[str, str] | None = None) -> None:
        self._root = root
        self._executables = {**(_installed_tools() if tools is None else tools), "python": python}

    async def run(self, workspace: str, argv: tuple[str, ...], timeout_s: int) -> CommandResult:
        cwd = self._workspace_dir(workspace)
        if not argv or argv[0] not in ALLOWED_EXECUTABLES:
            raise CommandNotAllowedError(f"Executable not allowed: {argv[:1]}")
        if argv[0] not in self._executables:
            message = (
                f"Outil introuvable sur ce poste : {argv[0]}. "
                "Installez-le ou utilisez le bac à sable."
            )
            return CommandResult(argv, MISSING_TOOL_EXIT, "", message, 0.0)
        command = [self._executables[argv[0]], *argv[1:]]
        # A thread + subprocess.run works with any event loop (Windows selector loop too).
        return await asyncio.to_thread(self._run_blocking, argv, command, cwd, timeout_s)

    def _workspace_dir(self, workspace: str) -> Path:
        cwd = self._root / workspace
        if not _WORKSPACE.fullmatch(workspace) or not cwd.is_dir():
            raise CommandNotAllowedError(f"Unknown workspace: {workspace!r}")
        return cwd

    @staticmethod
    def _run_blocking(
        argv: tuple[str, ...], command: list[str], cwd: Path, timeout_s: int
    ) -> CommandResult:
        env = {key: os.environ[key] for key in (*_KEPT_ENV, *TOOL_ENV) if key in os.environ}
        env |= {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8", "NO_COLOR": "1"}
        started = time.monotonic()
        try:
            done = subprocess.run(  # noqa: S603 - allow-listed executable, no shell
                command,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                argv=argv,
                exit_code=-1,
                stdout=truncate(_as_text(exc.stdout)),
                stderr=truncate(_as_text(exc.stderr)),
                duration_s=time.monotonic() - started,
                timed_out=True,
            )
        return CommandResult(
            argv=argv,
            exit_code=done.returncode,
            stdout=truncate(done.stdout),
            stderr=truncate(done.stderr),
            duration_s=time.monotonic() - started,
        )


def _as_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else value
