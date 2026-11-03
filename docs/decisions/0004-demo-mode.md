# ADR-0004 — Mode démo : vrai code, faux LLM

- Statut : accepté (2026-11-01)

## Contexte
L'installation doit fonctionner sans clé API (spec F40, §17.3), sans afficher de faux résultats.

## Décision
- Un `FakeProvider` déterministe et scriptable remplace le LLM ; il se déclare toujours `demo: true`.
- À partir de la phase 1, le Builder instancie des **templates validés** : les tests des projets générés sont réellement exécutés.
- Les données synthétiques portent `is_demo=true` et l'UI affiche « Données de démonstration ».

## Conséquences
La démo prouve la chaîne réelle (fichiers, tests, ZIP) ; seule la rédaction par un modèle est simulée.
