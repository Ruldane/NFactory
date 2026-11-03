"""A saved recipe is replayable (task 5.5, spec F38): the same type and request through
the real pipeline give the same project. With the demo engine, every generated file is
byte-identical; only what holds a clock differs (the workbook's creation date, the
JUnit timings), so those two are compared by content."""

import hashlib
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from openpyxl import load_workbook

from nfactory_worker.evals.cases import Case, Expect
from nfactory_worker.evals.run import EvalEnv, run_case
from nfactory_worker.runner import LocalRunner

REQUEST = "Un classeur Excel de suivi des dépenses, avec catégorie, montant et date."
CLOCKED = {".nfactory/junit.xml", "output/depenses.xlsx"}


def _files(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file() and not {"__pycache__", ".pytest_cache"} & set(p.parts)
    }


def _cells(path: Path) -> list[tuple[str, list[tuple[object, ...]]]]:
    workbook = load_workbook(path)
    return [(ws.title, [tuple(row) for row in ws.iter_rows(values_only=True)]) for ws in workbook]


def _junit(path: Path) -> list[tuple[str | None, str | None, bool]]:
    cases = ET.parse(path).getroot().iter("testcase")
    return sorted((c.get("classname"), c.get("name"), c.find("failure") is None) for c in cases)


async def test_replaying_a_recipe_rebuilds_the_same_project(tmp_path: Path) -> None:
    env = EvalEnv(base=tmp_path, runner=LocalRunner(tmp_path / "workspaces", python=sys.executable))
    case = Case(
        id="replay",
        suite="recipes",
        project_type="excel",
        request=REQUEST,
        title="Dépenses",
        tags=(),
        parent_request=None,
        knowledge=(),
        expect=Expect(),
    )

    first, second = await run_case(case, env), await run_case(case, env)

    assert (first.outcome, second.outcome) == ("COMPLETED", "COMPLETED")
    assert first.workspace and second.workspace and first.workspace != second.workspace
    a, b = _files(first.workspace), _files(second.workspace)
    assert set(a) == set(b) and CLOCKED <= set(a)
    assert {k: v for k, v in a.items() if k not in CLOCKED} == {
        k: v for k, v in b.items() if k not in CLOCKED
    }
    workbook = "output/depenses.xlsx"
    assert _cells(first.workspace / workbook) == _cells(second.workspace / workbook)
    junit = ".nfactory/junit.xml"
    assert _junit(first.workspace / junit) == _junit(second.workspace / junit)
    assert all(passed for *_, passed in _junit(first.workspace / junit))
