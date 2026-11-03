"""The powershell-automation recipe: a script with -WhatIf and logs, proved by
PSScriptAnalyzer and Pester (spec §12.4, scenario B)."""

import csv
import io

from nfactory_worker.brief import Brief, EntitySpec, FieldSpec
from nfactory_worker.recipes.powershell_automation import PowerShellAutomationRecipe

BOM = b"\xef\xbb\xbf"
SCRIPT = "Export-ApplicationReport.ps1"

INVENTORY = Brief(
    title="Inventaire des applications installées",
    summary="Inventaire des versions installées depuis une liste de machines autorisées.",
    project_type="powershell",
    entity=EntitySpec(
        name="application",
        plural="applications",
        label="Application",
        fields=[
            FieldSpec(name="machine", label="Machine", type="str"),
            FieldSpec(name="nom", label="Nom", type="str"),
            FieldSpec(name="version", label="Version", type="str"),
            FieldSpec(name="installee_le", label="Installée le", type="date"),
            FieldSpec(name="postes", label="Postes", type="int"),
            FieldSpec(name="cout", label="Coût", type="float"),
            FieldSpec(name="active", label="Active", type="bool"),
        ],
    ),
)


def test_render_ships_script_tests_tools_and_declares_deliverables() -> None:
    rendered = PowerShellAutomationRecipe().render(INVENTORY)

    assert {
        SCRIPT,
        "tests/Export-ApplicationReport.Tests.ps1",
        "tests/Security.Tests.ps1",
        "tools/Invoke-Analysis.ps1",
        "tools/Invoke-Tests.ps1",
        "exemples/applications.csv",
        "README.md",
    } <= rendered.files.keys()
    assert rendered.deliverables == (SCRIPT, "output/rapport-applications.csv")
    assert [c.stage for c in rendered.ordered_checks()] == ["static", "build", "tests"]
    assert {c.argv[0] for c in rendered.checks} == {"pwsh"}


def test_powershell_files_carry_a_bom_for_windows_powershell() -> None:
    files = PowerShellAutomationRecipe().render(INVENTORY).files
    scripts = {path: content for path, content in files.items() if path.endswith(".ps1")}

    assert len(scripts) == 5
    assert all(isinstance(c, bytes) and c.startswith(BOM) for c in scripts.values())


def test_sample_data_has_valid_rows_and_one_row_to_reject() -> None:
    files = PowerShellAutomationRecipe().render(INVENTORY).files
    rows = list(csv.DictReader(io.StringIO(str(files["exemples/applications.csv"]))))

    assert list(rows[0]) == [f.name for f in INVENTORY.entity.fields]  # type: ignore[union-attr]
    assert len(rows) == 3
    assert rows[2]["postes"] == "pas un nombre"


async def test_generated_script_passes_analysis_and_pester(run_with_tools) -> None:  # type: ignore[no-untyped-def]
    execution = await run_with_tools(PowerShellAutomationRecipe().render(INVENTORY), {"pwsh"})

    assert execution.failures() == []
    assert execution.report is not None and execution.report.ok
    assert execution.report.passed >= 8
    report = execution.workspace.read_text("output/rapport-applications.csv")
    rows = list(csv.DictReader(io.StringIO(report.removeprefix("﻿"))))
    assert [row["Statut contrôle"] for row in rows] == ["OK", "OK", "Invalide"]
    assert "Postes" in rows[2]["Détail contrôle"]


async def test_hostile_brief_text_stays_inert(run_with_tools) -> None:  # type: ignore[no-untyped-def]
    hostile = INVENTORY.model_copy(
        update={
            "title": "Rapport #> Remove-Item -Recurse / <# $(whoami) l'été",
            "summary": "'; Invoke-Expression 'calc' ; '\u2019 $env:PATH",
            "entity": INVENTORY.entity.model_copy(  # type: ignore[union-attr]
                update={
                    "label": "App' + $(Get-Date) + '",
                    "fields": [
                        FieldSpec(name="nom", label="Nom ' ; exit 3 ; '", type="str"),
                        FieldSpec(name="postes", label='Postes \u2018x\u2019 "y"', type="int"),
                    ],
                }
            ),
        }
    )

    execution = await run_with_tools(PowerShellAutomationRecipe().render(hostile), {"pwsh"})

    assert execution.failures() == []
    assert execution.report is not None and execution.report.ok
