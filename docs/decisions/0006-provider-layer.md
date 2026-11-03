# ADR-0006 — Couche fournisseurs : httpx direct, dans le cœur partagé

- Statut : accepté (2026-11-02)

## Contexte
La phase 2 branche huit fournisseurs de modèles (spec §6). L'API doit tester une connexion et découvrir les modèles ; le worker doit appeler les modèles. Les faits vérifiés sur les documentations officielles sont dans `docs/research/providers.md`.

## Décision
- **Emplacement.** Les adaptateurs vivent dans `nfactory_core.providers`, utilisé par l'API et le worker.
- **Transport.** Un seul client HTTP (`httpx`), sans SDK propriétaire.
  - Un SDK par fournisseur multiplierait les dépendances et les formats d'erreur.
  - Avec un client unique, la suite de contrat `respx` couvre tous les adaptateurs de la même façon.
- **Trois dialectes.**
  - OpenAI-compatible : OpenAI, DeepSeek, Z.ai, Kimi, Qwen, MiniMax et l'endpoint personnalisé. Un *profil* par fournisseur décrit ses écarts : JSON, `tool_choice`, usage en streaming, classement des erreurs.
  - Anthropic Messages.
  - Ollama natif.
- **Erreurs normalisées.** Chaque réponse en échec devient un `ProviderError` avec un `kind` :
  - `auth`, `quota`, `rate_limit`, `timeout`, `unavailable`, `bad_request`, `not_found`, `unsupported` ou `invalid_response` ;
  - un drapeau `retryable` et un message en français.
  - Le classement se fait par fournisseur : un 429 est tantôt un quota, tantôt une limite de débit.
- **Pas de nom de modèle en dur.** Les modèles viennent de la découverte (`list_models`) ou du catalogue administrable (`model_catalog`). Le prix d'un modèle est saisi par l'administrateur. Sans prix connu, le coût vaut « Non mesuré », jamais 0.
- **Secrets (D10).**
  - La clé est chiffrée par Fernet dans la table `secrets`. La clé Fernet est dérivée de `NFACTORY_SECRET_KEY` par HKDF.
  - `provider_connections.secret_ref` vaut `db:<id>`, ou `env:<VARIABLE>` quand la clé vient de l'environnement.
  - L'API ne renvoie jamais une clé.
- **Routage figé.** Le routage par rôle est enregistré dans l'espace de travail. Il est copié dans `runs.provider_config` au lancement, comme le budget.
  - Sans routage, le mode démo s'applique s'il est actif. Sinon, le lancement est refusé.
- **Aucun repli silencieux.** Si le fournisseur d'un rôle échoue, avec le mode `ask_user`, le run passe en `APPROVAL_PENDING` avec une approbation `provider_fallback`. L'utilisateur choisit un autre moteur, et le run reprend à son checkpoint. Avec `none`, le run échoue.
- **`LOCAL_ONLY`.** Seuls `ollama_local` et le mode démo sont acceptés. Sinon, le lancement est refusé.
- **SSRF.**
  - L'endpoint personnalisé doit viser une adresse publique en HTTPS. Une adresse privée n'est acceptée que si son hôte est listé dans `NFACTORY_ALLOWED_PRIVATE_LLM_HOSTS`.
  - Le contrôle est refait avant chaque requête, et les redirections ne sont pas suivies.
  - Ollama accepte une adresse locale par nature.

## Précisions à l'implémentation (2026-11-02)
- **Statuts.** Une connexion enregistrée vaut « À tester » ; seul un test réussi, lancé par l'utilisateur, la passe à « Connecté ». Un échec stocke un statut honnête (`invalid_credentials`, `quota_exceeded`, `unreachable`…) et son message. Toute modification de configuration remet « À tester ».
- **Test sans découverte.** Z.ai et Qwen ne publient pas de liste de modèles : le test appelle le premier modèle du catalogue avec un jeton ; sans modèle au catalogue, le statut vaut « Modèle requis ».
- **Catalogue partagé.** `model_catalog` est propre à l'instance (une ligne par type de fournisseur et modèle), pas à l'espace de travail : en mode local il n'y en a qu'un. À revoir avec le multi-utilisateur (phase 6).
- **Réessais.** Seules les erreurs `rate_limit`, `timeout` et `unavailable` sont réessayées, sur le même moteur (3 tentatives, attente exponentielle bornée, `Retry-After` respecté). Toute autre erreur arrête l'appel.
- **Reprise après décision.** L'étape en échec n'est pas enregistrée dans le checkpoint : après l'accord, le run reprend à cette étape, sans rejouer les précédentes. L'accord remplace le moteur en échec dans tous les rôles qui l'utilisaient, ou le garde (nouvel essai). Le worker ARQ ne conserve pas les résultats de job (`keep_result: 0`), sinon la remise en file sous le même identifiant serait ignorée.
- **Démo.** Le moteur de démonstration est un fournisseur `demo` comme les autres dans `provider_config` ; un run qui l'utilise est marqué `is_demo`.

## Conséquences
- Ajouter un fournisseur OpenAI-compatible demande un profil et ses tests de contrat, sans nouveau code de transport.
- Limite connue : une résolution DNS peut changer entre le contrôle et la connexion (DNS rebinding). Le contrôle refait avant chaque requête réduit ce risque sans le supprimer.
- Codex et Claude Code (famille B, phase 4) restent hors de cette couche : ce ne sont pas des appels de complétion.
