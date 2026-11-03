"""Pipeline steps, one module per group. Each node: (state, deps) -> partial update."""

from nfactory_worker.pipeline.nodes.build import build
from nfactory_worker.pipeline.nodes.delivery import docs, package, review
from nfactory_worker.pipeline.nodes.repair import debug
from nfactory_worker.pipeline.nodes.understanding import architect, plan, requirements
from nfactory_worker.pipeline.nodes.verification import checks, tests

STEP_NODES = {
    "requirements": requirements,
    "plan": plan,
    "architect": architect,
    "build": build,
    "checks": checks,
    "tests": tests,
    "review": review,
    "docs": docs,
    "package": package,
}

__all__ = ["STEP_NODES", "debug"]
