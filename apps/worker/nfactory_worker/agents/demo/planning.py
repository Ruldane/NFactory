"""Demo answers of the planner and architect agents, derived from the recipe."""

from typing import Any

_COMPONENTS: dict[str, list[tuple[str, str]]] = {
    "python-api": [
        ("app/models.py", "Table SQLAlchemy de la ressource"),
        ("app/schemas.py", "Validation des entrées et sorties (Pydantic)"),
        ("app/routes.py", "Routes CRUD et erreurs 404"),
        ("app/main.py", "Application FastAPI, santé et OpenAPI"),
        ("tests/", "Tests de contrat de l'API"),
    ],
    "excel-automation": [
        ("data/", "Exports CSV d'exemple, à remplacer"),
        ("build_report.py", "Fusion des exports et écriture du classeur"),
        ("Onglet KPI", "Indicateurs calculés par formules"),
        ("tests/", "Recalcul des formules depuis les CSV"),
    ],
    "document": [
        ("content/document.md", "Source éditable du document"),
        ("content/outline.json", "Plan attendu : titre et sections"),
        ("build_document.py", "Rendu Word (.docx)"),
        ("tests/", "Contrôle de structure du document"),
    ],
}

_DECISIONS: dict[str, list[str]] = {
    "python-api": ["SQLite par défaut pour démarrer sans serveur ; DATABASE_URL pour changer."],
    "excel-automation": ["Formules Excel plutôt que valeurs figées : le classeur reste juste."],
    "document": ["Markdown comme source : modifiable sans Word, régénérable à l'identique."],
}


def plan(payload: dict[str, Any]) -> dict[str, Any]:
    brief = payload.get("brief", {})
    recipe = str(payload.get("recipe", ""))
    steps = [
        ("T1", "Structurer le livrable", f"Créer la structure de la recette {recipe}."),
        ("T2", "Produire le contenu", "Générer les fichiers à partir du besoin."),
        ("T3", "Vérifier", "Lancer l'analyse statique, la génération et les tests."),
        ("T4", "Documenter", "Écrire le README et l'explication."),
    ]
    tasks = [
        {
            "id": task_id,
            "title": title,
            "description": description,
            "depends_on": [f"T{int(task_id[1:]) - 1}"] if task_id != "T1" else [],
            "acceptance_criteria": [f"{title} : vérifié par le runner"],
            "risk": "low",
        }
        for task_id, title, description in steps
    ]
    return {
        "project_kind": str(brief.get("project_type", "")),
        "summary": f"Produire « {brief.get('title', '')} » avec la recette {recipe}.",
        "tasks": tasks,
        "requested_tools": ["python"],
        "requires_approval": False,
    }


def architecture(payload: dict[str, Any]) -> dict[str, Any]:
    recipe = str(payload.get("recipe", ""))
    components = _COMPONENTS.get(recipe, [("projet", "Livrable")])
    return {
        "components": [{"name": n, "responsibility": r} for n, r in components],
        "decisions": _DECISIONS.get(recipe, []),
    }
