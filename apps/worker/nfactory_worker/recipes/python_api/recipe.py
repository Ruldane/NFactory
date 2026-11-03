"""python-api recipe: FastAPI + SQLAlchemy (SQLite) + Alembic + pytest, one CRUD resource."""

import json
import re

from nfactory_worker.brief import Brief, EntitySpec
from nfactory_worker.recipes.base import RenderedProject
from nfactory_worker.recipes.checks import pytest_check, ruff_check
from nfactory_worker.recipes.python_api.fields import (
    DEFAULT_ENTITY,
    TYPES,
    class_name,
    payload,
    uses_dates,
)
from nfactory_worker.recipes.rendering import load_template, py_literal, render_template

_PACKAGE = __package__ or "nfactory_worker.recipes.python_api"
_DATE_IMPORT = "from datetime import date\n\n"
_EXPORT_DEPENDENCY = '    "openpyxl>=3.1",\n'
_EXPORT_IMPORT = "from app.export import router as export_router\n"
# Included before the CRUD router, whose /{id} would otherwise catch /export.xlsx.
_EXPORT_ROUTE = "app.include_router(export_router)\n"
_SHEET_FORBIDDEN = re.compile(r"[\[\]:*?/\\]")  # characters Excel refuses in a sheet name


class PythonApiRecipe:
    """`excel_export` adds GET /<plural>/export.xlsx (openpyxl) and its tests."""

    kind = "python-api"
    version = "1.1.0"

    def __init__(self, *, excel_export: bool = False) -> None:
        self.excel_export = excel_export

    def render(self, brief: Brief) -> RenderedProject:
        entity = brief.entity or DEFAULT_ENTITY
        cls = class_name(entity)
        date_import = _DATE_IMPORT if uses_dates(entity) else ""

        def tpl(template: str, /, **values: str) -> str:
            return render_template(load_template(_PACKAGE, template), values)

        files: dict[str, str | bytes] = {
            "README.md": tpl("README.md", **_readme_values(brief, entity, self.version)),
            "pyproject.toml": tpl(
                "pyproject.toml",
                slug=brief.slug,
                description=json.dumps(brief.summary[:200]),
                extra_dependencies=_EXPORT_DEPENDENCY if self.excel_export else "",
            ),
            "app/__init__.py": "",
            "app/db.py": tpl("db.py"),
            "app/models.py": tpl(
                "models.py",
                date_import=date_import,
                class_name=cls,
                table=py_literal(entity.plural),
                columns=_columns(entity),
            ),
            "app/schemas.py": tpl(
                "schemas.py",
                date_import=date_import,
                class_name=cls,
                fields=_schema_fields(entity),
            ),
            "app/routes.py": tpl(
                "routes.py",
                class_name=cls,
                name=entity.name,
                plural=entity.plural,
                tag=py_literal(entity.label),
                not_found=py_literal(f"{entity.label} introuvable"),
            ),
            "app/main.py": tpl(
                "main.py",
                title=py_literal(brief.title),
                export_import=_EXPORT_IMPORT if self.excel_export else "",
                export_route=_EXPORT_ROUTE if self.excel_export else "",
            ),
            "app/migrate.py": tpl("migrate.py"),
            "alembic.ini": tpl("alembic.ini"),
            "migrations/env.py": tpl("env.py"),
            "migrations/script.py.mako": tpl("script.py.mako"),
            "migrations/versions/0001_initial.py": tpl(
                "initial_migration.py",
                plural=entity.plural,
                table=py_literal(entity.plural),
                columns=_migration_columns(entity),
            ),
            "tests/test_migrations.py": tpl("test_migrations.py"),
            "tests/__init__.py": "",
            "tests/conftest.py": tpl("conftest.py"),
            f"tests/test_{entity.plural}.py": tpl(
                "test_api.py",
                plural=entity.plural,
                payload=repr(payload(entity)),
                updated=repr(payload(entity, updated=True)),
            ),
            ".gitignore": "__pycache__/\n.venv/\n*.db\n.nfactory/\n",
        }
        if self.excel_export:
            files["app/export.py"] = tpl(
                "export.py",
                class_name=cls,
                plural=entity.plural,
                tag=py_literal(entity.label),
                sheet=py_literal(_SHEET_FORBIDDEN.sub(" ", entity.label)[:31]),
                columns=repr([(f.name, f.label) for f in entity.fields]),
            )
            files["tests/test_export.py"] = tpl(
                "test_export.py",
                plural=entity.plural,
                payload=repr(payload(entity)),
                headers=repr(["N°", *(f.label for f in entity.fields)]),
            )
        return RenderedProject(files=files, checks=(ruff_check(), pytest_check()))


def _columns(entity: EntitySpec) -> str:
    return "\n".join(
        f"    {f.name}: Mapped[{TYPES[f.type].annotation}] = mapped_column()" for f in entity.fields
    )


def _migration_columns(entity: EntitySpec) -> str:
    return "\n".join(
        f"        sa.Column({py_literal(f.name)}, {TYPES[f.type].sa_type}, nullable=False),"
        for f in entity.fields
    )


def _schema_fields(entity: EntitySpec) -> str:
    lines = []
    for f in entity.fields:
        constraints = ", min_length=1, max_length=200" if f.type == "str" else ""
        lines.append(
            f"    {f.name}: {TYPES[f.type].annotation} = "
            f"Field(description={py_literal(f.label)}{constraints})"
        )
    return "\n".join(lines)


def _readme_values(brief: Brief, entity: EntitySpec, version: str) -> dict[str, str]:
    rows = "\n".join(f"| `{f.name}` | {f.label} | {f.type} |" for f in entity.fields)
    example = json.dumps(payload(entity), ensure_ascii=False).replace("'", "'\\''")
    return {
        "title": brief.title,
        "summary": brief.summary or "API générée par NFactory.",
        "version": version,
        "plural": entity.plural,
        "fields_table": f"| Champ | Libellé | Type |\n|---|---|---|\n{rows}",
        "payload_json": example,
    }
