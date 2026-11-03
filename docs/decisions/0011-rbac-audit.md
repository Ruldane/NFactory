# ADR-0011 — RBAC de base, journal d'audit et centre d'approbation

- Statut : accepté (2026-11-03)

## Contexte
La spec (F33, §15) demande des rôles par espace de travail (owner, admin, developer, reviewer, viewer), un journal des actions sensibles et un endroit unique où décider des approbations. Le mode local n'a qu'un utilisateur, propriétaire de son espace. Le mode équipe arrivera plus tard (SSO en phase 6), mais les droits doivent déjà être vérifiés côté serveur, et testés.

## Décision
- **Le rôle vient de l'adhésion.** `get_user_id` (dépendance FastAPI) dit qui appelle : `usr_local` en mode local. Le mode équipe authentifiera à cet endroit, et les tests le remplacent pour jouer un autre membre. `context_for` lit les adhésions de cet utilisateur : `RequestContext.roles` associe chaque espace à son rôle.
- **Une permission par action, une table explicite** (`app/services/access.py`) :

  | Rôle | read | approve | audit | build | configure |
  |---|---|---|---|---|---|
  | owner, admin | oui | oui | oui | oui | oui |
  | developer | oui | oui | | oui | |
  | reviewer | oui | oui | oui | | |
  | viewer | oui | | | | |

  - `build` : projets, runs, annulation, aperçu, tâches d'agent de code, documents de la base de connaissances.
  - `approve` : décisions sur un run en pause et publication d'une tâche d'agent.
  - `configure` : réglages, moteurs IA, catalogue de modèles, routage, réglages de la base, appairage du pont.
  - `audit` : lecture du journal.

  Ce n'est pas une échelle : un relecteur lit le journal, pas un développeur.
- **La route déclare sa permission** (`CanBuild`, `CanApprove`, `CanConfigure`, `CanAudit` dans `app/context.py`). La dépendance réduit le contexte aux espaces où le rôle l'accorde. Si l'espace par défaut n'en fait pas partie, la réponse est 403 `forbidden`, avec un message en français qui nomme le rôle. Un identifiant d'un autre espace reste un 404, comme un identifiant absent : les services filtrent déjà toute requête par `ctx.workspace_ids`.
- **Journal d'audit par espace.** `audit_log.workspace_id` (migration `8b2f4e6a9c31`, les anciennes lignes vont à `wks_local`). `app/services/audit.record` passe les détails par `redact` et écrit dans la transaction de l'action. Pour une action sur un run, l'entrée va dans l'espace du run. Les détails ne contiennent jamais une clé, un code d'appairage ou un jeton : pour un moteur, seul son type est noté. `GET /audit` est paginé à rebours (`before`, `next_before`).
- **Centre d'approbation.** `GET /approvals?status=pending|all` liste les approbations des espaces de l'appelant, avec le projet et l'état du run. La décision reste sur le run (`/runs/{id}/approvals/{id}/approve|reject`) et elle est auditée. La page `/audit` du dashboard affiche les décisions en attente : réessayer le même moteur, arrêter le run, ou ouvrir le run pour choisir un autre moteur. Elle affiche ensuite le journal. `GET /me` donne le rôle et les permissions, et le dashboard cache les boutons que le rôle n'autorise pas. Le serveur refuse de toute façon.

## Conséquences
- En mode local rien ne change : l'utilisateur local est propriétaire et a toutes les permissions.
- Les tests d'autorisation (`apps/api/tests/api/test_access.py`) créent de vrais membres viewer, reviewer, developer et admin, et vérifient 403 contre 2xx route par route, ainsi que les droits par espace.
- Une nouvelle route qui modifie quelque chose doit choisir une dépendance `Can…`. `Context` seul ne sert qu'à la lecture.
- Restent à faire : l'invitation de membres et le changement de rôle depuis l'interface (avec le mode équipe), les politiques par espace (phase 6).
