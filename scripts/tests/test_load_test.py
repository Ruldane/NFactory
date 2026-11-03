"""The baseline load test (task 5.6) reports what it measured, and only that."""

import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "load_test", Path(__file__).resolve().parent.parent / "load_test.py"
)
assert _spec and _spec.loader
load_test = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(load_test)


def test_percentiles_use_the_nearest_rank() -> None:
    values = [float(v) for v in range(1, 101)]

    assert load_test.percentile(values, 50) == 50.0
    assert load_test.percentile(values, 95) == 95.0
    assert load_test.percentile(values, 99) == 99.0
    assert load_test.percentile([], 50) is None


def test_a_phase_counts_errors_and_throughput() -> None:
    samples = [(0.010, 200), (0.020, 200), (0.030, 500), (0.040, None)]  # None: no answer

    figures = load_test.summarize(samples, wall_s=2.0)

    assert figures["requests"] == 4
    assert figures["errors"] == 2
    assert figures["error_rate"] == 0.5
    assert figures["throughput_rps"] == 2.0
    assert figures["p50_ms"] == 20.0 and figures["max_ms"] == 40.0


def test_an_empty_phase_measures_nothing() -> None:
    figures = load_test.summarize([], wall_s=1.0)

    assert figures["requests"] == 0
    assert figures["p95_ms"] is None and figures["error_rate"] is None


def test_runs_are_launched_only_on_the_demo_engine() -> None:
    demo = {"demo_mode": True}
    unrouted = {"routing": {"default": None, "roles": {}}}
    routed = {"routing": {"default": {"provider": "openai_api", "model": "m"}, "roles": {}}}

    load_test.require_demo_engine(demo, unrouted)
    with pytest.raises(SystemExit, match="moteur démo"):
        load_test.require_demo_engine(demo, routed)
    with pytest.raises(SystemExit, match="moteur démo"):
        load_test.require_demo_engine({"demo_mode": False}, unrouted)


def test_the_summary_says_unmeasured_and_cites_sources() -> None:
    report = {
        "generated_at": "2026-11-03T10:00:00+00:00",
        "version": "abc",
        "machine": {"os": "Windows", "cpus": 8, "python": "3.13"},
        "parameters": {"duration_s": 5, "levels": [1], "runs": 0},
        "read_phases": [
            {"concurrency": 1, **load_test.summarize([(0.01, 200)], wall_s=1.0)},
        ],
        "run_phase": None,
        "sources": load_test.SOURCES,
    }

    text = load_test.render_markdown(report)

    assert "| 1 |" in text and "Non mesuré" in text
    assert "rang le plus proche" in text  # each figure says where it comes from
