"""Static security analysis (spec §5.2 checks: SAST): every generated Python project is
linted with ruff's security rules (flake8-bandit, `S`), tests excepted for asserts."""

import tomllib

import pytest

from nfactory_worker.brief import Brief
from nfactory_worker.recipes import get_recipe

BRIEF = Brief(title="Suivi des licences", summary="Suivre les licences.", project_type="api")


@pytest.mark.parametrize(
    ("kind", "pyproject"),
    [
        ("python-api", "pyproject.toml"),
        ("excel-automation", "pyproject.toml"),
        ("document", "pyproject.toml"),
        ("webapp-react-fastapi", "backend/pyproject.toml"),
    ],
)
def test_generated_python_is_linted_with_security_rules(kind: str, pyproject: str) -> None:
    files = get_recipe(kind).render(BRIEF).files
    lint = tomllib.loads(str(files[pyproject]))["tool"]["ruff"]["lint"]

    assert "S" in lint["select"]
    assert lint["per-file-ignores"]["tests/**"] == ["S101"]
