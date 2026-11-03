"""The factory run as a LangGraph graph (spec §5.2).

requirements → plan → architect → build → checks → tests → review → docs → package
(the architect runs for applications only: `nfactory_core.roster.plan_steps`)
checks / tests failing → debug → checks (at most `max_repairs` times)
Any FAILED or CANCELLED outcome ends the graph.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from nfactory_core.pipeline import step_names
from nfactory_core.roster import plan_steps
from nfactory_worker.pipeline.nodes import STEP_NODES, debug
from nfactory_worker.pipeline.nodes.common import EngineFailedError, EnginePausedError, Update
from nfactory_worker.pipeline.types import FactoryState, PipelineDeps

NodeFn = Callable[[FactoryState, PipelineDeps], Awaitable[Update]]
_STOPPED = {"FAILED", "CANCELLED"}
_VERIFYING = {"checks", "tests"}


def _as_step(step: str, fn: NodeFn, deps: PipelineDeps) -> Callable[..., Awaitable[Update]]:
    """Wrap a node with cancellation, step reporting and error capture."""

    async def node(state: FactoryState) -> Update:
        if await deps.control.cancel_requested():
            return {"outcome": "CANCELLED"}
        planned = next(p for p in plan_steps(state["project_type"]) if p.name == step)
        if not planned.active:
            await deps.reporter.step_skipped(step, planned.reason or "")
            return {}
        await deps.reporter.step_started(step)
        try:
            update = await fn(state, deps)
        except EnginePausedError:
            raise  # stops the graph; the run waits for the user (execute_run)
        except EngineFailedError as exc:
            await deps.reporter.step_failed(step, exc.message)
            return {"outcome": "FAILED", "error": exc.message}
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            await deps.reporter.step_failed(step, error)
            return {"outcome": "FAILED", "error": error}
        output: dict[str, Any] = update.pop("output", {})
        if not update.get("failed_step"):
            await deps.reporter.step_succeeded(step, output)
        return update

    return node


def _after(step: str, following: str) -> Callable[[FactoryState], str]:
    def route(state: FactoryState) -> str:
        if state.get("outcome") in _STOPPED:
            return END
        if step in _VERIFYING and state.get("failed_step"):
            return "debug"
        return following

    return route


def _after_debug(state: FactoryState) -> str:
    return END if state.get("outcome") in _STOPPED else "checks"


def build_graph(deps: PipelineDeps) -> StateGraph[FactoryState]:
    graph: StateGraph[FactoryState] = StateGraph(FactoryState)
    steps = step_names()
    for step in steps:
        graph.add_node(step, _as_step(step, STEP_NODES[step], deps))

    async def debug_node(state: FactoryState) -> Update:
        if await deps.control.cancel_requested():
            return {"outcome": "CANCELLED"}
        return await debug(state, deps)

    graph.add_node("debug", debug_node)
    graph.add_edge(START, steps[0])
    for step, following in zip(steps, [*steps[1:], END], strict=True):
        graph.add_conditional_edges(step, _after(step, following))
    graph.add_conditional_edges("debug", _after_debug)
    return graph
