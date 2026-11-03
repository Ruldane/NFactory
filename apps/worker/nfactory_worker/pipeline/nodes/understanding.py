"""requirements, plan and architect steps: from a request to a validated design."""

from typing import Any

from nfactory_worker.agents import ARCHITECT, PLANNER, REQUIREMENTS
from nfactory_worker.brief import Brief, EntitySpec
from nfactory_worker.pipeline.nodes.common import Update, brief_of, call_agent
from nfactory_worker.pipeline.types import FactoryState, PipelineDeps

MAX_SOURCES = 6
MAX_EXCERPT = 1500


async def requirements(state: FactoryState, deps: PipelineDeps) -> Update:
    # Fail fast, before any model call, if this project type cannot be built yet.
    deps.recipes(state["recipe_kind"])
    payload: dict[str, Any] = {
        "request": state["request"],
        "project_type": state["project_type"],
        "title": state["title"],
    }
    previous = state.get("parent_brief")
    if previous:
        # A change request: the agent updates the delivered brief instead of starting over.
        payload["previous_brief"] = previous
    sources = await _sources(state, deps)
    if sources:
        # Untrusted data: a JSON string value, never part of the instructions.
        payload["sources"] = [
            {
                "id": s["id"],
                "path": s["path"],
                "lines": f"{s['start_line']}-{s['end_line']}",
                "section": s["section"],
                "excerpt": s["excerpt"],
            }
            for s in sources
        ]
    call = await call_agent(deps, state, "requirements", REQUIREMENTS, payload)
    # The project type and title are the user's choice; the model cannot change them.
    brief = call.output.model_copy(
        update={"project_type": state["project_type"], "title": state["title"][:120]}
    )
    if previous:
        brief = keep_delivered_identity(brief, previous)
    data = brief.model_dump(mode="json")
    output: dict[str, Any] = {"brief": data, "agent": call.agent}
    if sources is not None:
        output["sources"] = [_citation(s) for s in sources]
    return {**call.counted, "brief": data, "output": output}


def keep_delivered_identity(brief: Brief, previous: dict[str, Any]) -> Brief:
    """A child run keeps the delivered entity's table and route: data must stay readable."""
    delivered = previous.get("entity")
    if not delivered:
        return brief
    if brief.entity is None:
        return brief.model_copy(update={"entity": EntitySpec.model_validate(delivered)})
    entity = brief.entity.model_copy(
        update={"name": delivered["name"], "plural": delivered["plural"]}
    )
    return brief.model_copy(update={"entity": entity})


async def _sources(state: FactoryState, deps: PipelineDeps) -> list[dict[str, Any]] | None:
    """Search the project's knowledge base with the request; None when it has none."""
    if deps.knowledge is None:
        return None
    found = await deps.knowledge.retrieve(state["request"])
    sources = [
        {
            "id": f"S{number}",
            "document_id": str(p["document_id"]),
            "path": str(p["path"]),
            "start_line": int(p["start_line"]),
            "end_line": int(p["end_line"]),
            "section": p.get("section"),
            "excerpt": str(p["content"])[:MAX_EXCERPT],
        }
        for number, p in enumerate(found.passages[:MAX_SOURCES], start=1)
    ]
    await deps.reporter.emit(
        "knowledge.retrieved",
        {"sources": [_citation(s) for s in sources], "error": found.error},
        step="requirements",
    )
    return sources


def _citation(source: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in source.items() if key != "excerpt"}


async def plan(state: FactoryState, deps: PipelineDeps) -> Update:
    payload = {"brief": state["brief"], "recipe": state["recipe_kind"]}
    call = await call_agent(deps, state, "plan", PLANNER, payload)
    output = {"plan": call.output.model_dump(mode="json"), "agent": call.agent}
    return {**call.counted, "output": output}


async def architect(state: FactoryState, deps: PipelineDeps) -> Update:
    payload = {"brief": brief_of(state).model_dump(mode="json"), "recipe": state["recipe_kind"]}
    call = await call_agent(deps, state, "architect", ARCHITECT, payload)
    output = {"architecture": call.output.model_dump(mode="json"), "agent": call.agent}
    return {**call.counted, "output": output}
