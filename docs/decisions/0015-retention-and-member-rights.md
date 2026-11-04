# ADR-0015 — Rétention des données et droits des membres

- Statut : accepté (2026-11-04)

## Contexte

La revue juridique (`docs/legal/revue-france.md`, action 3) relève deux manques RGPD :
- rien n'est jamais supprimé : runs, événements, livrables et journal d'audit s'accumulent sans limite (art. 5(1)(e), limitation de la conservation) ;
- un membre ne peut ni obtenir ses données (art. 15 et 20) ni les faire effacer (art. 17), et un projet ne se supprime pas.

Contraintes :
- seul le worker écrit dans les volumes `artifacts` et `workspaces` (l'API voit les workspaces en lecture seule) ;
- les points de reprise LangGraph (`checkpoints*`, clé `thread_id` = id du run) contiennent l'état du run, donc la demande de l'utilisateur ;
- le journal d'audit a sa propre finalité (sécurité, intérêt légitime) : il survit à ce qu'il décrit.

## Décision

**Politique de rétention par espace de travail** (`workspaces.data_policy["retention"]`, `nfactory_core.retention`) :
- `runs_days` : un run terminé (`COMPLETED`, `PARTIAL`, `FAILED`, `CANCELLED`) depuis plus de N jours est supprimé, avec ses étapes, événements, approbations et livrables. Bornes 7 à 3650 jours.
- `audit_days` : les entrées d'audit plus vieilles que N jours sont supprimées. Bornes 30 à 3650 jours. La CNIL recommande de garder les journaux de 6 mois à 1 an.
- Valeur absente = tout garder (défaut). NFactory ne supprime rien tant que le propriétaire n'a pas choisi une durée. Une valeur enregistrée illisible vaut aussi « tout garder » : dans le doute, ne rien effacer.
- Un run actif (en cours, en attente, en pause) n'est jamais purgé.
- Toujours actif, sans réglage : les sessions SSO expirées ou révoquées et les tentatives de connexion expirées sont supprimées (minimisation).
- La purge écrit une entrée d'audit `retention.purge` avec les nombres supprimés, sans contenu.

**Base d'abord, fichiers ensuite.** Toute suppression (purge, projet supprimé) efface d'abord les lignes. Ensuite, la tâche du worker `apply_retention` (quotidienne, et au démarrage) balaie :
- les dossiers `run_*` des volumes `artifacts` et `workspaces` qui n'ont plus de run en base ;
- les lignes LangGraph dont le `thread_id` n'est plus un run.
La base reste la seule source de vérité. Une suppression faite par l'API (qui ne peut pas écrire dans `workspaces`) est donc finie au balayage suivant, et un balayage interrompu reprend au suivant.

**Droits d'un membre** :
- `GET /me/export` (tout membre) : ses données en JSON. On y trouve son profil, ses adhésions avec rôle, ses sessions (dates seulement, jamais le hash du jeton), les entrées d'audit dont il est l'auteur et les approbations qu'il a demandées ou décidées. Les runs et projets ne sont rattachés à aucun membre : ce sont des données de l'espace de travail.
- `GET /members` et `DELETE /members/{user_id}` (`CanConfigure`) : l'effacement retire l'adhésion à cet espace et révoque les sessions. Si le membre n'a plus d'autre adhésion, son identité est anonymisée : e-mail, identifiant SSO et identité locale vidés, nom remplacé par « Membre effacé ». La ligne `users` reste, pour que les entrées d'audit et les approbations gardent une référence, désormais pseudonyme. Refus : soi-même (`cannot_erase_self`), le propriétaire d'un espace (`owner_cannot_be_erased`).
- `DELETE /projects/{id}` (`CanConfigure`) : supprime le projet, ses runs, livrables, documents et vecteurs. Refusé tant qu'un run du projet est actif (`project_busy`).
- Chaque action est auditée : `settings.retention`, `member.export`, `member.erased`, `project.deleted`.

## Non retenu

- **Supprimer la ligne `users`** : les approbations perdraient leur référence (`SET NULL`), et l'audit pointerait vers un identifiant inconnu. L'anonymisation suffit à l'art. 17 : il ne reste rien qui identifie la personne.
- **Effacer les entrées d'audit d'un membre effacé** : le journal sert à la sécurité et doit rester complet. Ses entrées gardent un identifiant devenu pseudonyme ; la durée `audit_days` les fait disparaître ensuite.
- **Une durée par défaut** : supprimer des données sans que le propriétaire l'ait choisi serait une surprise. L'écran Réglages propose les durées.
- **Supprimer les fichiers depuis l'API** : il faudrait lui donner l'écriture sur `workspaces`, qu'elle n'a pas aujourd'hui.

## Conséquences

- Un membre effacé qui se reconnecte par Google, avec un domaine encore admis, revient comme un nouveau membre : il faut aussi le retirer de la liste d'admission (`.env`).
- Tests : `packages/core-py/tests/test_retention.py`, `apps/worker/tests/jobs/test_retention.py` (purge, balayage), `apps/api/tests/api/test_retention_settings.py`, `test_member_rights.py`, `test_project_deletion.py`, dashboard `settings-view`, `members-section`, `project-list` et `confirm-button`.
