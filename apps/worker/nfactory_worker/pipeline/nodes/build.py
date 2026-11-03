"""build step: the recipe renders the deliverable into the run workspace."""

from dataclasses import asdict

from nfactory_worker.pipeline.nodes.common import Update, brief_of, workspace_of
from nfactory_worker.pipeline.types import FactoryState, PipelineDeps


async def build(state: FactoryState, deps: PipelineDeps) -> Update:
    recipe = deps.recipes(state["recipe_kind"])
    rendered = recipe.render(brief_of(state))
    workspace = workspace_of(deps, state)
    workspace.write_files(rendered.files)
    files = workspace.files()
    preview = rendered.preview
    return {
        "checks": [asdict(check) for check in rendered.ordered_checks()],
        "deliverables": list(rendered.deliverables),
        "preview": {"argv": list(preview.argv), "port": preview.port} if preview else None,
        "output": {"recipe": recipe.kind, "version": recipe.version, "files": files},
    }
