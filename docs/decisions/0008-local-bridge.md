# ADR-0008 — Pont local vers Codex, Claude Code et GitHub CLI

- Statut : accepté (2026-11-02)

## Contexte
La phase 4 relie NFactory aux outils de code installés sur l'ordinateur de l'utilisateur (spec §6.4, §6.5, D13). Ces outils gardent leur session sur la machine. Un conteneur ne doit pas prétendre en disposer, et NFactory ne doit jamais lire ni relayer leurs jetons. Le pont écoute sur `127.0.0.1` seulement, demande une autorisation explicite et n'expose aucun shell.

## Décision
- **Un processus hôte, hors Docker.** `apps/local-bridge` (`nfactory_bridge`) est écrit en bibliothèque standard Python. L'utilisateur le lance avec `scripts/bridge.ps1` ou `scripts/bridge.sh`.
  - Il refuse toute adresse d'écoute autre qu'une adresse loopback IPv4.
- **Joignable depuis l'API.** Docker Desktop livre le trafic de `host.docker.internal` sur le `127.0.0.1` de l'hôte (vérifié sur ce poste). Compose fixe `NFACTORY_BRIDGE_URL=http://host.docker.internal:8765`.
- **Appairage.**
  - Au premier démarrage, ou avec `-Pair`, le pont affiche un code à usage unique (8 caractères, 10 minutes, brûlé après 5 erreurs).
  - L'utilisateur saisit ce code dans le dashboard. L'API l'échange contre un jeton long.
  - Le jeton est chiffré dans le `SecretStore`, dans une connexion `local_bridge`, et n'est jamais renvoyé.
  - Le pont ne garde que le SHA-256 du jeton, dans le profil de l'utilisateur (`%LOCALAPPDATA%\NFactory\bridge.json`), hors du dépôt.
- **Défenses HTTP.**
  - Sans jeton, seul `GET /health` répond (`status`, `paired`, `version`).
  - Toute requête portant un en-tête `Origin` vient d'un navigateur : elle est refusée (403).
  - Un `Host` autre que `127.0.0.1`, `localhost` ou `host.docker.internal` sur le bon port est refusé (421, rebinding DNS).
  - Les corps sont limités à 8 Ko.
- **Aucune commande libre.** Chaque route exécute une action fixe. La détection lance seulement `--version` et la commande de statut officielle de chaque outil (`codex login status`, `claude auth status --json`, `gh auth status`). Aucun fichier d'authentification n'est ouvert.
- **Sortie réduite.** Seuls l'état (`not_installed`, `installed`, `needs_login`, `connected`), la version et la méthode de connexion Codex (`chatgpt` / `api_key`) quittent le pont. Le courriel, l'organisation, l'offre et la sortie brute restent sur la machine. L'API revalide ce qu'elle reçoit (schéma borné) et écarte un outil ou un état inconnu.
- **Claude Code en passage de relais seulement.** Son mode `runtime` est `blocked_by_policy` jusqu'à vérification de conformité (spec §6.5). Le mode `handoff` est disponible.
- **Travail Git sur le dépôt de l'utilisateur (tâche 4.5, `nfactory_bridge.git_workspace`).**
  - Chaque run travaille dans son propre `git worktree`, sur une nouvelle branche `nfactory/<projet>/<run>`, à partir d'un commit. Les modifications non commitées de l'utilisateur restent dans son checkout, jamais copiées ni touchées.
  - Une branche existante n'est jamais réutilisée. Les noms de projet et de run, et chaque chemin écrit, sont vérifiés (pas de `..`, de chemin absolu ni de `.git`).
  - Chaque écriture de NFactory est indexée aussitôt : l'index garde ce que NFactory a écrit. Un fichier dont la copie diffère de l'index, ou un fichier non suivi sur le chemin, a été modifié par quelqu'un d'autre : rien n'est écrit (conflit, tout ou rien). Cette comparaison passe par Git, donc la conversion des fins de ligne (`core.autocrlf`) ne crée pas de faux conflit.
  - Le manifeste et le diff se calculent contre le commit de départ. Le commit est local (`local_commit_created`), signé « NFactory ». Le retour arrière supprime le worktree et la branche, et refuse toute branche hors `nfactory/`.

## Conséquences
- Un pont arrêté est un état normal (`unreachable`), affiché avec la commande pour le lancer, et non une erreur.
- Un pont réappairé ailleurs ne reconnaît plus le jeton : l'API affiche `token_rejected` et redemande un code.
- Sous Linux sans Docker Desktop, `host-gateway` mène à l'interface du pont Docker et non au loopback : il faudra une variante documentée, par exemple un socket Unix.
