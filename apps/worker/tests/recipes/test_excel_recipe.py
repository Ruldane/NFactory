"""The excel-automation recipe builds a real .xlsx and proves its formulas."""

import zipfile

from openpyxl import load_workbook

from nfactory_worker.brief import Brief
from nfactory_worker.recipes.excel_automation import ExcelAutomationRecipe

KPI = Brief(
    title="Rapport KPI hebdomadaire",
    summary="Fusionner deux exports CSV en un classeur multi-onglets.",
    project_type="excel",
    goals=["Volume par équipe", "Taux d'atteinte des objectifs"],
)


def test_render_ships_script_data_tests_and_declares_the_xlsx() -> None:
    rendered = ExcelAutomationRecipe().render(KPI)
    assert {
        "build_report.py",
        "data/activite.csv",
        "data/objectifs.csv",
        "tests/test_report.py",
        "README.md",
        "pyproject.toml",
    } <= rendered.files.keys()
    assert rendered.deliverables == ("output/rapport-kpi-hebdomadaire.xlsx",)
    assert [c.stage for c in rendered.ordered_checks()] == ["static", "build", "tests"]


async def test_generated_workbook_is_built_and_verified(run_recipe) -> None:  # type: ignore[no-untyped-def]
    execution = await run_recipe(ExcelAutomationRecipe().render(KPI))
    assert execution.failures() == []
    assert execution.report is not None and execution.report.ok

    path = execution.workspace.resolve("output/rapport-kpi-hebdomadaire.xlsx")
    workbook = load_workbook(path)
    assert workbook.sheetnames == ["Synthèse", "Données", "KPI", "Graphique"]
    assert str(workbook["KPI"]["B2"].value).startswith("=SUMIF(")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
    assert any(name.startswith("xl/charts/") for name in names)
    assert not any("vbaProject" in name for name in names)  # no macros


async def test_hostile_title_does_not_break_the_script(run_recipe) -> None:  # type: ignore[no-untyped-def]
    hostile = KPI.model_copy(update={"title": "Bilan \"Q1\" ''' \\ {{x}}"})
    execution = await run_recipe(ExcelAutomationRecipe().render(hostile))
    assert execution.failures() == []
