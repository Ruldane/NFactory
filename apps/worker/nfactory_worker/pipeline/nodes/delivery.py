"""review, docs and package steps: comment, explain, and store the delivery."""

from typing import Any

from nfactory_core.workspace import Workspace
from nfactory_worker.agents import DOCUMENTER, REVIEWER, explanation_markdown
from nfactory_worker.artifacts import zip_workspace
from nfactory_worker.changes import diff_workspaces
from nfactory_worker.pipeline.nodes.common import Update, brief_of, call_agent, workspace_of
from nfactory_worker.pipeline.nodes.verification import LEAK_SCAN
from nfactory_worker.pipeline.types import FactoryState, PipelineDeps

EXPLANATION_FILE = "EXPLICATION.md"
CHANGES_FILE = "modifications.diff"
MAX_REVIEW_DIFF = 12_000


def _all_results(state: FactoryState) -> list[dict[str, Any]]:
    results = state.get("results", {})
    return [*results.get("checks", []), *results.get("tests", [])]


async def review(state: FactoryState, deps: PipelineDeps) -> Update:
    changes, patch = await _changes(state, deps)
    checks = _all_results(state)
    scan = next((c for c in checks if c.get("name") == LEAK_SCAN), None)
    secrets = 0 if scan is None or scan["ok"] else len(str(scan["detail"]).splitlines())
    payload: dict[str, Any] = {
        "recipe": state["recipe_kind"],
        "checks": checks,
        "security": {"secrets": secrets},
        "repairs": state.get("repair_log", []),
        "files": workspace_of(deps, state).files()[:200],
    }
    if changes is not None:
        payload["changes"] = {**changes, "diff": patch[:MAX_REVIEW_DIFF]}
    call = await call_agent(deps, state, "review", REVIEWER, payload)
    output = {"review": call.output.model_dump(mode="json"), "agent": call.agent}
    return {**call.counted, "output": output, "changes": changes, "changes_patch": patch}


async def _changes(state: FactoryState, deps: PipelineDeps) -> tuple[dict[str, Any] | None, str]:
    """Child run: what changed since the delivered run (files and unified diff)."""
    parent_id = state.get("parent_run_id")
    if not parent_id:
        return None, ""
    parent = Workspace.open(deps.workspace_root, parent_id)
    if parent is None:
        return {"parent_run_id": parent_id, "available": False}, ""
    found = diff_workspaces(parent, workspace_of(deps, state))
    summary = {"parent_run_id": parent_id, **found.summary()}
    await deps.reporter.emit(
        "changes.computed",
        {
            "parent_run_id": parent_id,
            "added": len(found.added),
            "modified": len(found.modified),
            "removed": len(found.removed),
        },
        "review",
    )
    return summary, found.patch


async def docs(state: FactoryState, deps: PipelineDeps) -> Update:
    workspace = workspace_of(deps, state)
    brief = brief_of(state)
    payload = {
        "brief": brief.model_dump(mode="json"),
        "recipe": state["recipe_kind"],
        "deliverables": state.get("deliverables", []),
        "files": workspace.files(),
        "checks": _all_results(state),
    }
    call = await call_agent(deps, state, "docs", DOCUMENTER, payload)
    workspace.write_files({EXPLANATION_FILE: explanation_markdown(brief.title, call.output)})
    output = {"explanation": call.output.model_dump(mode="json"), "agent": call.agent}
    return {**call.counted, "output": output}


async def package(state: FactoryState, deps: PipelineDeps) -> Update:
    workspace = workspace_of(deps, state)
    slug = brief_of(state).slug
    run_id = state["run_id"]
    stored = [deps.artifacts.save(run_id, f"{slug}.zip", zip_workspace(workspace))]
    if state.get("changes_patch"):
        patch = state["changes_patch"].encode("utf-8")
        stored.append(deps.artifacts.save(run_id, CHANGES_FILE, patch))
    for deliverable in state.get("deliverables", []):
        name = deliverable.rsplit("/", 1)[-1]
        stored.append(deps.artifacts.save(run_id, name, workspace.read_bytes(deliverable)))
    for artifact in stored:
        await deps.reporter.artifact_saved(artifact)
        await deps.reporter.emit(
            "artifact.created",
            {"filename": artifact.filename, "size": artifact.size, "checksum": artifact.checksum},
            "package",
        )
    output: dict[str, Any] = {
        "files": workspace.files(),
        "artifacts": [{"filename": a.filename, "size": a.size} for a in stored],
    }
    if state.get("changes"):
        output["changes"] = state["changes"]
    if state.get("preview"):
        output["preview"] = state["preview"]  # the API starts it on request (sandbox)
    return {"outcome": "COMPLETED", "output": output}
