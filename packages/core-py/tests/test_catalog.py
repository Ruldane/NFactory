"""The recipe catalog lists every project type, code and non-code, with an honest status."""

import pytest

from nfactory_core.catalog import (
    CATALOG,
    PROJECT_TYPES,
    UnknownProjectTypeError,
    available_recipes,
    recipe_for_type,
)


def test_catalog_covers_code_and_non_code_deliverables() -> None:
    deliverables = {entry.deliverable for entry in CATALOG}
    assert deliverables == {"code", "non-code"}


def test_phase_three_adds_the_webapp_and_powershell_recipes() -> None:
    kinds = {entry.kind for entry in available_recipes()}
    assert kinds == {
        "python-api",
        "excel-automation",
        "document",
        "webapp-react-fastapi",
        "powershell-automation",
    }


def test_planned_recipes_are_never_marked_available() -> None:
    for entry in CATALOG:
        assert entry.available == (entry.phase <= 3), entry.kind


def test_every_project_type_maps_to_exactly_one_default_recipe() -> None:
    assert len(PROJECT_TYPES) == len(CATALOG)
    for project_type in PROJECT_TYPES:
        assert recipe_for_type(project_type).project_type == project_type


def test_spec_types_are_all_present() -> None:
    assert {"webapp", "api", "excel", "powershell", "feature", "document"} <= set(PROJECT_TYPES)


def test_unknown_type_is_rejected() -> None:
    with pytest.raises(UnknownProjectTypeError):
        recipe_for_type("spaceship")


def test_kinds_and_types_are_unique() -> None:
    assert len({e.kind for e in CATALOG}) == len(CATALOG)
    assert len({e.project_type for e in CATALOG}) == len(CATALOG)


def test_resolve_recipe_prefers_the_project_template() -> None:
    from nfactory_core.catalog import resolve_recipe

    assert resolve_recipe("api", None).kind == "python-api"
    assert resolve_recipe("api", "excel-automation").kind == "excel-automation"


def test_resolve_recipe_rejects_unknown_types_and_templates() -> None:
    from nfactory_core.catalog import UnknownProjectTypeError, resolve_recipe

    with pytest.raises(UnknownProjectTypeError):
        resolve_recipe("rocket", None)
    with pytest.raises(UnknownProjectTypeError):
        resolve_recipe("api", "no-such-template")
