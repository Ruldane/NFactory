"""Helpers shared by pipeline nodes."""

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from pydantic import BaseModel

from nfactory_core.providers import ProviderError, with_retries
from nfactory_core.workspace import Workspace
from nfactory_worker.agents import Agent
from nfactory_worker.brief import Brief
from nfactory_worker.pipeline.types import FactoryState, PipelineDeps
from nfactory_worker.recipes import Check

Update = dict[str, Any]  # partial FactoryState plus an optional "output" for the step


class BudgetExceededError(RuntimeError):
    pass


class EngineFailedError(Exception):
    """An engine failed for good (not retryable, or retries exhausted)."""

    def __init__(self, details: dict[str, Any]) -> None:
        super().__init__(details["message"])
        self.details = details
        self.message: str = details["message"]


class EnginePausedError(EngineFailedError):
    """Same failure, but the routing says to ask the user (fallback "ask_user")."""


@dataclass(frozen=True)
class AgentCall[OutT: BaseModel]:
    output: OutT
    agent: dict[str, Any]  # meta + trace id, as recorded in events and step output
    counted: Update  # the state update that records the call against the budget


async def call_agent[OutT: BaseModel](
    deps: PipelineDeps,
    state: FactoryState,
    step: str,
    agent: Agent[OutT],
    payload: Mapping[str, Any],
) -> AgentCall[OutT]:
    """The only way nodes reach a model: checked against the run's budget, traced."""
    used = state.get("llm_calls", 0)
    if used >= deps.max_llm_calls:
        raise BudgetExceededError(
            f"Budget dépassé : {used} appel(s) aux agents sur {deps.max_llm_calls} autorisé(s)."
        )
    llm = deps.engines.for_role(agent.name)
    try:
        # Temporary errors (rate limit, timeout, outage) are retried on the same engine;
        # any other error stops here: no other engine is ever tried silently.
        result = await with_retries(
            lambda: agent.run(llm, payload), base_delay_s=deps.retry_delay_s
        )
    except ProviderError as exc:
        details = {
            "role": agent.name,
            "provider": llm.provider_name,
            "model": llm.model,
            "kind": exc.kind,
            "message": exc.message,
        }
        await deps.reporter.emit("provider.failed", details, step)
        paused = deps.engines.fallback == "ask_user"
        raise (EnginePausedError if paused else EngineFailedError)(details) from None
    data = asdict(result.meta) | {"trace_id": state.get("trace_id", "")}
    await deps.reporter.emit("agent.progress", data, step)
    counted = {"llm_calls": used + 1, "cost_usd": _add(state.get("cost_usd", 0.0), data)}
    return AgentCall(output=result.output, agent=data, counted=counted)


def _add(total: float | None, meta: Mapping[str, Any]) -> float | None:
    cost = meta.get("cost_usd")
    return None if total is None or cost is None else total + cost


def brief_of(state: FactoryState) -> Brief:
    return Brief.model_validate(state["brief"])


def workspace_of(deps: PipelineDeps, state: FactoryState) -> Workspace:
    return Workspace.create(deps.workspace_root, state["run_id"])


def checks_of(state: FactoryState) -> list[Check]:
    return [Check(**{**raw, "argv": tuple(raw["argv"])}) for raw in state.get("checks", [])]
