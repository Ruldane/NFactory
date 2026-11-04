"""excel-automation recipe: a reproducible Python script that turns CSV exports into a
multi-sheet .xlsx (data, KPI formulas, chart, summary), plus tests that check the
formulas against the source data."""

import json

from nfactory_worker.artifacts import AI_NOTICE
from nfactory_worker.brief import Brief
from nfactory_worker.recipes.base import RenderedProject
from nfactory_worker.recipes.checks import pytest_check, python_script, ruff_check
from nfactory_worker.recipes.excel_automation.sample_data import activity_csv, targets_csv
from nfactory_worker.recipes.rendering import load_template, py_literal, render_template

_PACKAGE = __package__ or "nfactory_worker.recipes.excel_automation"


class ExcelAutomationRecipe:
    kind = "excel-automation"
    version = "1.0.0"

    def render(self, brief: Brief) -> RenderedProject:
        output_name = f"{brief.slug}.xlsx"

        def tpl(template: str, /, **values: str) -> str:
            return render_template(load_template(_PACKAGE, template), values)

        goals = "\n".join(f"- {goal}" for goal in brief.goals) or "- Indicateurs par équipe"
        files: dict[str, str | bytes] = {
            "build_report.py": tpl(
                "build_report.py",
                title=py_literal(brief.title),
                output_name=py_literal(output_name),
                ai_notice=py_literal(AI_NOTICE),
            ),
            "data/activite.csv": activity_csv(),
            "data/objectifs.csv": targets_csv(),
            "tests/__init__.py": "",
            "tests/test_report.py": tpl("test_report.py"),
            "pyproject.toml": tpl(
                "pyproject.toml", slug=brief.slug, description=json.dumps(brief.summary[:200])
            ),
            "README.md": tpl(
                "README.md",
                title=brief.title,
                summary=brief.summary or "Classeur Excel généré par NFactory.",
                goals=goals,
                output_name=output_name,
                version=self.version,
            ),
            ".gitignore": "__pycache__/\n.venv/\n.nfactory/\n",
        }
        return RenderedProject(
            files=files,
            checks=(
                ruff_check(),
                python_script("build_report.py", "Génération du classeur"),
                pytest_check(),
            ),
            deliverables=(f"output/{output_name}",),
        )
