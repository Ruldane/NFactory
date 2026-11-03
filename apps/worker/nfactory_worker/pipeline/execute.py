"""Run (or resume) one factory run.

With a checkpointer, the graph state is saved after every step under the run id, so a
crashed worker resumes at the step that was interrupted instead of starting over.
"""

from typing import Any, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.errors import GraphRecursionError

from nfactory_worker.pipeline.graph import build_graph
from nfactory_worker.pipeline.nodes.common import EnginePausedError
from nfactory_worker.pipeline.types import FactoryState, Outcome, PipelineDeps, RunInput, RunResult


async def execute_run(
    deps: PipelineDeps,
    run: RunInput,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> RunResult:
    graph = build_graph(deps).compile(checkpointer=checkpointer)
    config: RunnableConfig = {
        "configurable": {"thread_id": run.run_id},
        "recursion_limit": deps.max_steps,
    }
    inputs: FactoryState | None = _initial_state(run)
    if checkpointer is not None:
        snapshot = await graph.aget_state(config)
        if snapshot.values:
            if not snapshot.next:  # already finished: report the stored result again
                return _result(cast(FactoryState, snapshot.values))
            inputs = None  # resume from the last checkpoint
    try:
        final = await graph.ainvoke(inputs, config)
    except EnginePausedError as paused:
        # The failed step was not checkpointed: after the user's decision the run
        # resumes from that step, with the steps before it kept.
        return RunResult(outcome="APPROVAL_PENDING", error=paused.message, pause=paused.details)
    except GraphRecursionError:
        return RunResult(
            outcome="FAILED",
            error=f"Limite de {deps.max_steps} étapes atteinte (MAX_AGENT_STEPS) : run arrêté.",
        )
    return _result(cast(FactoryState, final))


def _initial_state(run: RunInput) -> FactoryState:
    return {
        "run_id": run.run_id,
        "project_id": run.project_id,
        "project_type": run.project_type,
        "recipe_kind": run.recipe_kind,
        "title": run.title,
        "request": run.request,
        "trace_id": run.trace_id,
        "llm_calls": 0,
        "cost_usd": 0.0,
        "repairs": 0,
        "results": {},
        "failed_step": None,
        "failures": [],
        "parent_run_id": run.parent.run_id if run.parent else None,
        "parent_brief": run.parent.brief if run.parent else None,
    }


def _result(state: FactoryState) -> RunResult:
    outcome = cast(Outcome, state.get("outcome") or "FAILED")
    error = state.get("error")
    if outcome == "FAILED" and not error:
        error = "Le run s'est arrêté sans résultat."
    return RunResult(outcome=outcome, error=error, cost_usd=state.get("cost_usd"))
