"""Parse pytest's JUnit XML into a verified test report (spec §5.1: the runner, not an
agent, decides whether tests passed)."""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

MAX_REPORT_BYTES = 5_000_000


class JUnitError(ValueError):
    pass


@dataclass(frozen=True)
class TestFailure:
    name: str
    message: str


@dataclass(frozen=True)
class TestReport:
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    failures: list[TestFailure] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.errors + self.skipped

    @property
    def ok(self) -> bool:
        # No test executed is never a success.
        return self.passed > 0 and self.failed == 0 and self.errors == 0


def parse_junit(xml_text: str) -> TestReport:
    if not xml_text or len(xml_text) > MAX_REPORT_BYTES:
        raise JUnitError("Empty or oversized JUnit report")
    try:
        root = ET.fromstring(xml_text)  # noqa: S314 - bounded size, expat entity limits
    except ET.ParseError as exc:
        raise JUnitError(f"Invalid JUnit XML: {exc}") from exc
    if root.tag not in {"testsuites", "testsuite"}:
        raise JUnitError(f"Unexpected root element: {root.tag}")

    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    failures: list[TestFailure] = []
    for case in root.iter("testcase"):
        name = f"{case.get('classname', '')}::{case.get('name', '')}"
        outcome = _outcome(case)
        counts[outcome] += 1
        if outcome in {"failed", "errors"}:
            node = case.find("failure") if outcome == "failed" else case.find("error")
            message = (node.get("message") if node is not None else None) or ""
            failures.append(TestFailure(name=name, message=message[:500]))
    return TestReport(**counts, failures=failures)


def _outcome(case: ET.Element) -> str:
    if case.find("failure") is not None:
        return "failed"
    if case.find("error") is not None:
        return "errors"
    if case.find("skipped") is not None:
        return "skipped"
    return "passed"


def merge_reports(reports: list[TestReport]) -> TestReport:
    """One verdict for a project tested by several checks (backend and frontend)."""
    return TestReport(
        passed=sum(r.passed for r in reports),
        failed=sum(r.failed for r in reports),
        errors=sum(r.errors for r in reports),
        skipped=sum(r.skipped for r in reports),
        failures=[failure for r in reports for failure in r.failures],
    )
