"""document recipe: a structured Word document (procedure, report or note).

The deliverable is non-code. The Markdown source is the editable truth, and a small
script renders it to .docx so the result stays reproducible and checkable.
"""

import json

from nfactory_worker.artifacts import AI_NOTICE
from nfactory_worker.brief import Brief
from nfactory_worker.recipes.base import RenderedProject
from nfactory_worker.recipes.checks import pytest_check, python_script, ruff_check
from nfactory_worker.recipes.document.markdown import one_line, render_markdown, sections_for
from nfactory_worker.recipes.rendering import load_template, py_literal, render_template

_PACKAGE = __package__ or "nfactory_worker.recipes.document"
KIND_LABELS = {"procedure": "Procédure", "report": "Rapport", "note": "Note"}


class DocumentRecipe:
    kind = "document"
    version = "1.0.0"

    def render(self, brief: Brief) -> RenderedProject:
        title = one_line(brief.title)
        sections = sections_for(brief)
        output_name = f"{brief.slug}.docx"
        outline = {
            "title": title,
            "kind": brief.document_kind,
            "output": f"output/{output_name}",
            "sections": [section.title for section in sections],
        }

        def tpl(template: str, /, **values: str) -> str:
            return render_template(load_template(_PACKAGE, template), values)

        files: dict[str, str | bytes] = {
            "content/document.md": render_markdown(title, brief.summary, sections),
            "content/outline.json": json.dumps(outline, ensure_ascii=False, indent=2) + "\n",
            "build_document.py": tpl("build_document.py", ai_notice=py_literal(AI_NOTICE)),
            "tests/__init__.py": "",
            "tests/test_document.py": tpl("test_document.py"),
            "pyproject.toml": tpl("pyproject.toml", slug=brief.slug),
            "README.md": tpl(
                "README.md",
                title=title,
                kind=KIND_LABELS[brief.document_kind],
                output_name=output_name,
                version=self.version,
            ),
            ".gitignore": "__pycache__/\n.venv/\n.nfactory/\n",
        }
        return RenderedProject(
            files=files,
            checks=(
                ruff_check(),
                python_script("build_document.py", "Génération du document"),
                pytest_check(),
            ),
            deliverables=(f"output/{output_name}",),
        )
