# ADR-0002 — Paquet partagé `nfactory_core` et pilote psycopg unique

- Statut : accepté (2026-11-01)

## Contexte
L'API et le worker manipulent les mêmes tables et les mêmes états. Le checkpointer LangGraph pour PostgreSQL utilise psycopg 3. La spec proposait `asyncpg` pour SQLAlchemy.

## Décision
- `packages/core-py` contient uniquement ce qui est partagé : modèles, machine d'états, contrat d'événements, configuration.
- Un seul pilote, **psycopg 3** (`postgresql+psycopg://`), pour SQLAlchemy (async et sync/Alembic) et LangGraph.

## Conséquences
Pas de duplication de modèles ; une seule pile réseau PostgreSQL. Sous Windows, psycopg async exige une boucle `SelectorEventLoop` : réglée dans `conftest.py` et `app/bootstrap.py` (les conteneurs Linux ne sont pas concernés).
