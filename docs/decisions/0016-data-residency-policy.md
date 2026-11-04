# ADR-0016 — Pays de traitement des moteurs et politique « UE ou local uniquement »

- Statut : accepté (2026-11-04)

## Contexte

La revue juridique (`docs/legal/revue-france.md` §2, action 5) demande deux choses :
- afficher, dans Moteurs IA, le pays où chaque fournisseur traite les données ;
- proposer un réglage « moteurs UE ou locaux uniquement ».

Choisir un moteur américain ou chinois transfère hors de l'UE le contenu des demandes : besoin, documents de la base de connaissances, code. La spec (§6.7) demande aussi d'afficher la région connue de chaque fournisseur.

## Décision

**Une table sourcée** (`nfactory_core.providers.residency`). Chaque point d'accès connu (fournisseur, région) a une entrée :
- sa zone : `local`, `eu`, `outside_eu` ou `unknown` ;
- son pays ;
- la page du fournisseur qui l'affirme, lue le 4 novembre 2026 ;
- au besoin, une condition à remplir.

Un test vérifie que chaque région de `SPECS` a son entrée et sa source. Ce qui n'est pas documenté reste `unknown`, jamais deviné. Un endpoint personnalisé est `unknown` : NFactory ne sait pas où il tourne.

Faits retenus :
- OpenAI : États-Unis par défaut. La résidence UE passe par une autre adresse (`eu.api.openai.com`), ajoutée comme région « Europe ». Elle ne vaut que pour un projet créé avec la résidence « Europe », et le calcul ne reste dans l'UE qu'avec la conservation zéro ou un contrôle approuvé par OpenAI : c'est affiché en note.
- Anthropic : stockage aux États-Unis, calcul dans tout pays disponible ; aucune option UE sur l'API.
- DeepSeek : Chine. Z.ai : Singapour, ou Chine pour `bigmodel.cn`. Moonshot : Singapour, ou Chine. MiniMax : États-Unis pour l'international, Chine pour `.cn`.
- Qwen : chaque région dit son pays. Francfort n'est dans l'UE que si l'espace Model Studio a la portée « UE » : la portée « Global » utilise la même adresse et peut calculer partout. La note le dit, et c'est à l'utilisateur de créer son espace avec la bonne portée.
- Codex et Claude Code tournent sur la machine de l'utilisateur, mais envoient le code au cloud de leur éditeur (États-Unis).

**Une politique** `eu_only`, à côté de `local_only` dans le routage de l'espace de travail (`RoutingConfig`, figée dans `runs.provider_config`). Une seule règle, `nfactory_core.routing.policy_violation`, l'applique partout où des données partent :
- au lancement d'un run (`freeze_routing`) ;
- au remplacement d'un moteur pendant un run en pause (`run_approvals`), selon la politique figée du run ;
- au choix et à l'usage d'un moteur d'embeddings (API et worker) ;
- au lancement d'une tâche d'agent de code (Codex, Claude Code).

Un moteur local passe toujours. Un moteur distant passe seulement si sa zone est `eu`. `unknown` est refusé : dans le doute, rien ne part. Erreur `eu_only_violation` (409), avec un message en français qui nomme le moteur et le pays.

**Affichage** : chaque carte de Moteurs IA montre la zone avec un glyphe et un libellé (⌂ Local, ● UE, ▲ Hors UE, ? Pays non documenté), le pays, un lien vers la source et la condition éventuelle. Chaque région du sélecteur montre sa zone.

## Non retenu

- **Bloquer seulement les fournisseurs chinois** : le critère juridique est le transfert hors UE, et les États-Unis en font partie, même avec le Data Privacy Framework (recours C-703/25 P pendant).
- **Laisser passer `unknown`** : un endpoint personnalisé peut être n'importe où.
- **Vérifier la portée d'un espace Qwen ou la résidence d'un projet OpenAI** : aucune API documentée ne le dit à NFactory. La condition est affichée et l'utilisateur en reste responsable.

## Conséquences

- La table vieillit : un fournisseur peut ouvrir ou fermer une région. Chaque entrée porte sa source pour être relue ; `docs/legal/revue-france.md` garde « à vérifier » sur les DPA et la certification DPF.
- Avec `eu_only`, les agents de code sont refusés : leur éditeur ne propose pas de traitement dans l'UE par défaut. Codex pointé vers un projet OpenAI européen n'est pas détecté, faute de moyen fiable de le savoir.
- Tests : `packages/core-py/tests/providers/test_residency.py`, `test_routing.py`, `knowledge/test_engine.py`, API `test_providers.py`, `test_routing.py`, `test_run_approvals.py`, `test_agent_tasks.py`, dashboard `providers-view` et `routing-editor`.
