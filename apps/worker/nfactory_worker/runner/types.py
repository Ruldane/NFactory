"""Runner interface. Two adapters: LocalRunner (tests, dev) and SandboxRunner (Docker)."""

from dataclasses import dataclass
from typing import Protocol

# Only these programs may be started. Arguments come from recipes, never from an LLM.
ALLOWED_EXECUTABLES = frozenset({"python", "pwsh", "node"})
# Non-secret variables the recipe tools need, passed on to every child process.
TOOL_ENV = ("NFACTORY_WEB_DEPS", "POWERSHELL_TELEMETRY_OPTOUT", "DOTNET_CLI_TELEMETRY_OPTOUT")
MISSING_TOOL_EXIT = 127
MAX_OUTPUT_CHARS = 64_000
TRUNCATION_MARK = "\n[sortie tronquée]"


class CommandNotAllowedError(PermissionError):
    pass


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


class Runner(Protocol):
    async def run(self, workspace: str, argv: tuple[str, ...], timeout_s: int) -> CommandResult: ...


def truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[: MAX_OUTPUT_CHARS - len(TRUNCATION_MARK)] + TRUNCATION_MARK
