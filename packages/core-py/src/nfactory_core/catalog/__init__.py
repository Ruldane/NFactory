"""Recipe catalog. Interface: CATALOG, PROJECT_TYPES, available_recipes, recipe_for_type,
recipe_by_kind, resolve_recipe."""

from nfactory_core.catalog.entries import CATALOG
from nfactory_core.catalog.types import CURRENT_PHASE, Deliverable, RecipeInfo

PROJECT_TYPES: tuple[str, ...] = tuple(entry.project_type for entry in CATALOG)

_BY_TYPE = {entry.project_type: entry for entry in CATALOG}
_BY_KIND = {entry.kind: entry for entry in CATALOG}


class UnknownProjectTypeError(KeyError):
    pass


def available_recipes() -> tuple[RecipeInfo, ...]:
    return tuple(entry for entry in CATALOG if entry.available)


def recipe_for_type(project_type: str) -> RecipeInfo:
    try:
        return _BY_TYPE[project_type]
    except KeyError:
        raise UnknownProjectTypeError(project_type) from None


def recipe_by_kind(kind: str) -> RecipeInfo:
    try:
        return _BY_KIND[kind]
    except KeyError:
        raise UnknownProjectTypeError(kind) from None


def resolve_recipe(project_type: str, template_id: str | None) -> RecipeInfo:
    """The recipe a project builds with: its template if it names one, else its type's."""
    return recipe_by_kind(template_id) if template_id else recipe_for_type(project_type)


__all__ = [
    "CATALOG",
    "CURRENT_PHASE",
    "PROJECT_TYPES",
    "Deliverable",
    "RecipeInfo",
    "UnknownProjectTypeError",
    "available_recipes",
    "recipe_by_kind",
    "recipe_for_type",
    "resolve_recipe",
]
