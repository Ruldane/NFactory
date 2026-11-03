"""Deterministic command execution for generated projects.

Interface: Runner (protocol), LocalRunner, SandboxRunner, CommandResult, parse_junit, merge_reports,
TestReport.
"""

from nfactory_worker.runner.junit import (
    JUnitError,
    TestFailure,
    TestReport,
    merge_reports,
    parse_junit,
)
from nfactory_worker.runner.local import LocalRunner
from nfactory_worker.runner.sandbox import SandboxError, SandboxRunner
from nfactory_worker.runner.types import (
    ALLOWED_EXECUTABLES,
    CommandNotAllowedError,
    CommandResult,
    Runner,
)

__all__ = [
    "ALLOWED_EXECUTABLES",
    "CommandNotAllowedError",
    "CommandResult",
    "JUnitError",
    "LocalRunner",
    "Runner",
    "SandboxError",
    "SandboxRunner",
    "TestFailure",
    "TestReport",
    "merge_reports",
    "parse_junit",
]
