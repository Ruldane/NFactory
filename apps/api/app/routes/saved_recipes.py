"""Reusable factory recipes (spec F38): save a delivered run, replay it as a new run."""

from typing import Annotated

from fastapi import APIRouter, Header, Response, status

from app.context import AppSettings, CanBuild, Context, Queue, Session, Sessions
from app.schemas.common import Items
from app.schemas.runs import RunDetail
from app.schemas.saved_recipes import RecipeLaunch, SavedRecipeIn, SavedRecipeOut
from app.services import saved_recipes

router = APIRouter(prefix="/saved-recipes", tags=["recipes"])


@router.get("")
async def list_saved_recipes(session: Session, ctx: Context) -> Items[SavedRecipeOut]:
    return Items(items=await saved_recipes.list_recipes(session, ctx))


@router.post("", status_code=status.HTTP_201_CREATED)
async def save_recipe(data: SavedRecipeIn, session: Session, ctx: CanBuild) -> SavedRecipeOut:
    return await saved_recipes.save_recipe(session, ctx, data)


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_recipe(recipe_id: str, session: Session, ctx: CanBuild) -> Response:
    await saved_recipes.delete_recipe(session, ctx, recipe_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{recipe_id}/launch", status_code=status.HTTP_201_CREATED)
async def launch_recipe(
    recipe_id: str,
    data: RecipeLaunch,
    sessions: Sessions,
    ctx: CanBuild,
    settings: AppSettings,
    queue: Queue,
    response: Response,
    idempotency_key: Annotated[str | None, Header()] = None,
) -> RunDetail:
    """Replay the recipe: a new project of the same type, and a run of the same request."""
    launched = await saved_recipes.launch_recipe(
        sessions, ctx, settings, queue, recipe_id, data, idempotency_key
    )
    if not launched.created:
        response.status_code = status.HTTP_200_OK
    return launched.run
