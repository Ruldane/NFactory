"""Structured requirements produced by the requirements agent and consumed by recipes.

The brief comes from an LLM, so anything that becomes code (entity and field names)
is validated as a safe Python identifier. Free text only ever enters generated code
as an escaped literal (see recipes.rendering.py_literal).
"""

import keyword
import re
import unicodedata
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, field_validator

FieldType = Literal["str", "int", "float", "bool", "date"]
DocumentKind = Literal["procedure", "report", "note"]

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
# `id` is the generated primary key; the others would shadow names imported by
# generated code once capitalised into a class name (e.g. "base" -> Base).
_RESERVED = frozenset({"id", "base", "session", "query", "field", "router", "app", "mapped"})


def _safe_identifier(value: str) -> str:
    if not _IDENTIFIER.fullmatch(value) or keyword.iskeyword(value) or value in _RESERVED:
        raise ValueError(f"not a safe identifier: {value!r}")
    return value


Identifier = Annotated[str, AfterValidator(_safe_identifier)]
Label = Annotated[str, Field(min_length=1, max_length=80)]


class FieldSpec(BaseModel):
    name: Identifier
    label: Label
    type: FieldType


class EntitySpec(BaseModel):
    name: Identifier  # singular, e.g. "licence"
    plural: Identifier  # e.g. "licences"; used for the table and the URL
    label: Label  # French, e.g. "Licence"
    fields: list[FieldSpec] = Field(min_length=1, max_length=12)

    @field_validator("fields")
    @classmethod
    def _unique_names(cls, fields: list[FieldSpec]) -> list[FieldSpec]:
        names = [f.name for f in fields]
        if len(names) != len(set(names)):
            raise ValueError("field names must be unique")
        return fields


class SectionSpec(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=120)]
    points: list[str] = Field(default_factory=list, max_length=30)


class Brief(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=120)]
    summary: Annotated[str, Field(max_length=2000)]
    project_type: str
    goals: list[str] = Field(default_factory=list, max_length=20)
    entity: EntitySpec | None = None  # data-centric recipes (API)
    document_kind: DocumentKind = "note"  # document recipe
    sections: list[SectionSpec] = Field(default_factory=list, max_length=20)
    open_questions: list[str] = Field(default_factory=list, max_length=20)

    @property
    def slug(self) -> str:
        ascii_title = unicodedata.normalize("NFKD", self.title).encode("ascii", "ignore").decode()
        slug = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")[:50].strip("-")
        return slug or "projet"
