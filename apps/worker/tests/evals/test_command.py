"""One command runs a dataset and writes the report (task 5.3)."""

import json
from pathlib import Path

from nfactory_worker.evals.__main__ import main

DATASET = """
[[case]]
id = "doc-procedure"
project_type = "document"
title = "Procédure"
request = "Procédure de mise en service d'un poste"
[case.expect]
document_kind = "procedure"
deliverables = [".docx"]

[[case]]
id = "doc-wrong"
project_type = "document"
title = "Note"
request = "Une note de service"
[case.expect]
document_kind = "report"
"""


def test_the_command_writes_a_json_and_html_report(tmp_path: Path) -> None:
    datasets = tmp_path / "datasets"
    datasets.mkdir()
    (datasets / "docs.toml").write_text(DATASET, encoding="utf-8")
    out = tmp_path / "reports"

    code = main(["--datasets", str(datasets), "--out", str(out), "--runner", "local"])

    assert code == 1  # one case failed: the command says so
    report = json.loads((out / "latest.json").read_text(encoding="utf-8"))
    statuses = {c["id"]: c["status"] for c in report["cases"]}
    assert statuses == {"doc-procedure": "passed", "doc-wrong": "failed"}
    assert list(out.glob("*.html"))


def test_only_selects_cases_by_id_or_suite(tmp_path: Path) -> None:
    datasets = tmp_path / "datasets"
    datasets.mkdir()
    (datasets / "docs.toml").write_text(DATASET, encoding="utf-8")
    out = tmp_path / "reports"

    code = main(
        [
            "--datasets",
            str(datasets),
            "--out",
            str(out),
            "--runner",
            "local",
            "--only",
            "doc-procedure",
        ]
    )

    assert code == 0
    report = json.loads((out / "latest.json").read_text(encoding="utf-8"))
    assert [c["id"] for c in report["cases"]] == ["doc-procedure"]


def test_compare_takes_any_previous_report(tmp_path: Path) -> None:
    datasets = tmp_path / "datasets"
    datasets.mkdir()
    (datasets / "docs.toml").write_text(DATASET, encoding="utf-8")
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps({"version": "v0", "totals": {"pass_rate": 1.0}, "cases": [
            {"id": "doc-procedure", "status": "failed"},
            {"id": "doc-wrong", "status": "passed"},
        ]}),
        encoding="utf-8",
    )  # fmt: skip
    out = tmp_path / "reports"

    main(["--datasets", str(datasets), "--out", str(out), "--compare", str(baseline)])

    comparison = json.loads((out / "latest.json").read_text(encoding="utf-8"))["comparison"]
    assert comparison["previous_version"] == "v0"
    assert comparison["regressions"] == ["doc-wrong"] and comparison["fixed"] == ["doc-procedure"]


def _datasets(tmp_path: Path) -> Path:
    datasets = tmp_path / "datasets"
    datasets.mkdir()
    (datasets / "docs.toml").write_text(DATASET, encoding="utf-8")
    return datasets


def test_several_engines_write_a_comparison(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The bench (task 5.5): same cases per engine, one comparison report. Opening a real
    engine needs the database; here it is replaced by a second demo engine."""
    import nfactory_worker.evals.__main__ as command
    from nfactory_worker.agents import Engines, demo_llm

    async def opened(specs):  # type: ignore[no-untyped-def]
        return {spec.label: Engines.single(demo_llm()) for spec in specs}

    monkeypatch.setattr(command, "_open_engines", opened)
    out = tmp_path / "reports"

    code = main(
        [
            "--datasets", str(_datasets(tmp_path)), "--out", str(out),
            "--only", "doc-procedure",
            "--engine", "demo", "--engine", "openai_api:gpt-test",
        ]
    )  # fmt: skip

    assert code == 0
    (bench,) = out.glob("bench-*.json")
    comparison = json.loads(bench.read_text(encoding="utf-8"))
    assert [e["engine"] for e in comparison["engines"]] == ["demo", "openai_api:gpt-test"]
    assert comparison["matrix"] == [
        {"case": "doc-procedure", "results": {"demo": "passed", "openai_api:gpt-test": "passed"}}
    ]
    assert list(out.glob("bench-*.html"))
    assert not (out / "latest.json").exists()  # the regression baseline stays the demo run's


def test_an_unknown_or_repeated_engine_stops_the_command(tmp_path: Path) -> None:
    datasets = str(_datasets(tmp_path))
    out = str(tmp_path / "reports")

    assert main(["--datasets", datasets, "--out", out, "--engine", "nope:x"]) == 2
    assert main(["--datasets", datasets, "--out", out, "--engine", "demo", "--engine", "demo"]) == 2
