"""Test results come from the JUnit XML written by pytest, never from an agent's claim."""

import pytest

from nfactory_worker.runner import JUnitError, parse_junit

REPORT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" errors="1" failures="1" skipped="1" tests="5">
<testcase classname="tests.test_api" name="test_ok" time="0.01"/>
<testcase classname="tests.test_api" name="test_ok2" time="0.01"/>
<testcase classname="tests.test_api" name="test_bad" time="0.01">
  <failure message="assert 1 == 2">trace</failure></testcase>
<testcase classname="tests.test_api" name="test_boom" time="0.01">
  <error message="fixture exploded">trace</error></testcase>
<testcase classname="tests.test_api" name="test_skip" time="0.01">
  <skipped message="later"/></testcase>
</testsuite></testsuites>"""


def test_counts_each_outcome() -> None:
    report = parse_junit(REPORT)
    assert (report.passed, report.failed, report.errors, report.skipped) == (2, 1, 1, 1)
    assert report.total == 5
    assert not report.ok


def test_failures_carry_name_and_message() -> None:
    report = parse_junit(REPORT)
    assert [(f.name, f.message) for f in report.failures] == [
        ("tests.test_api::test_bad", "assert 1 == 2"),
        ("tests.test_api::test_boom", "fixture exploded"),
    ]


def test_all_green_report_is_ok() -> None:
    xml = '<testsuite><testcase classname="t" name="a"/></testsuite>'
    assert parse_junit(xml).ok


def test_empty_suite_is_not_ok() -> None:
    # Zero tests run must never count as success.
    assert not parse_junit("<testsuite/>").ok


@pytest.mark.parametrize("bad", ["", "not xml", "<html/>"])
def test_garbage_is_rejected(bad: str) -> None:
    with pytest.raises(JUnitError):
        parse_junit(bad)


def test_a_report_with_a_byte_order_mark_is_read() -> None:
    xml = (
        '\ufeff<?xml version="1.0" encoding="utf-8"?>'
        '<testsuites><testsuite><testcase classname="a" name="b"/></testsuite></testsuites>'
    )
    assert parse_junit(xml).passed == 1


def test_reports_of_several_checks_add_up() -> None:
    from nfactory_worker.runner import TestFailure, TestReport, merge_reports

    backend = TestReport(passed=3, failed=1, failures=[TestFailure("b::x", "boom")])
    frontend = TestReport(passed=2, skipped=1)

    merged = merge_reports([backend, frontend])

    assert (merged.passed, merged.failed, merged.skipped, merged.total) == (5, 1, 1, 7)
    assert [f.name for f in merged.failures] == ["b::x"]
    assert not merged.ok
