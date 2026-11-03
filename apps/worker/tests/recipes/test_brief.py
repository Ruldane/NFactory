"""The Brief is LLM output: identifiers that end up in generated code are strictly checked."""

import pytest
from pydantic import ValidationError

from nfactory_worker.brief import Brief, EntitySpec, FieldSpec


def entity(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "name": "licence",
        "plural": "licences",
        "label": "Licence",
        "fields": [{"name": "name", "label": "Nom", "type": "str"}],
    }
    return data | overrides


def test_valid_brief_parses() -> None:
    brief = Brief.model_validate(
        {"title": "Licences", "summary": "Suivi", "project_type": "api", "entity": entity()}
    )
    assert brief.entity is not None
    assert brief.entity.fields[0] == FieldSpec(name="name", label="Nom", type="str")


@pytest.mark.parametrize(
    "name", ["Licence", "1abc", "a-b", "x; import os", "", "class", "id", "base"]
)
def test_entity_and_field_names_must_be_safe_identifiers(name: str) -> None:
    with pytest.raises(ValidationError):
        EntitySpec.model_validate(entity(name=name))
    with pytest.raises(ValidationError):
        FieldSpec.model_validate({"name": name, "label": "x", "type": "str"})


def test_unknown_field_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        FieldSpec.model_validate({"name": "x", "label": "x", "type": "blob"})


def test_entity_needs_at_least_one_field_and_unique_names() -> None:
    with pytest.raises(ValidationError):
        EntitySpec.model_validate(entity(fields=[]))
    dup = [{"name": "a", "label": "A", "type": "str"}] * 2
    with pytest.raises(ValidationError):
        EntitySpec.model_validate(entity(fields=dup))


def test_slug_is_ascii_and_never_empty() -> None:
    assert Brief(title="Rapport KPI hebdo é!", summary="", project_type="excel").slug == (
        "rapport-kpi-hebdo-e"
    )
    assert Brief(title="!!!", summary="", project_type="excel").slug == "projet"
