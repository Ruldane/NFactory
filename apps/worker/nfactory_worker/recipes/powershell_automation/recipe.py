"""powershell-automation recipe: a .ps1 that checks a CSV and writes a report.

Brief text only enters PowerShell code as single-quoted literals (`ps_literal`) or
one-line comments (`ps_comment`); field names are already safe identifiers. Scripts are
written with a UTF-8 BOM so Windows PowerShell 5.1 reads their accents correctly.
"""

import csv
import io

from nfactory_worker.brief import Brief, EntitySpec
from nfactory_worker.recipes.base import Check, RenderedProject
from nfactory_worker.recipes.python_api.fields import DEFAULT_ENTITY, TYPES, class_name
from nfactory_worker.recipes.rendering import load_template, ps_comment, ps_literal, render_template

_PACKAGE = __package__ or "nfactory_worker.recipes.powershell_automation"
_BOM = b"\xef\xbb\xbf"
JUNIT_PATH = ".nfactory/junit.xml"
_PWSH = ("pwsh", "-NoProfile", "-NonInteractive")
# A value each type rejects, used for the demo row the script must flag.
_INVALID = {
    "int": "pas un nombre",
    "float": "pas un nombre",
    "date": "31/12/2026",
    "bool": "peut-être",
}


class PowerShellAutomationRecipe:
    kind = "powershell-automation"
    version = "1.0.0"

    def render(self, brief: Brief) -> RenderedProject:
        entity = brief.entity or DEFAULT_ENTITY
        script = f"Export-{class_name(entity)}Report.ps1"
        sample = f"exemples/{entity.plural}.csv"
        report = f"output/rapport-{entity.plural}.csv"
        valid, updated, invalid = _rows(entity)
        header = [f.name for f in entity.fields]

        def tpl(template: str, /, **values: str) -> str:
            return render_template(load_template(_PACKAGE, template), values)

        def ps1(text: str) -> bytes:
            return _BOM + text.encode("utf-8")

        files: dict[str, str | bytes] = {
            script: ps1(
                tpl(
                    "script.ps1",
                    synopsis=ps_comment(brief.title),
                    description=ps_comment(brief.summary or brief.title),
                    script=script,
                    sample=sample,
                    columns=_columns(entity),
                )
            ),
            f"tests/{script.removesuffix('.ps1')}.Tests.ps1": ps1(
                tpl(
                    "script.Tests.ps1",
                    script=ps_literal(script),
                    header=ps_literal(_csv_line(header)),
                    valid=ps_literal(_csv_line(valid)),
                    invalid=ps_literal(_csv_line(invalid)),
                    describe=ps_literal(script.removesuffix(".ps1")),
                )
            ),
            "tests/Security.Tests.ps1": ps1(tpl("Security.Tests.ps1", script=ps_literal(script))),
            "tools/Invoke-Analysis.ps1": ps1(tpl("Invoke-Analysis.ps1")),
            "tools/Invoke-Tests.ps1": ps1(tpl("Invoke-Tests.ps1", junit=ps_literal(JUNIT_PATH))),
            sample: _csv_text([header, valid, updated, invalid]),
            "README.md": tpl(
                "README.md",
                title=brief.title,
                summary=brief.summary or "Script généré par NFactory.",
                version=self.version,
                script=script,
                sample=sample,
                report=report,
                columns_table=_columns_table(entity),
            ),
            ".gitignore": "output/\n.nfactory/\n*.log\n",
        }
        checks = (
            Check(
                name="Analyse statique (PSScriptAnalyzer)",
                stage="static",
                argv=(*_PWSH, "-File", "tools/Invoke-Analysis.ps1"),
                timeout_s=180,
            ),
            Check(
                name="Exécution sur les données d'exemple",
                stage="build",
                argv=(
                    *_PWSH,
                    "-File",
                    script,
                    "-InputPath",
                    sample,
                    "-OutputPath",
                    report,
                    "-LogPath",
                    ".nfactory/demo.log",
                ),
                timeout_s=120,
            ),
            Check(
                name="Tests (Pester)",
                stage="tests",
                argv=(*_PWSH, "-File", "tools/Invoke-Tests.ps1"),
                timeout_s=300,
                junit_path=JUNIT_PATH,
            ),
        )
        return RenderedProject(files=files, checks=checks, deliverables=(script, report))


def _columns(entity: EntitySpec) -> str:
    return ",\n".join(
        f"    @{{ Name = {ps_literal(f.name)}; Label = {ps_literal(f.label)}; Type = '{f.type}' }}"
        for f in entity.fields
    )


def _value(field_type: str, raw: object) -> str:
    if field_type == "bool":
        return "oui" if raw else "non"
    return str(raw)


def _rows(entity: EntitySpec) -> tuple[list[str], list[str], list[str]]:
    def row(updated: bool) -> list[str]:
        values = []
        for f in entity.fields:
            info = TYPES[f.type]
            raw = info.updated if updated else info.sample
            values.append(f"{raw} {f.label}" if f.type == "str" else _value(f.type, raw))
        return values

    valid, updated = row(False), row(True)
    invalid = [_INVALID.get(f.type, value) for f, value in zip(entity.fields, valid, strict=True)]
    if invalid == valid:  # text fields only: an empty value is the error to flag
        invalid[0] = ""
    return valid, updated, invalid


def _csv_line(values: list[str]) -> str:
    return _csv_text([values]).rstrip("\n")


def _csv_text(rows: list[list[str]]) -> str:
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    return buffer.getvalue()


def _columns_table(entity: EntitySpec) -> str:
    kinds = {
        "str": "texte non vide",
        "int": "entier",
        "float": "nombre (point décimal)",
        "bool": "oui / non",
        "date": "date AAAA-MM-JJ",
    }
    rows = "\n".join(f"| `{f.name}` | {f.label} | {kinds[f.type]} |" for f in entity.fields)
    return f"| Colonne | Libellé | Valeur attendue |\n|---|---|---|\n{rows}"
