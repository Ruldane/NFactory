"""Maps catalog kinds to recipe implementations. Add new recipes here."""

from nfactory_worker.recipes.base import Recipe
from nfactory_worker.recipes.document import DocumentRecipe
from nfactory_worker.recipes.excel_automation import ExcelAutomationRecipe
from nfactory_worker.recipes.powershell_automation import PowerShellAutomationRecipe
from nfactory_worker.recipes.python_api import PythonApiRecipe
from nfactory_worker.recipes.webapp_react_fastapi import WebappRecipe

_RECIPES: dict[str, Recipe] = {
    recipe.kind: recipe
    for recipe in (
        PythonApiRecipe(),
        ExcelAutomationRecipe(),
        DocumentRecipe(),
        WebappRecipe(),
        PowerShellAutomationRecipe(),
    )
}


class RecipeNotAvailableError(LookupError):
    pass


def get_recipe(kind: str) -> Recipe:
    try:
        return _RECIPES[kind]
    except KeyError:
        raise RecipeNotAvailableError(kind) from None


def registered_kinds() -> set[str]:
    return set(_RECIPES)
