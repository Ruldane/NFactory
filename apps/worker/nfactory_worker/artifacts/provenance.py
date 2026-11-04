"""AI-generated marking of a delivery (AI Act art. 50(2), ADR-0014).

The manifest is machine-readable: a fixed flag, the IPTC "digital source type" term
for AI-generated content, the engine of each agent role, and the sha256 of every
delivered file. It holds no timestamp, so packaging the same workspace twice still
yields the same ZIP bytes; the run id ties it to the run's own dated record.
"""

import hashlib
from typing import TYPE_CHECKING, Any

from nfactory_core.workspace import Workspace

if TYPE_CHECKING:  # recipes import AI_NOTICE from here: keep this module dependency-free
    from nfactory_worker.agents import Engines

PROVENANCE_FILE = ".nfactory/provenance.json"
SCHEMA = "nfactory.provenance/1"
GENERATOR = "NFactory"
DIGITAL_SOURCE_TYPE = "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"
AI_NOTICE = "Contenu généré par IA avec NFactory : relisez-le et testez-le avant tout usage."

# Run internals (JUnit reports...) are not delivered, so they are neither zipped nor listed.
INTERNAL_PREFIX = ".nfactory/"


def delivered_files(workspace: Workspace) -> list[str]:
    return [path for path in workspace.files() if not path.startswith(INTERNAL_PREFIX)]


def provenance_manifest(
    workspace: Workspace,
    *,
    run_id: str,
    project_type: str,
    recipe_kind: str,
    engines: "Engines",
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "ai_generated": True,
        "digital_source_type": DIGITAL_SOURCE_TYPE,
        "generator": GENERATOR,
        "notice": AI_NOTICE,
        "run_id": run_id,
        "project_type": project_type,
        "recipe": recipe_kind,
        "engines": [
            {"role": role, "provider": llm.provider_name, "model": llm.model, "demo": llm.demo}
            for role, llm in sorted(engines.llms.items())
        ],
        "files": [
            {"path": path, "sha256": hashlib.sha256(workspace.read_bytes(path)).hexdigest()}
            for path in delivered_files(workspace)
        ],
    }
