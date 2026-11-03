"""Project recipes, one package per project type.

Interface: get_recipe(kind) -> Recipe, registered_kinds(), Recipe, RenderedProject, Check,
Preview.
"""

from nfactory_worker.recipes.base import Check, Preview, Recipe, RenderedProject, Stage
from nfactory_worker.recipes.registry import (
    RecipeNotAvailableError,
    get_recipe,
    registered_kinds,
)

__all__ = [
    "Check",
    "Preview",
    "Recipe",
    "RecipeNotAvailableError",
    "RenderedProject",
    "Stage",
    "get_recipe",
    "registered_kinds",
]
