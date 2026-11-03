"""Reusable factory recipes (task 5.5, spec F38).

A recipe keeps what a run needs to be replayed: the project type, the factory recipe
kind and the request. It is saved from a delivered run of the workspace, or written by
hand. Replaying it creates a new project and launches a run through `runs.launch_run`,
so budget, engines and checks are those of any new run.

Interface: list_recipes, save_recipe, delete_recipe, launch_recipe.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.errors import AppError, not_found
from app.queue import JobQueue
from app.schemas.runs import RunCreate
from app.schemas.saved_recipes import RecipeLaunch, SavedRecipeIn, SavedRecipeOut
from app.services import audit, runs
from app.services.identity import RequestContext
from nfactory_core.config import Settings
from nfactory_core.models import Project, Run, SavedRecipe
from nfactory_core.states import RunState


async def list_recipes(session: AsyncSession, ctx: RequestContext) -> list[SavedRecipeOut]:
    rows = await session.scalars(
        select(SavedRecipe)
        .where(SavedRecipe.workspace_id.in_(ctx.workspace_ids))
        .order_by(SavedRecipe.created_at.desc())
    )
    return [SavedRecipeOut.model_validate(r) for r in rows]


async def save_recipe(
    session: AsyncSession, ctx: RequestContext, data: SavedRecipeIn
) -> SavedRecipeOut:
    workspace_id = ctx.default_workspace_id
    template_id: str | None = None
    description = data.description
    if data.run_id is not None:
        run = await runs.owned_run(session, ctx, data.run_id)
        if run.state != RunState.COMPLETED.value:
            raise AppError(
                409,
                "run_not_delivered",
                "Seul un run livré peut devenir une recette : "
                "celui-ci n'est pas terminé avec succès.",
                {"state": run.state},
            )
        project = await session.get_one(Project, run.project_id)
        workspace_id, template_id = project.workspace_id, project.template_id
        project_type, request = project.type, run.request
        if description is None:
            description = project.description
    else:
        assert data.project_type is not None and data.request is not None  # schema-checked
        project_type, request = data.project_type, data.request
    recipe = SavedRecipe(
        workspace_id=workspace_id,
        name=data.name,
        description=description or "",
        project_type=project_type,
        template_id=template_id,
        request=request,
        source_run_id=data.run_id,
        created_by=ctx.user_id,
        uses=0,
    )
    session.add(recipe)
    await session.flush()
    details = {"name": recipe.name, "project_type": project_type, "run_id": data.run_id}
    audit.record(session, ctx, "recipe.save", recipe.id, workspace_id=workspace_id, details=details)
    await session.commit()
    await session.refresh(recipe)
    return SavedRecipeOut.model_validate(recipe)


async def delete_recipe(session: AsyncSession, ctx: RequestContext, recipe_id: str) -> None:
    recipe = await _owned(session, ctx, recipe_id)
    audit.record(
        session,
        ctx,
        "recipe.delete",
        recipe.id,
        workspace_id=recipe.workspace_id,
        details={"name": recipe.name},
    )
    await session.delete(recipe)
    await session.commit()


async def launch_recipe(
    sessions: async_sessionmaker[AsyncSession],
    ctx: RequestContext,
    settings: Settings,
    queue: JobQueue,
    recipe_id: str,
    data: RecipeLaunch,
    idempotency_key: str | None,
) -> runs.Launched:
    async with sessions() as session:
        recipe = await _owned(session, ctx, recipe_id)
        key = runs.scoped_key(recipe.id, idempotency_key)
        if key is not None:
            existing = await session.scalar(select(Run).where(Run.idempotency_key == key))
            if existing is not None:
                return runs.Launched(await runs.run_detail(session, existing), created=False)
        project = Project(
            workspace_id=recipe.workspace_id,
            title=data.title or recipe.name,
            type=recipe.project_type,
            description=recipe.description,
            template_id=recipe.template_id,
        )
        session.add(project)
        await session.commit()
        project_id, request = project.id, recipe.request

    launched = await runs.launch_run(
        sessions,
        ctx,
        settings,
        queue,
        project_id,
        RunCreate(request=request),
        idempotency_key,
        key_scope=recipe_id,
    )
    async with sessions() as session:
        recipe = await session.get_one(SavedRecipe, recipe_id)
        recipe.uses += 1
        recipe.last_used_at = datetime.now(UTC)
        audit.record(
            session,
            ctx,
            "recipe.launch",
            recipe.id,
            workspace_id=recipe.workspace_id,
            details={"name": recipe.name, "run_id": launched.run.id},
        )
        await session.commit()
    return launched


async def _owned(session: AsyncSession, ctx: RequestContext, recipe_id: str) -> SavedRecipe:
    recipe = await session.scalar(
        select(SavedRecipe).where(
            SavedRecipe.id == recipe_id, SavedRecipe.workspace_id.in_(ctx.workspace_ids)
        )
    )
    if recipe is None:
        raise not_found("Recette")
    return recipe
