"""The eval report (spec §14.2): JSON and HTML, every figure with its source, and a
comparison with the previous report."""

import json
from pathlib import Path
from typing import Any

from nfactory_worker.evals import build_report, render_html, write_report


def result(
    case_id: str, status: str, duration: float = 2.0, cost: float | None = 0.0
) -> dict[str, Any]:
    return {
        "id": case_id,
        "suite": "web_api",
        "project_type": "api",
        "tags": [],
        "status": status,
        "skipped": "pwsh absent" if status == "skipped" else None,
        "checks": [{"name": "outcome", "ok": status == "passed", "detail": "<b>x</b>"}],
        "metrics": {"duration_s": duration, "cost_usd": cost, "llm_calls": 5, "findings": 0},
    }


META = {"engine": {"provider": "fake", "model": "fake-demo-1", "demo": True}, "runner": "local"}


def test_the_totals_leave_skipped_cases_out_of_the_rate() -> None:
    report = build_report(
        [result("a", "passed"), result("b", "failed"), result("c", "skipped")], META
    )

    totals = report["totals"]
    assert (totals["cases"], totals["passed"], totals["failed"], totals["skipped"]) == (3, 1, 1, 1)
    assert totals["pass_rate"] == 0.5
    assert report["by_suite"]["web_api"]["passed"] == 1
    assert report["engine"]["demo"] is True
    assert all(figure["source"] for figure in report["figures"].values())


def test_latency_and_cost_are_measured_or_unknown() -> None:
    durations = [result(f"c{i}", "passed", duration=float(i)) for i in range(1, 11)]
    report = build_report([*durations, result("x", "passed", cost=None)], META)

    assert report["figures"]["latency_p50_s"]["value"] == 5.0
    assert report["figures"]["latency_p95_s"]["value"] == 10.0
    assert report["figures"]["cost_usd"]["value"] is None  # one case had no known price


def test_the_comparison_names_regressions_and_fixes() -> None:
    previous = build_report([result("a", "passed"), result("b", "failed")], META)

    report = build_report([result("a", "failed"), result("b", "passed")], META, previous)

    comparison = report["comparison"]
    assert comparison["regressions"] == ["a"] and comparison["fixed"] == ["b"]
    assert comparison["pass_rate_before"] == 0.5


def test_the_html_escapes_case_content(tmp_path: Path) -> None:
    report = build_report([result("a", "failed")], META)

    html = render_html(report)
    assert "<b>x</b>" not in html and "&lt;b&gt;x&lt;/b&gt;" in html
    assert "moteur démo" in html.lower()

    json_path, html_path = write_report(report, tmp_path)
    assert json.loads(json_path.read_text(encoding="utf-8"))["totals"]["failed"] == 1
    assert html_path.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
    assert (tmp_path / "latest.json").is_file()
