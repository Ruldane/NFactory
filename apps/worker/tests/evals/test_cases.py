"""Eval scenarios (task 5.3, spec §14.2) are versioned TOML files, one per suite."""

from pathlib import Path

import pytest

from nfactory_worker.evals import CaseError, load_cases, suite_counts

DATASETS = Path(__file__).resolve().parents[4] / "evals" / "datasets"


def write(tmp_path: Path, name: str, text: str) -> Path:
    (tmp_path / f"{name}.toml").write_text(text, encoding="utf-8")
    return tmp_path


def test_a_case_reads_its_request_and_expectations(tmp_path: Path) -> None:
    write(
        tmp_path,
        "excel",
        """
[[case]]
id = "excel-heures"
project_type = "excel"
title = "Suivi des heures"
request = "Un classeur des heures par semaine"
tags = ["kpi"]
[case.expect]
deliverables = [".xlsx"]
min_tests = 3
""",
    )

    (case,) = load_cases(tmp_path)

    assert (case.id, case.suite, case.project_type) == ("excel-heures", "excel", "excel")
    assert case.expect.outcome == "COMPLETED"  # the default
    assert case.expect.deliverables == (".xlsx",) and case.expect.min_tests == 3
    assert case.tags == ("kpi",)


@pytest.mark.parametrize(
    ("text", "error"),
    [
        ('[[case]]\nid = "x"\nproject_type = "api"\n', "request"),
        ('[[case]]\nid = "x"\nproject_type = "nope"\nrequest = "r"\n', "nope"),
        ('[[case]]\nid = "Bad Id"\nproject_type = "api"\nrequest = "r"\n', "Bad Id"),
        (
            '[[case]]\nid = "x"\nproject_type = "api"\nrequest = "r"\n'
            "[case.expect]\nsurprise = 1\n",
            "surprise",
        ),
    ],
)
def test_a_malformed_case_is_refused_with_its_reason(tmp_path: Path, text: str, error: str) -> None:
    write(tmp_path, "web_api", text)

    with pytest.raises(CaseError, match=error):
        load_cases(tmp_path)


def test_ids_are_unique_across_suites(tmp_path: Path) -> None:
    case = '[[case]]\nid = "same"\nproject_type = "api"\nrequest = "r"\n'
    write(tmp_path, "web_api", case)
    write(tmp_path, "feature", case)

    with pytest.raises(CaseError, match="same"):
        load_cases(tmp_path)


def test_the_versioned_dataset_covers_the_spec() -> None:
    cases = load_cases(DATASETS)

    counts = suite_counts(cases)
    # Spec §14.2: at least 30 cases, 10 web/API, 8 Excel, 6 PowerShell, 6 repo feature,
    # plus adversarial cases.
    assert len(cases) >= 30
    assert counts["web_api"] >= 10 and counts["excel"] >= 8
    assert counts["powershell"] >= 6 and counts["feature"] >= 6
    assert counts["adversarial"] >= 6
    assert all(c.parent_request for c in cases if c.suite == "feature")
    assert {c.project_type for c in cases if c.suite == "web_api"} == {"api", "webapp"}
