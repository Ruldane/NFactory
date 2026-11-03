"""Eval scenarios (spec §14.2): one TOML file per suite under `evals/datasets/`, each a
list of `[[case]]` tables. A case is a request plus what a correct delivery must show."""

import re
import tomllib
from collections import Counter
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

from nfactory_core.catalog import UnknownProjectTypeError, recipe_for_type

_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class CaseError(ValueError):
    """A scenario file that cannot be trusted to measure anything."""


@dataclass(frozen=True)
class Expect:
    outcome: str = "COMPLETED"
    entity: str | None = None  # brief.entity.name
    fields: tuple[str, ...] = ()  # in brief.entity.fields
    document_kind: str | None = None
    files: tuple[str, ...] = ()  # rendered files that must exist
    contains: dict[str, tuple[str, ...]] = field(default_factory=dict)  # file -> texts
    min_tests: int = 0  # passing tests in the JUnit reports
    deliverables: tuple[str, ...] = ()  # artifact suffixes, e.g. ".xlsx"
    cited: tuple[str, ...] = ()  # knowledge paths the requirements step must cite
    forbidden_calls: tuple[str, ...] = ()  # never called in generated Python
    forbidden_commands: tuple[str, ...] = ()  # never in a command the runner ran
    secret_absent: bool = False  # the generated {secret} never stored nor delivered
    security_findings: bool | None = None  # True: the secret scan must flag something
    max_diff_lines: int | None = None  # change requests: size of modifications.diff


@dataclass(frozen=True)
class Case:
    id: str
    suite: str
    project_type: str
    request: str
    title: str = "Projet"
    tags: tuple[str, ...] = ()
    parent_request: str | None = None  # set: the case is a change request on it
    knowledge: tuple[dict[str, Any], ...] = ()  # passages the knowledge base returns
    expect: Expect = field(default_factory=Expect)


_CASE_KEYS = {f.name for f in fields(Case)} - {"suite"}
_EXPECT_KEYS = {f.name for f in fields(Expect)}


def load_cases(directory: Path) -> list[Case]:
    cases: list[Case] = []
    seen: set[str] = set()
    for path in sorted(directory.glob("*.toml")):
        with path.open("rb") as handle:
            try:
                data = tomllib.load(handle)
            except tomllib.TOMLDecodeError as exc:
                raise CaseError(f"{path.name} : TOML invalide ({exc})") from exc
        for raw in data.get("case", []):
            case = _case(path.stem, raw, path.name)
            if case.id in seen:
                raise CaseError(f"{path.name} : identifiant en double « {case.id} »")
            seen.add(case.id)
            cases.append(case)
    return cases


def suite_counts(cases: list[Case]) -> dict[str, int]:
    return dict(Counter(case.suite for case in cases))


def _case(suite: str, raw: dict[str, Any], where: str) -> Case:
    case_id = str(raw.get("id", ""))
    if not _ID.match(case_id):
        raise CaseError(f"{where} : identifiant invalide « {case_id} »")
    _known(raw, _CASE_KEYS, f"{where} / {case_id}")
    if not str(raw.get("request", "")).strip():
        raise CaseError(f"{where} / {case_id} : request manquante")
    project_type = str(raw.get("project_type", ""))
    try:
        recipe_for_type(project_type)
    except UnknownProjectTypeError as exc:
        raise CaseError(f"{where} / {case_id} : type inconnu « {project_type} »") from exc
    expect = raw.get("expect", {})
    _known(expect, _EXPECT_KEYS, f"{where} / {case_id} / expect")
    return Case(
        id=case_id,
        suite=suite,
        project_type=project_type,
        request=str(raw["request"]),
        title=str(raw.get("title", "Projet")),
        tags=tuple(raw.get("tags", ())),
        parent_request=raw.get("parent_request"),
        knowledge=tuple(raw.get("knowledge", ())),
        expect=_expect(expect),
    )


def _expect(raw: dict[str, Any]) -> Expect:
    values: dict[str, Any] = {
        key: tuple(value) if isinstance(value, list) else value
        for key, value in raw.items()
        if key != "contains"
    }
    values["contains"] = {path: tuple(texts) for path, texts in raw.get("contains", {}).items()}
    return Expect(**values)


def _known(table: dict[str, Any], allowed: set[str], where: str) -> None:
    unknown = sorted(set(table) - allowed)
    if unknown:
        raise CaseError(f"{where} : clé inconnue {', '.join(unknown)}")
