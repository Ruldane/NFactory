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
  - Les corps sont limités à 32 Ko (une tâche fait au plus 4 000 caractères).
- **Aucune commande libre.** Chaque route exécute une action fixe. La détection lance seulement `--version` et la commande de statut officielle de chaque outil (`codex login status`, `claude auth status --json`, `gh auth status`). Aucun fichier d'authentification n'est ouvert.
- **Sortie réduite.** Seuls l'état (`not_installed`, `installed`, `needs_login`, `connected`), la version et la méthode de connexion Codex (`chatgpt` / `api_key`) quittent le pont. Le courriel, l'organisation, l'offre et la sortie brute restent sur la machine. L'API revalide ce qu'elle reçoit (schéma borné) et écarte un outil ou un état inconnu.
- **Claude Code en passage de relais seulement.** Son mode `runtime` est `blocked_by_policy` jusqu'à vérification de conformité (spec §6.5). Le mode `handoff` est disponible.
- **Travail Git sur le dépôt de l'utilisateur (tâche 4.5, `nfactory_bridge.git_workspace`).**
  - Chaque run travaille dans son propre `git worktree`, sur une nouvelle branche `nfactory/<projet>/<run>`, à partir d'un commit. Les modifications non commitées de l'utilisateur restent dans son checkout, jamais copiées ni touchées.
  - Une branche existante n'est jamais réutilisée. Les noms de projet et de run, et chaque chemin écrit, sont vérifiés (pas de `..`, de chemin absolu ni de `.git`).
  - Chaque écriture de NFactory est indexée aussitôt : l'index garde ce que NFactory a écrit. Un fichier dont la copie diffère de l'index, ou un fichier non suivi sur le chemin, a été modifié par quelqu'un d'autre : rien n'est écrit (conflit, tout ou rien). Cette comparaison passe par Git, donc la conversion des fins de ligne (`core.autocrlf`) ne crée pas de faux conflit.
  - Le manifeste et le diff se calculent contre le commit de départ. Le commit est local (`local_commit_created`), signé « NFactory ». Le retour arrière supprime le worktree et la branche, et refuse toute branche hors `nfactory/`.
- **Dépôts autorisés (tâche 4.3, `nfactory_bridge.repos`).** L'utilisateur les déclare depuis son terminal (`bridge.ps1 -Allow <dossier>`, `-Revoke <id>`, `-Repos`). Le pont garde la liste dans `repos.json`, à côté de `bridge.json`. Le navigateur et l'API ne voient qu'un identifiant et un nom, jamais un chemin : aucune requête ne peut désigner un dossier.
- **Codex piloté (tâche 4.3, `codex_runtime`, `tasks`).**
  - Chaque tâche exige `consent: true` dans la requête, envoyé seulement par la case d'accord du dashboard ; sinon 403.
  - Voie retenue : `codex exec --json`, plus simple qu'`app-server` pour un petit patch non interactif. L'argv est fixe et la tâche passe par l'entrée standard, jamais par la ligne de commande : `--sandbox workspace-write` avec `sandbox_workspace_write.network_access=false`, `approval_policy=never`, `--ephemeral`, `--ignore-user-config`, `--cd <worktree>`, et `--enable experimental_windows_sandbox` sous Windows. `--ignore-user-config` écarte le modèle et les options personnelles ; la connexion reste celle de Codex (`CODEX_HOME`), que le pont ne lit jamais.
  - Le pont lance le `codex` le plus récent du PATH (`--version`), pas le premier trouvé. Un binaire `.cmd` passe par `cmd.exe` : l'argv est alors refusé s'il contient un caractère que `cmd` interprète.
  - Chaque tâche travaille dans un worktree et sur une branche `nfactory/<dépôt>/<tâche>` (règles de 4.5). Une seule tâche tourne à la fois ; délai de 30 minutes ; l'annulation tue l'arbre de processus.
  - Seuls des événements réduits quittent le pont : type, message de l'agent, commande et code de sortie, fichiers touchés, usage en jetons. Jamais la sortie des commandes, ni le raisonnement. À la fin : manifeste et diff (plafonné) contre le commit de départ. Rien n'est commité ni poussé ; « Abandonner » supprime worktree et branche.
- **Relais Claude Code (tâche 4.4).** Le pont prépare un worktree et un brief, écrit à côté du worktree et jamais dedans. Il ne lance aucun agent : `bridge.ps1 -Handoff <tâche>` affiche la commande `claude` officielle, que l'utilisateur lance lui-même avec son compte (spec §6.5). Ensuite, `collect` importe le manifeste et le diff.
- **Le code d'un agent se teste dans le sandbox, jamais sur le pont (tâche 4.4).** Le pont ne fait que remettre les fichiers suivis par Git (`snapshot`, bornés). Le worker les copie dans un espace jetable et lance pytest par le superviseur du sandbox ; le verdict vient du rapport JUnit. Le worker lit lui-même le jeton du pont dans le `SecretStore` (`nfactory_core.local_bridge`) ; il joint le pont par `host.docker.internal`, comme l'API.
- **Publication sur GitHub (tâche 4.6, `nfactory_bridge.github`).**
  - Deux autorisations distinctes. L'utilisateur autorise d'abord le dépôt à la publication depuis son terminal (`bridge.ps1 -AllowPush <id>`) : le pont lit le remote `origin` et ne garde que son `owner/nom` GitHub ; c'est la seule cible possible. Puis, pour chaque tâche, une approbation dans le dashboard, séparée du lancement de l'agent : la route `POST /tasks/<id>/publish` exige `approve: true` (sinon 403), et l'API l'inscrit dans `audit_log`.
  - Le pont fait un commit local sur la branche de la tâche, pousse cette branche seule (`refs/heads/nfactory/…:` la même, jamais forcé), puis ouvre une PR **brouillon** par le `gh` de l'utilisateur. L'argv est fixe ; le corps de la PR passe par l'entrée standard ; seules les branches `nfactory/…` sont nommées ; aucune commande ne fusionne.
  - Le corps de la PR est écrit par l'API : agent, branche, fichiers changés, verdict du sandbox (rapport JUnit, pas l'avis de l'agent) et limites.
  - Les quatre statuts (`local_commit_created`, `pushed`, `pr_created`, `merged`) sont relus à chaque lecture : le commit dans le worktree, la branche par `gh api repos/…/git/ref/heads/…`, la PR par `gh pr list --head`. La sortie brute de `gh` ne quitte jamais le pont ; une erreur devient un message fixe.

## Conséquences
- Un pont arrêté est un état normal (`unreachable`), affiché avec la commande pour le lancer, et non une erreur.
- Un pont réappairé ailleurs ne reconnaît plus le jeton : l'API affiche `token_rejected` et redemande un code.
- Sous Linux sans Docker Desktop, `host-gateway` mène à l'interface du pont Docker et non au loopback : il faudra une variante documentée, par exemple un socket Unix.
