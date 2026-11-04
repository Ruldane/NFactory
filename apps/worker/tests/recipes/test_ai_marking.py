"""AI-generated marking inside the delivered project (AI Act art. 50, ADR-0014): every
README says it, and so does the header of a delivered script."""

import pytest

from nfactory_worker.artifacts import AI_NOTICE
from nfactory_worker.brief import Brief
from nfactory_worker.recipes import get_recipe, registered_kinds

BRIEF = Brief(title="Suivi des licences", summary="Suivre les licences.", project_type="api")


@pytest.mark.parametrize("kind", sorted(registered_kinds()))
def test_every_readme_says_the_project_was_generated_by_ai(kind: str) -> None:
    readme = str(get_recipe(kind).render(BRIEF).files["README.md"])

    assert AI_NOTICE in readme


def test_the_delivered_powershell_script_says_so_in_its_help() -> None:
    rendered = get_recipe("powershell-automation").render(BRIEF)
    script = next(path for path in rendered.deliverables if path.endswith(".ps1"))

    content = rendered.files[script]
    text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
    header = text.split("#>", 1)[0]

    assert f".NOTES\n    {AI_NOTICE}" in header
