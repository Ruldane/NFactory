"""The python-api recipe produces a project whose own lint and tests really pass."""

from nfactory_worker.brief import Brief
from nfactory_worker.recipes.checks import JUNIT_PATH
from nfactory_worker.recipes.python_api import PythonApiRecipe

LICENCES = Brief.model_validate(
    {
        "title": "Gestion des licences",
        "summary": "Suivre les licences logicielles et leurs échéances.",
        "project_type": "api",
        "entity": {
            "name": "licence",
            "plural": "licences",
            "label": "Licence",
            "fields": [
                {"name": "name", "label": "Nom", "type": "str"},
                {"name": "seats", "label": "Postes", "type": "int"},
                {"name": "price", "label": "Prix annuel", "type": "float"},
                {"name": "active", "label": "Active", "type": "bool"},
                {"name": "expires_on", "label": "Expiration", "type": "date"},
            ],
        },
    }
)


def test_render_lists_the_expected_project_layout() -> None:
    files = PythonApiRecipe().render(LICENCES).files
    assert {
        "README.md",
        "pyproject.toml",
        "app/__init__.py",
        "app/db.py",
        "app/models.py",
        "app/schemas.py",
        "app/routes.py",
        "app/main.py",
        "tests/conftest.py",
        "tests/test_licences.py",
        "alembic.ini",
        "migrations/env.py",
        "migrations/script.py.mako",
        "migrations/versions/0001_initial.py",
        "tests/test_migrations.py",
    } <= files.keys()


def test_schema_comes_from_migrations_not_create_all() -> None:
    files = PythonApiRecipe().render(LICENCES).files
    assert "create_all" not in str(files["app/main.py"])
    assert "Ajoutez Alembic" not in str(files["README.md"])
    assert "alembic upgrade head" in str(files["README.md"])


def test_render_is_deterministic() -> None:
    assert PythonApiRecipe().render(LICENCES) == PythonApiRecipe().render(LICENCES)


async def test_generated_project_passes_its_own_lint_and_tests(run_recipe) -> None:  # type: ignore[no-untyped-def]
    execution = await run_recipe(PythonApiRecipe().render(LICENCES))
    assert execution.failures() == []
    assert execution.report is not None
    assert execution.report.ok
    assert execution.report.passed >= 9
    # The generated migration really builds the models' schema (checked by Alembic).
    junit = execution.workspace.read_text(JUNIT_PATH)
    assert 'name="test_migrations_match_the_models"' in junit


async def test_hostile_text_stays_inert_in_generated_code(run_recipe) -> None:  # type: ignore[no-untyped-def]
    hostile = LICENCES.model_copy(
        update={"title": 'Évil"); import os; os.system("x") #', "summary": "{{title}} ``` '"}
    )
    rendered = PythonApiRecipe().render(hostile)
    assert "import os; os.system" not in rendered.files["app/main.py"].split("TITLE = ")[0]
    execution = await run_recipe(rendered)
    assert execution.failures() == []


def test_brief_without_entity_falls_back_to_a_generic_resource() -> None:
    brief = Brief(title="Mon API", summary="", project_type="api")
    assert "tests/test_items.py" in PythonApiRecipe().render(brief).files
