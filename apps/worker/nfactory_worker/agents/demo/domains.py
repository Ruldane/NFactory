"""Demo heuristics: known IT domains -> a plausible entity for the python-api recipe.

This is keyword matching, not understanding. It is labelled demo everywhere and is
replaced by a real model in phase 2.
"""

import re
from typing import Any

# (pattern on the lowercased request, entity as Brief JSON)
DOMAINS: tuple[tuple[re.Pattern[str], dict[str, Any]], ...] = (
    (
        re.compile(r"licen[cs]e"),
        {
            "name": "licence",
            "plural": "licences",
            "label": "Licence",
            "fields": [
                {"name": "name", "label": "Logiciel", "type": "str"},
                {"name": "vendor", "label": "Éditeur", "type": "str"},
                {"name": "seats", "label": "Postes", "type": "int"},
                {"name": "expires_on", "label": "Expiration", "type": "date"},
            ],
        },
    ),
    (
        re.compile(r"inventaire|mat[ée]riel|[ée]quipement|parc"),
        {
            "name": "equipement",
            "plural": "equipements",
            "label": "Équipement",
            "fields": [
                {"name": "name", "label": "Nom", "type": "str"},
                {"name": "serial_number", "label": "Numéro de série", "type": "str"},
                {"name": "location", "label": "Emplacement", "type": "str"},
                {"name": "purchased_on", "label": "Date d'achat", "type": "date"},
            ],
        },
    ),
    (
        re.compile(r"ticket|incident|demande"),
        {
            "name": "ticket",
            "plural": "tickets",
            "label": "Ticket",
            "fields": [
                {"name": "title", "label": "Titre", "type": "str"},
                {"name": "priority", "label": "Priorité", "type": "int"},
                {"name": "resolved", "label": "Résolu", "type": "bool"},
            ],
        },
    ),
    (
        re.compile(r"client|contact"),
        {
            "name": "client",
            "plural": "clients",
            "label": "Client",
            "fields": [
                {"name": "name", "label": "Nom", "type": "str"},
                {"name": "email", "label": "E-mail", "type": "str"},
                {"name": "city", "label": "Ville", "type": "str"},
            ],
        },
    ),
    (
        re.compile(r"t[âa]che|todo|to-do"),
        {
            "name": "tache",
            "plural": "taches",
            "label": "Tâche",
            "fields": [
                {"name": "title", "label": "Titre", "type": "str"},
                {"name": "done", "label": "Terminée", "type": "bool"},
                {"name": "due_on", "label": "Échéance", "type": "date"},
            ],
        },
    ),
)

GENERIC_ENTITY: dict[str, Any] = {
    "name": "item",
    "plural": "items",
    "label": "Élément",
    "fields": [
        {"name": "name", "label": "Nom", "type": "str"},
        {"name": "description", "label": "Description", "type": "str"},
    ],
}


def entity_for(request: str) -> dict[str, Any]:
    lowered = request.lower()
    for pattern, entity in DOMAINS:
        if pattern.search(lowered):
            return entity
    return GENERIC_ENTITY
