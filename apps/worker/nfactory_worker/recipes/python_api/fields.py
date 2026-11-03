"""How each brief field type maps to generated Python code and test data."""

from dataclasses import dataclass
from typing import Any

from nfactory_worker.brief import EntitySpec, FieldSpec, FieldType


@dataclass(frozen=True)
class TypeInfo:
    annotation: str  # Python annotation used by the model and the schema
    sa_type: str  # SQLAlchemy column type written into the migration
    sample: Any  # JSON value for the create payload
    updated: Any  # JSON value for the replace payload


TYPES: dict[FieldType, TypeInfo] = {
    "str": TypeInfo("str", "sa.String()", "Exemple", "Modifié"),
    "int": TypeInfo("int", "sa.Integer()", 3, 7),
    "float": TypeInfo("float", "sa.Double()", 9.5, 1.25),
    "bool": TypeInfo("bool", "sa.Boolean()", True, False),
    "date": TypeInfo("date", "sa.Date()", "2026-12-31", "2027-01-15"),
}

DEFAULT_ENTITY = EntitySpec(
    name="item",
    plural="items",
    label="Élément",
    fields=[
        FieldSpec(name="name", label="Nom", type="str"),
        FieldSpec(name="description", label="Description", type="str"),
    ],
)


def class_name(entity: EntitySpec) -> str:
    return "".join(part.capitalize() for part in entity.name.split("_"))


def uses_dates(entity: EntitySpec) -> bool:
    return any(field.type == "date" for field in entity.fields)


def payload(entity: EntitySpec, *, updated: bool = False) -> dict[str, Any]:
    values = {}
    for field in entity.fields:
        info = TYPES[field.type]
        value = info.updated if updated else info.sample
        values[field.name] = f"{value} {field.label}" if field.type == "str" else value
    return values
