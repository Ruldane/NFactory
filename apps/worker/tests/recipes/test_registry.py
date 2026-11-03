import pytest

from nfactory_core.catalog import CATALOG, available_recipes
from nfactory_worker.recipes import RecipeNotAvailableError, get_recipe, registered_kinds


def test_registry_implements_exactly_the_available_catalog_entries() -> None:
    # A recipe is "available" in the UI only if the worker can really run it, and vice versa.
    assert registered_kinds() == {entry.kind for entry in available_recipes()}


def test_get_recipe_returns_matching_kind() -> None:
    for kind in registered_kinds():
        assert get_recipe(kind).kind == kind


@pytest.mark.parametrize("kind", [e.kind for e in CATALOG if not e.available] + ["nope"])
def test_planned_or_unknown_kinds_are_refused(kind: str) -> None:
    with pytest.raises(RecipeNotAvailableError):
        get_recipe(kind)
