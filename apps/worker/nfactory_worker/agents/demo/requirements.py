"""Demo answer of the requirements agent."""

import re
from typing import Any

from nfactory_worker.agents.demo.changes import answer_change
from nfactory_worker.agents.demo.domains import entity_for
from nfactory_worker.recipes.document.outlines import OUTLINES

_SENTENCES = re.compile(r"(?<=[.!?;])\s+|\n+")


def answer(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("previous_brief"):
        return answer_change(payload)
    request = " ".join(str(payload.get("request", "")).split())
    project_type = str(payload.get("project_type", ""))
    title = str(payload.get("title") or request[:80] or "Projet")
    goals = [s.strip(" .;") for s in _SENTENCES.split(request) if s.strip(" .;")][:5]

    brief: dict[str, Any] = {
        "title": title[:120],
        "summary": request[:2000],
        "project_type": project_type,
        "goals": goals,
        "open_questions": _questions(project_type),
    }
    if project_type in ("api", "webapp"):  # both serve one CRUD resource
        brief["entity"] = entity_for(request)
    if project_type == "document":
        kind = _document_kind(request)
        brief["document_kind"] = kind
        brief["sections"] = _sections(kind, goals)
    return brief


def _document_kind(request: str) -> str:
    lowered = request.lower()
    if re.search(r"proc[ée]dure|mode op[ée]ratoire|marche [àa] suivre", lowered):
        return "procedure"
    if re.search(r"rapport|bilan|compte[- ]rendu|audit", lowered):
        return "report"
    return "note"


def _sections(kind: str, goals: list[str]) -> list[dict[str, Any]]:
    # Only the first section gets content: the request itself. Inventing the rest
    # would be fabricating facts, so it stays "À compléter".
    return [
        {"title": title, "points": goals if index == 0 else []}
        for index, (title, _hint) in enumerate(OUTLINES[kind])  # type: ignore[index]
    ]


def _questions(project_type: str) -> list[str]:
    common = ["Qui utilisera ce livrable, et à quelle fréquence ?"]
    specific = {
        "api": ["Faut-il une authentification ?", "Quelle base de données en production ?"],
        "excel": ["Quels sont les vrais fichiers d'export et leurs colonnes ?"],
        "document": ["Qui valide le document avant diffusion ?"],
    }
    return common + specific.get(project_type, [])
