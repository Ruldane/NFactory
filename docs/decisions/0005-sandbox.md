# ADR-0005 — Exécution du code généré (sandbox)

- Statut : accepté ; v1 (phase 1) remplacée par la v2 en place depuis la phase 3 (2026-11-02)

## Contexte
Le code généré est non fiable (spec §8.3). Interdiction de monter `docker.sock` dans l'API ou le worker.

## Décision
- **v1 (phase 1, en place)** : service `sandbox` dédié (`apps/sandbox`).
  - Serveur HTTP en bibliothèque standard : `POST /run` avec jeton `NFACTORY_SANDBOX_TOKEN`, `GET /health`.
  - Il revalide tout : nom de workspace, exécutable sur liste blanche (`python`), arguments sans shell, timeout borné, environnement épuré.
  - Réseau Docker `internal: true` partagé avec le seul worker : pas d'Internet, pas de port publié.
  - uid 10001, système de fichiers en lecture seule (sauf `/tmp` et le volume des workspaces), `cap_drop: ALL`, `no-new-privileges`, 1 CPU, 1 Go, 256 processus.
  - Dépendances des recettes pré-installées, versions alignées sur `uv.lock`.
  - Côté worker, `SandboxRunner` implémente le même contrat `Runner` que `LocalRunner`. `LocalRunner` (sous-processus local) ne sert qu'aux tests et au développement sans Docker ; le worker l'annonce dans ses logs.
- **v2 (phase 3, en place)** : service `sandbox-supervisor` (`apps/sandbox/nfactory_sandbox`, bibliothèque standard).
  - Même contrat HTTP que la v1 (`POST /run`, jeton, validation). Statuts : 400 invalide, 401 jeton, 502 échec du moteur Docker, 503 trop de commandes en cours (4 au plus).
  - Chaque commande tourne dans un **conteneur jetable** de l'image sandbox, à la spécification figée (`containers.py`) : `NetworkMode: none`, système de fichiers en lecture seule, `CapDrop: ALL`, `no-new-privileges`, uid 10001, 1 CPU, 1 Go sans swap, 256 processus, `/tmp` de 256 Mo, journaux plafonnés à 2 Mo, `init`.
  - Seul le workspace du run est monté : sous-chemin du volume `nfactory_workspaces` (Docker Engine ≥ 26, API 1.45), avec `NoCopy` (sinon Docker donne le dossier vide à root).
  - Dépassement du délai : conteneur tué, `timed_out`. Mémoire dépassée : code 137 et message « Mémoire dépassée ». Le conteneur est toujours supprimé ; au démarrage, le superviseur supprime ceux qu'un arrêt brutal aurait laissés (étiquette `nfactory.sandbox`).
  - Le superviseur est **le seul service qui monte `docker.sock`** (§8.3 : superviseur distinct à périmètre limité). Il tourne en uid 10001 avec le groupe propriétaire du socket, en lecture seule, sans capacité, sur le réseau interne, sans port publié, et ne reçoit de `.env` que le jeton. Il ne lit les workspaces qu'en lecture seule, pour vérifier qu'un workspace existe. Aucune option de conteneur ne vient de la requête.
- **Aperçu (tâche 3.10, en place)** : l'application générée tourne dans un conteneur de longue durée, lancé par le même superviseur.
  - Même spécification figée qu'une vérification (`previews.py`), à deux différences près :
    - réseau interne `nfactory_preview`, sans Internet et sans aucun service NFactory ;
    - workspace monté en **lecture seule** : l'aperçu ne modifie jamais le livrable ; ses données de test vivent dans `/tmp` et disparaissent à l'arrêt.
  - Commande : celle que la recette déclare (`RenderedProject.preview`, ex. `python tools/preview.py`), enregistrée dans la sortie de l'étape package. L'API la relit dans le run ; la requête ne porte que l'identifiant du run. API et superviseur revérifient la liste blanche.
  - Routes du superviseur, avec le même jeton : `POST /previews`, `GET` et `DELETE /previews/<run>`. Deux aperçus au plus (503 au-delà), arrêt automatique après 15 min.
  - Aucun port publié. Le service `preview-gateway` (même image, **sans socket Docker ni secret**) est la seule entrée. Il relaie `/preview/<run>/…` vers le conteneur, par son nom, sur le réseau d'aperçu, et :
    - retire cookies et en-têtes d'authentification dans les deux sens ;
    - n'autorise que le dashboard à l'encadrer (`frame-ancestors`) ;
    - sert les aperçus sur une **autre origine** que le dashboard (127.0.0.1:8090).

## Conséquences
- Isolation réseau dès la phase 1, vérifiée dans la stack (résolution DNS impossible depuis le sandbox).
- Depuis la v2, un run ne voit plus le workspace d'un autre run, ni le réseau, ni aucun secret. Tests §19.1 contre un vrai Docker : `apps/sandbox/tests/test_isolation.py`.
- Coût : un conteneur par commande, environ une demi-seconde de plus par vérification.
- Risque assumé : le socket Docker donne au superviseur un pouvoir équivalent à root sur la VM Docker. Il est réduit par la surface minimale (jeton, liste blanche, spécification figée, aucun paramètre libre) et l'absence d'Internet ; une alternative sans socket (Docker rootless, gVisor, microVM) reste possible derrière la même interface `Executor`.
- Limite : l'espace disque d'un workspace n'a pas de quota (le volume n'en offre pas) ; `/tmp` et les journaux sont plafonnés.
- Aperçu, risque assumé : deux aperçus ouverts en même temps partagent le réseau d'aperçu et peuvent se joindre. Ce sont deux runs du même utilisateur local ; isoler chaque aperçu sur son propre réseau reste possible derrière `PreviewManager`.
- Aperçu, preuve : `test_isolation.py::test_a_preview_is_confined_and_reachable_only_on_its_network` lance un vrai aperçu et vérifie, depuis le réseau d'aperçu, l'absence d'Internet, le workspace en lecture seule et l'absence des autres runs.
