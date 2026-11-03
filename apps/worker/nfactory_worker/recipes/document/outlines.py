"""Default section outline per document kind, with what each section should hold."""

from nfactory_worker.brief import DocumentKind

OUTLINES: dict[DocumentKind, tuple[tuple[str, str], ...]] = {
    "procedure": (
        ("Objet", "ce que la procédure permet de faire"),
        ("Périmètre", "systèmes, équipes et situations concernés"),
        ("Prérequis", "droits, outils et vérifications avant de commencer"),
        ("Étapes", "les actions dans l'ordre, une par ligne"),
        ("Vérification", "comment confirmer que tout fonctionne"),
        ("Retour arrière", "comment annuler en cas de problème"),
        ("Contacts", "qui prévenir et qui peut aider"),
    ),
    "report": (
        ("Résumé", "les conclusions en quelques lignes"),
        ("Contexte", "pourquoi ce rapport"),
        ("Constats", "les faits observés, chiffrés si possible"),
        ("Analyse", "ce que les constats signifient"),
        ("Recommandations", "les actions proposées"),
        ("Prochaines étapes", "qui fait quoi, et quand"),
    ),
    "note": (
        ("Contexte", "la situation de départ"),
        ("Objectifs", "ce que l'on cherche à obtenir"),
        ("Proposition", "la solution proposée"),
        ("Risques", "ce qui pourrait mal tourner"),
        ("Prochaines étapes", "qui fait quoi, et quand"),
    ),
}
