"""One factory run, from the database row to the final state."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver

from nfactory_core.catalog import UnknownProjectTypeError, resolve_recipe
from nfactory_core.config import Settings
from nfactory_core.events import Notifier
from nfactory_worker.artifacts import LocalArtifactStore
from nfactory_worker.jobs.engines import NoModelConfiguredError, build_engines
from nfactory_worker.jobs.knowledge import knowledge_for
from nfactory_worker.jobs.lifecycle import claim, finish, pause_for_engine
from nfactory_worker.jobs.reporting import (
    DatabaseControl,
    DatabaseReporter,
    Sessions,
    StepHook,
)
from nfactory_worker.pipeline import PipelineDeps, RunInput, RunResult, execute_run
from nfactory_worker.recipes import Recipe, get_recipe
from nfactory_worker.runner import Runner


def recipe_kind(project_type: str, template_id: str | None) -> str:
    try:
        return resolve_recipe(project_type, template_id).kind
    except UnknownProjectTypeError:
        # The pipeline then fails with "recipe not available" and this name.
        return template_id or project_type


async def process_run(
    run_id: str,
    *,
    sessions: Sessions,
    settings: Settings,
    runner: Runner,
    recipes: Callable[[str], Recipe] = get_recipe,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
    notify: Notifier | None = None,
    after_step: StepHook | None = None,
    retry_delay_s: float = 2.0,
) -> RunResult | None:
    claimed = await claim(sessions, run_id, notify)
    if claimed is None:
        return None

    try:
        async with sessions() as session:
            engines = await build_engines(
                session, claimed.provider_config, claimed.workspace_id, settings
            )
    except NoModelConfiguredError as exc:
        result = RunResult(outcome="FAILED", error=str(exc))
        await finish(sessions, run_id, result, None, notify)
        return result

    deps = PipelineDeps(
        engines=engines,
        runner=runner,
        workspace_root=Path(settings.workspace_root),
        artifacts=LocalArtifactStore(Path(settings.artifact_root)),
        reporter=DatabaseReporter(sessions, run_id, claimed.project_id, notify, after_step),
        control=DatabaseControl(sessions, run_id),
        recipes=recipes,
        max_repairs=_limit(claimed.budget, "max_repair_attempts", settings.max_repair_attempts),
        max_llm_calls=_limit(claimed.budget, "max_llm_calls", settings.max_llm_calls_per_run),
        max_steps=_limit(claimed.budget, "max_agent_steps", settings.max_agent_steps),
        retry_delay_s=retry_delay_s,
        knowledge=await knowledge_for(sessions, claimed.workspace_id, claimed.project_id, settings),
    )
    run = RunInput(
        run_id=run_id,
        project_id=claimed.project_id,
        project_type=claimed.project_type,
        recipe_kind=recipe_kind(claimed.project_type, claimed.template_id),
        title=claimed.title,
        request=claimed.request,
        trace_id=claimed.trace_id,
        parent=claimed.parent,
    )
    result = await execute_run(deps, run, checkpointer)
    if result.outcome == "APPROVAL_PENDING":
        await pause_for_engine(sessions, run_id, result, notify)
    else:
        await finish(sessions, run_id, result, result.cost_usd, notify)
    return result


def _limit(budget: dict[str, Any], key: str, default: int) -> int:
    """A limit stored on the run wins over the worker's setting (frozen at launch)."""
    value = budget.get(key)
    return value if isinstance(value, int) and value >= 0 else default
