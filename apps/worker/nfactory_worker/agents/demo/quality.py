"""Demo answers of the reviewer, debugger and documenter agents.

They only restate verified facts (check results, file lists). The debugger never
proposes a patch: pretending to fix code in demo mode would be a fake success.
"""

from typing import Any

_DEMO_LIMIT = "Généré en mode démo : contenu issu de modèles validés, sans IA réelle."
_LIMITS: dict[str, list[str]] = {
    "python-api": [
        "Aucune authentification : à ajouter avant toute exposition.",
        "Pas de migrations Alembic : le schéma est créé au démarrage.",
    ],
    "excel-automation": [
        "Les données fournies sont synthétiques : remplacez data/*.csv par vos exports.",
        "Les formules sont calculées par Excel à l'ouverture du fichier.",
    ],
    "document": [
        "Les sections marquées « À compléter » doivent être rédigées avant diffusion.",
    ],
}


def review(payload: dict[str, Any]) -> dict[str, Any]:
    checks = payload.get("checks", [])
    failed = [c for c in checks if not c.get("ok")]
    findings = [
        {"severity": "blocker", "message": f"{c.get('name')} en échec : {c.get('detail', '')}"}
        for c in failed
    ]
    findings += [
        {"severity": "warning", "message": limit}
        for limit in _LIMITS.get(str(payload.get("recipe")), [])
    ]
    return {"verdict": "changes_requested" if failed else "approve", "findings": findings}


def debug(payload: dict[str, Any]) -> dict[str, Any]:
    failures = [str(f) for f in payload.get("failures", [])]
    return {
        "cause": failures[0] if failures else "Cause inconnue.",
        "proposed_fix": "Mode démo : aucune correction automatique. Un moteur IA réel "
        "(phase 2) ou une intervention humaine est nécessaire.",
        "patches": [],
    }


def explain(payload: dict[str, Any]) -> dict[str, Any]:
    brief = payload.get("brief", {})
    recipe = str(payload.get("recipe", ""))
    checks = payload.get("checks", [])
    passed = [c["name"] for c in checks if c.get("ok")]
    deliverables = [str(d) for d in payload.get("deliverables", [])]
    verify = [f"Relire : {q}" for q in brief.get("open_questions", [])]
    verify.append("Ouvrir le livrable et vérifier qu'il répond à la demande initiale.")
    return {
        "summary": (
            f"NFactory a produit « {brief.get('title', '')} » avec la recette {recipe}. "
            f"Vérifications réussies : {', '.join(passed) or 'aucune'}."
        ),
        "generated": [*deliverables, f"{len(payload.get('files', []))} fichiers source"],
        "verify": verify,
        "limits": [*_LIMITS.get(recipe, []), _DEMO_LIMIT],
    }
