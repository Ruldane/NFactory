# NFACTORY — Master Product & Engineering Blueprint

> **Version :** 1.0 — 1er novembre 2026  
> **Statut :** cahier des charges exécutable pour Claude Code  
> **Langue du produit :** français par défaut, anglais disponible  
> **Objectif :** construire une **AI Software Factory local-first, multi-agents, multi-providers**, avec dashboard web, capable de créer, modifier, tester, documenter, prévisualiser et livrer de véritables projets logiciels.

---

# 0. INSTRUCTIONS PRIORITAIRES POUR CLAUDE CODE

**Tu es le lead engineer chargé de CONSTRUIRE NFactory, pas seulement d'en produire le squelette ou la documentation.** Ce document constitue le cahier des charges principal. Quand il est ouvert dans un dépôt, applique immédiatement ces consignes :

1. Inspecte le dépôt et l'environnement (`git status`, versions Python/Node/Docker, présence de `claude`, `codex`, `gh`, authentifications déjà actives sans exposer les identifiants). **Ne lis ni n'imprime les fichiers secrets.**
2. Si le dépôt est vide, initialise le monorepo décrit plus bas. S'il existe, préserve le travail en cours et implémente sans écraser les fichiers personnels. Si des commits existent, crée une branche de travail dédiée.
3. Crée un `IMPLEMENTATION_STATUS.md` listant les étapes, critères d'acceptation, commandes de test, points bloqués et prochaines tâches. Actualise-le à chaque étape.
4. Implémente le produit **verticalement, de bout en bout**, dans l'ordre des phases. Évite dix écrans factices et dix agents simulés comme produit final : chaque fonctionnalité annoncée doit avoir un comportement vérifiable.
5. Choisis des versions de dépendances **stables et disponibles**, vérifie les API/SDK dans leurs documentations officielles lorsque tu disposes d'un accès réseau, et verrouille les versions dans les lockfiles. N'invente pas les noms de modèles, endpoints, méthodes SDK ou conditions d'abonnement.
6. Prépare automatiquement Docker Compose, migrations, données de démonstration, `.env.example`, commandes `make`/scripts, tests, documentation et un parcours **zéro clé API** en mode démo. Une installation locale doit démarrer sans service payant.
7. Si l'utilisateur possède déjà un **Codex CLI** ou un **Claude Code CLI** officiel connecté, détecte les capacités **sans accéder aux tokens/session cookies**. Implémente les intégrations locales dans les limites officielles et de licence exposées ci-dessous. Ne contourne jamais l'authentification ni les quotas.
8. Implémente les adaptateurs API **avec leurs champs de configuration, tests simulés et connecteurs réels**, mais ne prétends pas les avoir validés auprès de fournisseurs auxquels aucun accès n'est disponible.
9. Pour tout acte externe — création d'un dépôt distant, push, ouverture d'une PR, déploiement, achat, exécution de script privilégié, installation système — respecte les droits et les validations explicites nécessaires. **Ne crée pas de PR réelle ni ne déploie sans choix/autorisation de l'utilisateur.**
10. Exécute les tests à chaque phase. Corrige les échecs, fournis la preuve de ce qui a été testé. Ne marque pas `DONE` une fonctionnalité partiellement implémentée : utilise `READY`, `PARTIAL`, `BLOCKED` ou `DONE`.
11. À la fin de chaque session, résume ce qui fonctionne vraiment, ce qui reste à faire, et les commandes exactes pour lancer l'application. **Continue l'implémentation autant que l'environnement le permet ; ne t'arrête pas après avoir établi un plan.**

**Instruction de lancement à donner à Claude Code :**

```text
Lis NFACTORY_MASTER_PLAN.md et traite-le comme la spécification produit principale.
Commence immédiatement à implémenter NFactory, phase par phase, sans me demander de choisir
la stack ou de redéfinir les besoins. Initialise le monorepo, Docker Compose, FastAPI,
Next.js, PostgreSQL/pgvector, Redis, les adaptateurs providers, le dashboard et le
premier workflow agentique complet. Crée IMPLEMENTATION_STATUS.md et maintiens les
preuves de tests. Active le mode démo sans API et détecte les outils locaux officiels.
Ne fabrique aucune clé ni aucun login ; pour les connexions réelles manquantes,
laisse une interface prête et indique exactement l'action d'authentification requise.
Ne fais pas d'action externe irréversible sans validation explicite.
```

---

# 1. Vision : ce qu'est NFactory

**NFactory = une usine logicielle IA accessible par conversation ET par interface visuelle.** Un utilisateur novice décrit son besoin ; NFactory génère un plan, met en place le projet, utilise les agents/modèles autorisés, écrit le code, exécute les vérifications, améliore les erreurs, affiche une prévisualisation, puis crée un package ou une **pull request** que quelqu'un peut relire.

## 1.1 Les quatre promesses produit

1. **« Idée → projet utilisable » :** pas seulement un extrait de code, mais un dépôt cohérent avec instructions, tests, documentation et livrables.
2. **« Apportez votre moteur IA » :** OpenAI API, Anthropic API, DeepSeek, Z.ai/GLM, Moonshot/Kimi, Qwen, MiniMax, modèles locaux ; Codex et Claude Code officiels locaux selon les droits/conditions en vigueur.
3. **« Local-first, cloud-ready » :** le coeur fonctionne sur la machine de l'utilisateur ; les services cloud/entreprise sont une étape ultérieure.
4. **« Confiance vérifiable » :** provenance du code, validations, logs, évaluations, approbation humaine avant les actions sensibles.

## 1.2 Publics

- **Employé IT non développeur :** générer Excel, PowerShell, scripts ou petites applications depuis un assistant guidé.
- **Développeur :** ajouter une feature à un dépôt existant, générer tests, docs et PR.
- **Tech lead :** imposer templates, architecture, budgets et contrôles.
- **Equipe IT :** accélérer les demandes répétitives sans sacrifier la revue et la sécurité.

## 1.3 Ce que NFactory n'est PAS

- Pas un simple chatbot RAG.
- Pas un wrapper avec dix appels LLM systématiques.
- Pas un outil qui « merge » directement du code non relu dans la branche principale.
- Pas une promesse de prise en charge de tous les langages et projets dès la v1 : il faut une plateforme extensible avec **4 livrables excellents** au lancement et un catalogue extensible ensuite.

---

# 2. Fonctionnalités produit — catalogue complet

**Priorité : P0 = MVP réel, P1 = v1 ambitieuse, P2 = extensions.** Les fonctionnalités historiques de NFactory sont conservées et renforcées.

| ID | Fonctionnalité | Comportement réel attendu | Priorité |
|---|---|---|---|
| F01 | **Conversational Project Builder** | Créer un projet depuis une phrase en langage naturel ; clarifier uniquement les paramètres manquants décisifs. | P0 |
| F02 | **Visual Project Wizard (low/no-code)** | Formulaire guidé : type, objectif, stack, sources, niveau d'accès, destination, moteur IA. | P0 |
| F03 | **Factory Dashboard** | Liste, filtres, état des runs, progression, métriques, previews, validations, providers. | P0 |
| F04 | **Ten-agent Factory** | Planner, architect, builder, tester, reviewer, debugger, etc. ; orchestration réelle et tracée. | P0 |
| F05 | **Provider Marketplace** | Choix OpenAI/Anthropic/DeepSeek/GLM/Kimi/Qwen/MiniMax/Ollama/Custom. | P0 |
| F06 | **Local Codex Integration** | Détection, connexion officielle quand disponible, exécution contrôlée dans un workspace. | P1 |
| F07 | **Local Claude Code Integration** | Détection du binaire officiel et exécution conforme aux conditions en vigueur ; aucune collecte de cookies/tokens. | P1 |
| F08 | **AI Model Router** | Affectation provider/modèle par rôle, fallback explicite, budgets, tests de capacités. | P1 |
| F09 | **Golden Path Templates** | Génération de projets via templates validés et paramétrables, pas uniquement génération libre. | P0 |
| F10 | **RAG / Enterprise Brain** | Indexer docs, runbooks, exemples, conventions, templates et repos avec citations et ACL. | P0 |
| F11 | **Vector Search** | PostgreSQL + pgvector, recherche hybride, filtrage par projet/équipe. | P0 |
| F12 | **GitHub Project & PR** | Importer repo, créer branche, commit, push et PR brouillon après approbation. | P1 |
| F13 | **Feature Builder** | Ajout de fonctionnalité à un repo existant en respectant l'architecture. | P1 |
| F14 | **Automated Build & Test** | Lint, typecheck, tests unitaires/intégration, analyse des résultats. | P0 |
| F15 | **Self-Healing Loop** | Corriger les erreurs des builds/tests dans un nombre limité de tentatives. | P0 |
| F16 | **AI Code Review** | Relecture structure, qualité, vulnérabilités, conformité et diff. | P1 |
| F17 | **Preview & Artifacts** | Voir une application générée ou télécharger zip, Excel, scripts, README, rapport. | P0 |
| F18 | **Excel Automation Factory** | Générer des fichiers `.xlsx` et pipelines Python reproductibles. | P0 |
| F19 | **PowerShell Factory** | Générer des scripts Windows avec dry-run, analyse statique et validations. | P0 |
| F20 | **Web App Factory** | Générer frontend React/Next + backend FastAPI + tests + compose. | P0 |
| F21 | **API / Backend Factory** | FastAPI seul, endpoints REST, schémas OpenAPI et tests. | P0 |
| F22 | **Workflow & Scheduler** | Automatisations planifiées après approbation ; retries et traçabilité. | P1 |
| F23 | **Live Agent Timeline** | Visualisation du graphe, étapes, coûts, outils, artefacts, erreurs, validations. | P0 |
| F24 | **Human-in-the-loop** | Pause et validation avant permissions, exécution risquée, GitHub, publication. | P0 |
| F25 | **AI Evaluations** | Jeux de cas, pass/fail, régressions, scores par projet/provider. | P1 |
| F26 | **Observability** | Tracing OTel, logs structurés, coût, tokens, latence, taux d'erreur. | P0 |
| F27 | **Budget & Quotas** | Limites par run, modèle, projet et utilisateur ; arrêt automatique si seuil atteint. | P0 |
| F28 | **Context Memory / Project Memory** | Mémoire persistante des conventions et décisions validées, scoped par projet. | P1 |
| F29 | **Version & Rollback** | Historique des runs, snapshots de code, comparaison et reprise de run. | P1 |
| F30 | **Enterprise Policy Engine** | Templates approuvés, dépendances autorisées, restrictions réseau et destinations. | P1 |
| F31 | **Plugin / Connector SDK** | Adaptateurs d'outils et nouveaux types de livrables sans modifier le coeur. | P2 |
| F32 | **MCP Optionnel** | Connecter des outils MCP lorsque nécessaire, jamais prérequis pour Codex/Claude. | P2 |
| F33 | **Multi-user / RBAC** | Rôles Owner, Admin, Developer, Reviewer, Viewer ; isolation projets. | P1 |
| F34 | **Enterprise SSO** | OIDC/SAML selon fournisseur, à ajouter après le MVP local. | P2 |
| F35 | **Cost & Quality Comparison** | Benchmark comparatif des providers sur mêmes tâches, métriques transparentes. | P1 |
| F36 | **Knowledge Drift Detector** | Détecter documentation périmée et contradictions ; proposer une PR documentaire. | P2 |
| F37 | **Automatic Documentation** | README, ADR, OpenAPI, runbooks, scripts d'installation, changelog. | P0 |
| F38 | **Reusable Factory Recipes** | Sauvegarder un workflow comme recette réutilisable par l'équipe. | P1 |
| F39 | **Human-friendly Explain Mode** | Expliquer sans jargon ce qui a été généré et ce que l'utilisateur doit vérifier. | P0 |
| F40 | **Offline Demo / Mock Providers** | Démonstration de tous les écrans et du workflow avec données synthétiques, sans clé. | P0 |

**Au-delà de l'effet « waouh » :** les meilleures démos doivent prouver `spec → code → test → preview → PR`, avec un rapport vérifiable. Toute fonctionnalité en maquette doit être explicitement marquée `DEMO`.

---

# 3. Parcours utilisateur et scénarios de démonstration

## 3.1 Scénario A — Application complète de gestion des licences IT

L'utilisateur écrit :

> « Crée une application interne de suivi des licences : dashboard React, API Python, PostgreSQL, export Excel, alertes d'expiration. Génère les tests, la documentation et une PR. »

1. Le **Requirements Agent** extrait les modules et signale les 2–3 questions vraiment indispensables (ex. source des licences, règles de notification).
2. Le **Planner** décompose en tickets indépendants, définit un plan et une checklist.
3. Le **Enterprise Brain/RAG** retrouve le golden path sélectionné ; il présente des citations vers les sources auxquelles l'utilisateur a droit.
4. L'**Architect** établit la structure fichiers, schémas, endpoints et risques.
5. Le **Builder** génère le backend, frontend et schémas de base.
6. L'**Automation Agent** crée l'export Excel et les alertes (simulation si les services externes ne sont pas connectés).
7. Le **Tester** lance lint/build/tests dans un bac à sable isolé.
8. Le **Debugger** corrige au plus `MAX_REPAIR_ATTEMPTS` fois.
9. Les agents **Reviewer** et **Security** analysent le diff et signalent les points ouverts.
10. L'utilisateur voit le projet dans **Preview**, accepte de créer une branche/PR et reçoit un lien GitHub si l'autorisation est disponible ; sinon un ZIP et les instructions de connexion.

**Démo réussie :** au moins un écran React réel, une API FastAPI réellement testée, une feuille Excel téléchargeable, tests passés, aucun faux statut de PR.

## 3.2 Scénario B — PowerShell pour IT Windows

> « Génère un script PowerShell qui produit un inventaire des versions installées de nos applications depuis une liste de machines autorisées. »

NFactory livre : `.ps1`, paramètres obligatoires, mode `-WhatIf`/dry-run lorsque pertinent, rapport CSV/Excel de démonstration, Pester tests, README, avertissements de permissions. **Aucune exécution sur un parc ou machine externe sans autorisation explicite**, ni exfiltration.

## 3.3 Scénario C — Automatisation Excel

> « Chaque semaine, transforme deux exports CSV en un Excel multi-onglets avec formules, KPIs et graphiques. »

NFactory livre : `pipeline.py`, exemples de CSV synthétiques, fichier `.xlsx` généré et testé, `requirements` verrouillés, procédure d'exécution et recette de planification désactivée par défaut.

## 3.4 Scénario D — Feature GitHub existante

> « Dans mon repo, ajoute un endpoint de recherche filtrable, les tests et la documentation. Crée une PR brouillon. »

NFactory clone **uniquement le repo autorisé**, prépare un git worktree/une branche, indexe les fichiers nécessaires, modifie une portée limitée, lance les checks, publie une PR si autorisé ; **ne merge jamais automatiquement**.

## 3.5 Scénario E — Changement incrémental

Après livraison, l'utilisateur demande « Ajoute un filtre par département et un export PDF ». L'agent reprend le **même projet**, crée un run enfant avec diff et nouvelle validation, au lieu de repartir de zéro.

---

# 4. Architecture cible

## 4.1 Schéma logique

```text
                       NFACTORY DASHBOARD
                         Next.js / React
                 projects · runs · builder · settings
                               │ HTTPS/SSE
                               ▼
                      Python FASTAPI (API)
        auth · projects · artifacts · providers · approvals
                               │
                ┌──────────────┼──────────────┐
                ▼              ▼              ▼
           PostgreSQL       Redis         Object Store
           + pgvector    queue/cache      (local/MinIO)
                │              │              │
                └──────────────┼──────────────┘
                               ▼
                    NFACTORY WORKER POOL
              LangGraph · state · policies · evals
                               │
            ┌──────────────────┴───────────────────┐
            ▼                                      ▼
      AI PROVIDER HUB                        TOOL HUB
    API adapters / local                    Git / file / tests
    coding-agent adapters                   sandbox / RAG / docs
            │                                      │
   ┌────────┴────────────────┐           ┌─────────┴──────────┐
   ▼                         ▼           ▼                    ▼
External API             Local Bridge  pgvector            Sandbox
OpenAI/Anthropic/        (host only)   indexed docs        Executor
DeepSeek/GLM/Kimi/       Codex CLI /   + citations         (isolated)
Qwen/MiniMax             Claude Code                        │
   │                         │                               ▼
   └─────────────────────────┴─────────────────────── Code Workspace
                                                           │
                                                   Build/Test/Review
                                                           │
                                                       GitHub PR
                                                    (with approval)
```

**Choix essentiel :** backend principal **100 % Python / FastAPI** ; dashboard **Next.js/TypeScript**. Pas de second backend Node.js en dehors du serveur frontend Next.js. Un pont local léger peut être nécessaire pour les binaires installés sur la machine ; il doit rester distinct des workers serveurs.

## 4.2 Stack précise et responsabilités

| Bloc | Technologie de référence | Pourquoi |
|---|---|---|
| Dashboard | Next.js + TypeScript + Tailwind + shadcn/ui | UX rapide, composants accessibles |
| Visualisation des agents | React Flow si utile | Graphe et états des tâches |
| Client state/data | TanStack Query + SSE | Streaming sans WebSocket imposé |
| API | Python + FastAPI + Pydantic v2 | Contrats typés, OpenAPI |
| Orchestration | LangGraph (Python) | Workflows persistants, interruptions |
| Workers | ARQ + Redis, ou alternative maintenue si incompatibilité vérifiée | Jobs asynchrones et retries |
| State durable | PostgreSQL + checkpointer LangGraph compatible | Reprise/relecture de runs |
| Search/RAG | PostgreSQL + pgvector + recherche plein texte | Vector DB intégrée |
| Documents | Stockage local dev ; S3-compatible/MinIO en option | Artifacts et pièces jointes |
| App cache | Redis | Cache, pub/sub et anti-abus |
| Data access | SQLAlchemy 2 + Alembic | Migrations fiables |
| LLM API gateway | Couche `ProviderAdapter` maison ; LiteLLM comme intégration optionnelle | Aucun couplage à un SDK unique |
| Tests Python | pytest, pytest-asyncio, ruff, mypy | Qualité backend |
| Tests frontend | Vitest + Playwright | Composants et E2E |
| Evaluation | eval runner maison + jeux de cas ; LangSmith/Langfuse optionnel | Mesures reproductibles |
| Observability | OpenTelemetry + logs JSON + dashboard interne | Diagnostiques et latence |
| Environnements | Docker Compose (dev), images Docker | Démarrage reproductible |
| Sandbox d'exécution | Runner dédié isolé, non privilégié | Exécution de code généré |
| GitHub | REST API ou `gh` local / GitHub App (selon mode) | Branches et PR |

**Règle :** ajouter des dépendances seulement si un cas d'usage les justifie. Le résultat doit être stable avant d'être spectaculaire.

## 4.3 Trois modes de déploiement

**Mode 1 — Local personal (MVP) :** Next.js + FastAPI + Redis + Postgres en Docker Compose ; host-agent optionnel sur l'ordinateur pour Codex/Claude Code locaux ; aucun service cloud NFactory obligatoire.

**Mode 2 — Team (P1) :** serveur central + workers distants + RBAC ; **agents d'exécution locaux facultatifs** associés à un utilisateur, avec consentement.

**Mode 3 — Enterprise (P2) :** SSO, GitHub App, audit immuable, politiques par équipe, secrets manager, restrictions réseau et résidence des données.

**Ne pas faire semblant :** une page web sur un serveur cloud ne peut pas contrôler directement `codex` ou `claude` installé sur le PC. Le mode web central nécessitera un **companion/host agent** installé avec accord utilisateur ou une exécution distante séparée.

---

# 5. Système de 10 agents : rôles et contrats

Les dix rôles sont disponibles, **mais pas forcément dix LLM actifs dans chaque run**. Les validations déterministes, scripts, tests et règles d'autorisation doivent rester du code traditionnel.

| # | Agent | Entrée | Sortie / responsabilité |
|---|---|---|---|
| A1 | **Requirements Agent** | Demande utilisateur, formulaire, contexte | `ProjectRequirements` structuré et questions critiques |
| A2 | **Planner Agent** | Requirements, contraintes, budget | `ExecutionPlan` : tâches, dépendances, critères de succès |
| A3 | **Architect Agent** | Plan, golden path, repo | `ArchitectureSpec` : stack, arborescence, ADR, sécurité |
| A4 | **Orchestrator** | Plan, états, outils | Enchaînement LangGraph, reprises, timers, permissions (**principalement déterministe**) |
| A5 | **Builder Agent** | Tâches, architecture | Modifications de fichiers dans un workspace isolé ; interfaces outil |
| A6 | **Automation Agent** | Besoin Excel/PowerShell/scripts | Artefacts et automatisations paramétrées |
| A7 | **Tester Agent** | Workspace + critères | Lancement de vrais tests, résultats normalisés (**runner déterministe**) |
| A8 | **Debugger Agent** | Erreurs tests, diff, traces | Hypothèses + patchs ciblés + nouvelle tentative |
| A9 | **Reviewer Agent** | Diff, style, risques, sources | Revue structurée, recommandations, blocages |
| A10 | **Security & Delivery Agent** | Artefacts, rapport de tests, policies | Scans, manifest, release package et préparation GitHub (**permissions déterministes**) |

**Ne pas multiplier les appels LLM inutiles :** `A4`, une partie de `A7` et les décisions d'autorisation de `A10` doivent être des modules logiciels, pas des prompts pseudo-autonomes.

## 5.1 Schémas de sorties obligatoires

Chaque agent LLM produit un objet JSON typé et validé Pydantic. Exemple :

```python
from pydantic import BaseModel, Field
from typing import Literal


class WorkItem(BaseModel):
    id: str
    title: str
    description: str
    depends_on: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str]
    risk: Literal["low", "medium", "high"]


class ExecutionPlan(BaseModel):
    project_kind: Literal["webapp", "api", "excel", "powershell", "feature"]
    summary: str
    tasks: list[WorkItem]
    requested_tools: list[str] = Field(default_factory=list)
    requires_approval: bool = False
```

Chaque sortie stocke la version du prompt, le provider/modèle utilisé, l'horodatage, le coût si disponible et l'identifiant de trace. Un agent ne doit pas décider seul qu'un test a réussi ; le runner fournit le résultat vérifié.

## 5.2 Graphe d'exécution durable

```text
REQUEST
  → VALIDATE_INPUT
  → REQUIREMENTS
  → [CLARIFICATION si nécessaire]
  → RETRIEVE_CONTEXT (RAG + ACL)
  → PLAN
  → [APPROVE_PLAN si action sensible / coût prévu élevé]
  → ARCHITECT
  → CREATE_WORKSPACE
  → BUILD / AUTOMATE
  → RUN_STATIC_CHECKS
  → RUN_TESTS
      ├─ fail → DEBUG → APPLY_PATCH → RUN_TESTS  (max 3 essais)
      └─ pass → REVIEW → SECURITY_GATE
  → GENERATE_DOCS
  → PACKAGE_AND_PREVIEW
  → [APPROVE_GITHUB_ACTION]
  → CREATE_BRANCH_AND_DRAFT_PR (si autorisé)
  → COMPLETE / PARTIAL / FAILED / CANCELLED
```

**Garde-fous :** idempotency keys, maximum d'étapes, deadline, budget, cancellation, reprise sur checkpoint, aucun cycle de réparation infini, pas de suppression du workspace sans confirmation et politique de rétention.

---

# 6. Multi-provider : la partie la plus importante

## 6.1 Deux familles réellement différentes

**Famille A — Model API :** fournisseur de génération/réponse à un prompt. OpenAI API, Anthropic API, DeepSeek, GLM, Kimi, Qwen, MiniMax, Ollama. Les capacités varient : JSON strict, tool calling, streaming, embeddings, vision, contexte, prix et quotas. Une interface « OpenAI-compatible » n'implique **pas** une parité fonctionnelle totale.

**Famille B — Coding Agent Runtime :** moteur qui peut travailler **dans un dépôt**, modifier des fichiers, exécuter des commandes et gérer sa session : **OpenAI Codex CLI/SDK/app-server**, **Claude Code officiel**. Ces outils ne se branchent pas comme une simple `chat_completion()` ; ils ont des permissions, événements, sessions et contraintes d'authentification propres.

Les deux familles sont réunies dans l'UI sous « Moteurs IA », mais les contrats techniques sont distincts.

## 6.2 Liste des providers demandés

| ID | Fournisseur / runtime | Type | Connexion utilisateur | État visé |
|---|---|---|---|---|
| `openai_api` | OpenAI API (GPT, modèles disponibles pour le compte) | API | `OPENAI_API_KEY` | P0 |
| `anthropic_api` | Anthropic API (Claude) | API | `ANTHROPIC_API_KEY` | P0 |
| `deepseek_api` | DeepSeek | API | `DEEPSEEK_API_KEY` | P0 |
| `zai_glm_api` | Z.ai / GLM | API | `ZAI_API_KEY` | P0 |
| `moonshot_kimi_api` | Moonshot AI / Kimi | API | `MOONSHOT_API_KEY` | P0 |
| `qwen_api` | Alibaba Cloud Model Studio / Qwen | API | `DASHSCOPE_API_KEY` + région/workspace | P1 |
| `minimax_api` | MiniMax | API | `MINIMAX_API_KEY` | P1 |
| `custom_openai_compatible` | Autre endpoint compatible | API | URL + clé + capabilities | P1 |
| `ollama_local` | Ollama local | API locale | URL locale, modèle téléchargé | P1 |
| `codex_local` | OpenAI Codex officiel | Agent local | Connexion ChatGPT officielle **ou** clé API | P1 |
| `claude_code_local` | Claude Code officiel | Agent local | Connexion native Claude Code autorisée **ou** clé API | P1 |

**Noms des modèles :** les récupérer par découverte quand le fournisseur l'expose ; sinon conserver un catalogue configurable administrable. **Ne jamais figer en dur un nom de modèle susceptible de disparaître.**

## 6.3 Contrats de code proposés

```python
from dataclasses import dataclass
from typing import Any, Protocol, AsyncIterator


@dataclass(frozen=True)
class ProviderCapabilities:
    streaming: bool
    tool_calling: bool
    structured_output: bool
    vision: bool
    embeddings: bool
    json_schema: bool
    max_context_tokens: int | None


class ModelProvider(Protocol):
    async def check_connection(self) -> dict[str, Any]: ...
    async def list_models(self) -> list[dict[str, Any]]: ...
    async def capabilities(self, model: str) -> ProviderCapabilities: ...
    async def complete(self, model: str, messages: list[dict], **kwargs) -> dict: ...
    async def stream(self, model: str, messages: list[dict], **kwargs) -> AsyncIterator[dict]: ...


class CodingAgentRuntime(Protocol):
    async def detect(self) -> dict[str, Any]: ...
    async def status(self) -> dict[str, Any]: ...
    async def start_task(self, workspace: str, task: dict, permissions: dict) -> str: ...
    async def stream_events(self, session_id: str) -> AsyncIterator[dict]: ...
    async def cancel(self, session_id: str) -> None: ...
```

Les deux interfaces ne doivent **pas être fusionnées en un seul faux appel générique**. Adapter ensuite `ModelProvider` aux invocations LangGraph, et `CodingAgentRuntime` à l'exécution de tâches dans les workspaces.

### Routage par rôle

Exemple configurable, **pas une hiérarchie universelle de qualité** :

```yaml
routing:
  requirements: { provider: openai_api, model: "<user-selected>" }
  planner:      { provider: anthropic_api, model: "<user-selected>" }
  architect:    { provider: zai_glm_api, model: "<user-selected>" }
  builder:      { runtime: codex_local }
  tester:       { engine: deterministic }
  debugger:     { provider: deepseek_api, model: "<user-selected>" }
  reviewer:     { provider: moonshot_kimi_api, model: "<user-selected>" }
  security:     { engine: deterministic_plus_review }
  fallback:     { mode: ask_user }
  limits:       { max_llm_calls: 80, max_repair_attempts: 3 }
```

Un utilisateur peut choisir **un seul moteur pour tous les rôles compatibles**. Quand un agent local complet est sélectionné, il doit produire les mêmes artefacts vérifiables que le builder API ; l'orchestrateur ne suppose pas qu'il contrôle le raisonnement interne du runtime.

## 6.4 Intégration **Codex avec abonnement ChatGPT**

Deux voies possibles et distinctes :

**Voie 1 — Codex local déjà installé/connecté :**

- Détecter le binaire officiel `codex` et sa version via commandes publiques.
- Ne jamais lire les fichiers d'auth privés, cookies ou jetons.
- Utiliser le **Codex SDK**, `codex exec` ou **Codex app-server**, selon le niveau d'interactivité et les droits réellement disponibles.
- Utiliser les sessions et callbacks officiels ; demander les approbations pour les commandes/actions requises ; exécuter sur un projet isolé.
- Afficher les vrais statuts : `installed`, `needs_login`, `connected`, `blocked_by_policy`, `rate_limited`.

**Voie 2 — « Sign in with ChatGPT » dans une application open source locale éligible :**

- OpenAI documente un flux de connexion et de partage **optionnel** du forfait pour certaines applications open source/localement hébergées. La permission doit être explicitement accordée (`chatgpt.tokens.use.direct`), et l'accès dépend de l'éligibilité et des restrictions en vigueur.
- Si NFactory remplit les critères, suivre **exactement** le flux officiel et son SDK/guide ; ne pas simuler une connexion.
- Pour une application commerciale **hébergée**, l'accès peut requérir une validation partenaire : ne pas promettre cette option à tous les utilisateurs.
- La connexion ChatGPT **n'est pas une clé OpenAI API gratuite et illimitée** ; limites et capacités restent celles autorisées au compte.

**Critère d'acceptation :** un utilisateur local déjà connecté à Codex peut lancer un petit patch avec consentement ; on voit les événements et le diff ; sinon un état `Login required` honnête et un bouton vers le flux natif.

## 6.5 Intégration **Claude Code avec abonnement Claude** — point de conformité

- Détecter le **binaire officiel non modifié** `claude`.
- L'utilisateur se connecte **dans le flux natif Anthropic** (`claude` et commandes officielles). NFactory ne doit jamais récolter ou relayer le token OAuth, ni présenter un faux « Login with Claude » propriétaire.
- Anthropic distingue l'**usage ordinaire de Claude Code** et l'intégration par des **applications tierces/Agent SDK**. Le document officiel *Legal and compliance* précise que les intégrations de produits doivent respecter des conditions commerciales et que les développeurs ne peuvent pas router des requêtes sur les identifiants d'abonnement des utilisateurs comme substitut à une API. **Avant d'activer l'orchestration programmatique à grande échelle sur abonnement, vérifier que le mode d'intégration précis est autorisé.**
- Fournir dès le MVP une intégration **Claude API** totalement prise en charge et un mode **handoff local explicite** pour Claude Code : préparation du workspace/brief, lancement par l'utilisateur dans le binaire officiel, puis import du diff et des résultats. Cela ne dépend d'aucun contournement.
- Le mode « runtime piloté » via CLI/SDK doit être **feature-flagged** jusqu'à vérification juridique/contractuelle ; si non autorisé, garder le handoff local et le provider API.
- Ne pas prétendre que « Claude Max = accès API Anthropic inclus ». Ce sont des offres différentes.

**UX souhaitée :** « Claude Code local — installé » ; « Utiliser mon installation » ; explication claire du mode disponible (`handoff` / `runtime autorisé` / `API`).

## 6.6 Fournisseurs chinois et API OpenAI-compatibles

- **DeepSeek :** API et interface compatibles OpenAI/Anthropic selon sa documentation. Utiliser un adaptateur versionné et des tests tool-call/JSON.
- **Z.ai / GLM :** API Z.ai ; adaptation des paramètres et des capacités réelles.
- **Moonshot / Kimi :** API officielle Moonshot ; noms des modèles configurables et endpoints vérifiés à l'implémentation.
- **Alibaba / Qwen :** endpoint **dépendant de la région et de l'espace de travail** ; ne pas hardcoder une URL unique universelle.
- **MiniMax :** adaptateur dédié ou OpenAI-compatible après tests de conformité.
- **Custom :** prise en charge `base_url`, `api_key`, `model_id`, headers configurables autorisés et tests de connexion, avec prévention des accès à des réseaux internes non autorisés (SSRF).

Chaque adaptateur possède : `connection_check`, `model_discovery` ou catalogue, `streaming`, `tool_calls`, `json/structured outputs`, erreurs normalisées, tokens/usage, limites, validation de certificat, tests d'intégration mockés.

## 6.7 Sécurité et confidentialité des fournisseurs

- **Aucun fallback silencieux** de modèles locaux à un fournisseur externe : le transfert de code/documents privés à un autre fournisseur nécessite une autorisation claire.
- Afficher le fournisseur, la région connue, les catégories de données transmises et les limites de politique IT.
- Mode `LOCAL_ONLY` : interdire toute API de modèle distante ; si aucun modèle réellement local n'est disponible, arrêter proprement au lieu de tromper l'utilisateur.
- Tous les appels externes respectent la classification des données et les contrats d'entreprise.

---

# 7. RAG + Vector Database : Enterprise Brain

## 7.1 Objectif

NFactory doit s'appuyer sur des **connaissances vérifiables** : templates, README, docs IT, conventions, dépôts Git autorisés, tickets exportés avec droit d'usage, exemples de tests et politiques. Une couche RAG seule ne permet pas d'« apprendre » une architecture sans contrôle : chaque source doit être qualifiée.

## 7.2 Pipeline d'ingestion

1. **Connectors :** upload Markdown/PDF/DOCX/TXT/code, dossier local choisi, dépôt Git autorisé ; GitHub API, Confluence/SharePoint en P2 selon droits.
2. **Extraction :** extraction texte+structure ; pour code, découpage AST/symboles quand possible ; déduplication via hash.
3. **Metadata :** `tenant_id`, `project_id`, `source_id`, `revision`, `path`, `language`, `visibility`, `owner`, `expires_at`, `allowed_roles`.
4. **Chunking :** sections pour docs ; fonctions/classes pour code ; chevauchement raisonnable et trace vers la ligne d'origine.
5. **Embeddings :** provider sélectionnable **indépendant** du modèle de génération ; option locale pour confidentialité. Vérifier que les modèles ont la même dimension par index ; ré-indexation versionnée en cas de changement.
6. **Storage :** PostgreSQL + pgvector ; index vectoriels et plein texte ; fichiers originaux en stockage contrôlé.
7. **Retrieval :** ACL et filtres d'abord → combinaison BM25/full-text + vecteur → fusion de résultats → reranking si disponible → limite de tokens.
8. **Réponse :** citations exactes (`source path`, `commit`, `section`, `line` ou lien), score descriptif si disponible, distinction entre faits et hypothèses.
9. **Maintenance :** invalidation sur changement de commit/doc, date d'expiration, purge par projet, suppression conforme aux droits et politiques de rétention.

## 7.3 Mémoire de projet

- `decision_memory` : décisions validées par une personne.
- `run_history` : étapes, diagnostics, diff et incidents ; ne pas stocker systématiquement toute la conversation brute.
- `pattern_library` : templates golden paths versionnés.
- `failed_attempts` : erreurs/solutions confirmées, utiles à la réparation future.

**Protection :** les documents récupérés sont du **contenu non fiable** pour l'agent. Aucune instruction contenue dans un README externe ne peut augmenter les permissions des outils ou changer les politiques.

## 7.4 Evals RAG

- Recall@K sur un jeu de documents de référence.
- Pertinence des passages remontés.
- Qualité des citations (les passages existent et soutiennent la réponse).
- Isolation entre utilisateurs/projets (tests négatifs).
- Rejet d'instructions malveillantes dans les documents.

---

# 8. Docker, Redis, exécution et sandboxes

## 8.1 Services Docker Compose de développement

```text
frontend       Next.js dashboard
api            FastAPI
worker         ARQ / Redis worker + LangGraph
postgres       PostgreSQL + extension pgvector
redis          cache + broker jobs
objectstore    MinIO ou volume local (optionnel)
telemetry      Jaeger/OTel collector (profil optionnel)
```

Le **host bridge** pour Codex/Claude Code reste **sur la machine de l'utilisateur** : un container serveur ne doit pas prétendre disposer de sa session locale. Il doit écouter sur `127.0.0.1` uniquement, utiliser une autorisation explicite et ne jamais exposer un shell brut via HTTP.

## 8.2 Redis : utilisations précises

- File de jobs `factory-runs` avec priorité et tentatives bornées.
- Cache de requêtes RAG non sensibles, séparé par `tenant_id`/`project_id` ; TTL explicite.
- Progress events/pub-sub pour UI SSE.
- Rate limiting par utilisateur/provider.
- Verrou d'idempotence pour empêcher deux PR/builds identiques.

**Ne pas stocker l'état critique uniquement dans Redis.** État durable, approbations, événements métiers et historique doivent être en PostgreSQL.

## 8.3 Sandbox obligatoire

**Le code généré est non fiable, y compris si le LLM le propose.**

- Créer un workspace unique par run ; aucun accès au repo NFactory lui-même.
- Exécuter tests/build/scripts dans un environnement isolé non privilégié, quotas CPU/RAM/disque/temps, fichiers montés au strict minimum, pas de secrets réels injectés par défaut.
- Réseau sortant désactivé par défaut pendant les exécutions de code utilisateur ; si packages nécessaires, permettre une phase de préparation contrôlée et des registries approuvés.
- Ne jamais monter `/var/run/docker.sock` dans l'API ou un worker généraliste ; utiliser un **sandbox supervisor** distinct avec périmètre limité (ou un backend isolé équivalent).
- Traiter les appels Docker et PowerShell comme des actions à risques, journalisées et explicitement autorisées ; pas d'élévation de privilège automatique.
- Limiter nombre de fichiers modifiables, taille totale, exécutions concurrentes et temps d'une commande.
- Protection des chemins (`../`, liens symboliques, traversée du filesystem), des URL internes (SSRF), secrets, commandes dangereuses et sorties trop volumineuses.
- Pour les scripts Windows : génération + analyse statique d'abord ; exécution réelle uniquement sur environnement Windows explicitement dédié et autorisé.

## 8.4 Politique de reprise

- `run_id` et `step_id` stables ; chaque étape vérifie si elle a déjà produit un effet.
- Pannes réseau/provider → retry exponentiel limité et circuit breaker.
- Approbations humaines → graph interrompu avec checkpoint PostgreSQL.
- Après redémarrage, reprendre uniquement les étapes sûres ; actions GitHub idempotentes par branche / marqueur de run.

---

# 9. Dashboard : expérience visuelle indispensable

## 9.1 Direction design

Un dashboard qui ressemble à un **véritable produit SaaS premium**, pas à une maquette de hackathon. Interface lumineuse, structurée, contrastée, avec typographie marquée, statuts vivants, timeline et vues détaillées.

**Palette proposée :**

- Cream `#F5EFE5` — fond clair.
- Eggplant `#261A2E` — surfaces/sidenav sombres.
- Navy `#162743` — texte ou surfaces secondaires.
- Coral `#E07A5F` — accent principal.
- Deep coral `#C04A2A` — actions importantes.
- Golden butter `#F5C926` — mises en évidence.

Accessibilité : contrastes WCAG, raccourcis clavier, états de focus, responsive desktop/tablette, reduced motion. **Ne pas faire dépendre une information critique uniquement d'une couleur.**

## 9.2 Navigation

```text
NFactory
├── Overview
│   ├── Factory health / provider health
│   ├── Recent projects & runs
│   ├── Success rate / average latency / costs
│   └── Approvals awaiting review
├── New Project
│   ├── Chat builder
│   ├── Guided wizard
│   └── Template gallery
├── Projects
│   ├── Project overview
│   ├── Files / code diff
│   ├── Features / backlog
│   ├── Knowledge base / RAG
│   ├── Runs / previews / artifacts
│   └── GitHub / Releases
├── Live Factory
│   ├── Agent graph
│   ├── Event timeline
│   ├── Build/test logs
│   └── Approval queue
├── AI Providers
│   ├── API connections
│   ├── Local runtimes
│   ├── Routing by agent
│   ├── Capabilities & diagnostics
│   └── Budgets
├── Knowledge Hub
│   ├── Sources & indexes
│   ├── Search playground
│   ├── Retrieval diagnostics
│   └── Source access
├── Evaluations
│   ├── Test suites
│   ├── Benchmark runs
│   ├── Regression results
│   └── Provider comparison
├── Templates / Recipes
├── Audit & Security
└── Settings
```

## 9.3 Écrans à implémenter réellement

**Overview :** chiffres tirés de la base (runs, terminés, réussis, durée moyenne, coût estimé lorsque disponible), health-check providers. En mode démo les données portent clairement la mention `Demo data`.

**New Project :** grande zone de prompt, types proposés (« Web app », « API », « Excel », « PowerShell », « Existing repo »), modèle/provider, permissions, budget, bouton `Generate plan`.

**Project Workspace :** split view conversation / arbre de fichiers / tabs Diff-Preview-Tests-Docs ; boutons `Run`, `Cancel`, `Approve`, `Download`, `Create draft PR` selon autorisations.

**Live Factory :** visualisation DAG des agents, activité temps réel SSE, durée, statuts par étape, logs filtrables, traces, tentatives de réparation.

**Providers :** cartes `API key needed`, `Connected`, `Local install detected`, `Login required`, `Unsupported`, `Disabled by policy` ; pas de fausse validation automatique.

**Knowledge Hub :** import de documents, statut d'indexation, moteur embedding, recherche et citations ; isoler les ressources par projet.

**Approvals :** qui approuve quoi, diff, périmètre d'accès, impact, boutons explicites, date et auteur.

**Settings :** préférences local/cloud, limites tokens/coûts, comportement fallback, rétention, journaux et export des données.

## 9.4 UX pour novices

- **Express mode** : besoin → plan simplifié → « Construire » → preview → télécharger.
- **Expert mode** : architecture, providers par agent, secrets, tests, workflow, GitHub, budgets.
- Sur chaque action, afficher les conséquences et demander un accord avant d'accéder à un dépôt privé, lancer un script privilégié ou publier.
- Explications en langage simple : « L'application fonctionne en aperçu ; une revue reste nécessaire avant déploiement. »

---

# 10. Base de données et contrat d'événements

## 10.1 Tables minimales

| Table | Colonnes conceptuelles |
|---|---|
| `users` | id, email/local_identity, display_name, created_at |
| `workspaces` | id, name, owner_id, data_policy, created_at |
| `memberships` | workspace_id, user_id, role |
| `projects` | id, workspace_id, title, type, template_id, repo_url, status |
| `runs` | id, project_id, request, state, budget, provider_config, started_at, finished_at |
| `run_steps` | id, run_id, agent_role, state, attempts, started_at, ended_at, error |
| `events` | id, run_id, step_id, type, payload_redacted, created_at |
| `artifacts` | id, project_id, run_id, filename, mime, storage_key, checksum, size |
| `approvals` | id, run_id, action_type, summary, status, requester_id, approver_id, timestamp |
| `provider_connections` | id, workspace_id, kind, display_name, secret_ref, status, config_non_secret |
| `model_catalog` | provider_kind, model_id, capabilities, reviewed_at |
| `template_versions` | id, name, version, manifest, checksum, allowed |
| `documents` | id, workspace_id, project_id, source, path, revision, acl, checksum |
| `document_chunks` | id, document_id, content, embedding, metadata, tsvector |
| `evaluation_cases` | id, suite_id, input, expected_behavior, tags |
| `evaluation_results` | id, run_id, case_id, pass, metrics, reviewer |
| `github_links` | project_id, owner, repo, branch, pr_number, last_synced |
| `audit_log` | actor_id, action, target, timestamp, decision, redacted_details |

Prévoir index appropriés, migrations Alembic, contraintes d'intégrité, suppression en cascade réfléchie, champs `tenant/workspace` et requêtes toujours filtrées par droits. **Aucun secret en clair dans les colonnes de configuration.**

## 10.2 Machine d'états

```text
DRAFT → PLANNING → WAITING_FOR_INPUT → APPROVAL_PENDING
      → QUEUED → RUNNING → REVIEW_PENDING
      → COMPLETED | PARTIAL | FAILED | CANCELLED
```

Transitions explicites, interdiction de « retourner à COMPLETED » sans nouveau run. Une tâche de fond qui échoue ne doit pas laisser l'interface afficher `RUNNING` éternellement.

## 10.3 Event stream versionné

```json
{
  "schema_version": "1",
  "event_id": "evt_demo_001",
  "run_id": "run_demo_001",
  "step_id": "step_build_api",
  "type": "step.completed",
  "timestamp": "2026-11-01T16:00:00Z",
  "payload": {
    "agent": "builder",
    "duration_ms": 18400,
    "artifacts": ["backend/app/main.py"],
    "test_status": "not_run"
  }
}
```

Événements utiles : `run.created`, `run.started`, `agent.started`, `agent.progress`, `tool.invoked`, `approval.requested`, `approval.resolved`, `artifact.created`, `test.failed`, `repair.started`, `step.completed`, `run.completed`, `run.failed`.

---

# 11. API FastAPI — endpoints proposés

`/api/v1` :

```text
GET    /health                           health non sensible
GET    /ready                            état dépendances
GET    /dashboard/summary                KPIs réels
POST   /projects                         créer projet
GET    /projects                         lister projet selon droits
GET    /projects/{id}                    détail projet
PATCH  /projects/{id}                    métadonnées autorisées
POST   /projects/{id}/runs               lancer run (idempotence)
GET    /runs/{id}                        statut + étapes
GET    /runs/{id}/events                 SSE, reprise Last-Event-ID
POST   /runs/{id}/cancel                 annulation
POST   /runs/{id}/resume                 reprise autorisée
GET    /runs/{id}/artifacts              liste artefacts
GET    /artifacts/{id}/download          téléchargement avec ACL
POST   /runs/{id}/approvals/{approval_id}/decision
GET    /providers                        adapters + connexions
POST   /providers/{kind}/validate         test de connexion consenti
PUT    /providers/{kind}/configuration   config non-secrète + secret via store
GET    /providers/{kind}/models          découverte / cache
GET    /local-runtimes                   détecter via bridge local
POST   /knowledge/documents              upload/indexer
GET    /knowledge/documents              liste et statut
POST   /knowledge/search                 recherche avec citations
GET    /templates                        templates validés
POST   /templates/{id}/instantiate       instancier
POST   /projects/{id}/github/prepare     préparer push/PR
POST   /projects/{id}/github/publish     après approbation
GET    /evaluations/suites               listes
POST   /evaluations/suites/{id}/run      exécuter les evals
GET    /audit                            journal filtré par droits
```

Exiger validation Pydantic, OAuth local/identité fiable en team mode, rate limiting, réponses d'erreurs structurées, pagination, OpenAPI généré et tests d'autorisation.

---

# 12. Templates / factories par type de livrable

Chaque « Factory Recipe » est un manifest **versionné** avec : `name`, `supported_inputs`, `stack`, `template_repo`, `generator`, `validation_steps`, `allowed_tool_profile`, `artifact_manifest`, `post_build_checks`, `readme_template`.

## 12.1 `webapp-react-fastapi`

- React/Next.js frontend, FastAPI backend, PostgreSQL (option), exemples de CRUD, validation, gestion d'erreurs.
- Générer composants réels, pages, API, `.env.example`, scripts dev, Dockerfile(s), Compose, tests backend/frontend et README.
- Template sans secrets ni identifiants administrateur par défaut.

## 12.2 `python-api`

- FastAPI, Pydantic, SQLAlchemy, Alembic, pytest, healthcheck, OpenAPI.
- Contrat typé et exemples curl ; pas d'auth fictive annoncée comme robuste.

## 12.3 `excel-automation`

- Python `openpyxl` / `pandas` suivant besoin ; exemples de données synthétiques ; validation des formules, feuilles, références et export `.xlsx`.
- Livrer à la fois le fichier final et le code reproductible, sans macros dangereuses par défaut.

## 12.4 `powershell-automation`

- `.ps1`, modules Pester, `README`, paramètres, validation d'entrées et logs.
- Mode dry-run, refus de commandes privilégiées non approuvées ; pas d'accès système distant sans consentement.

## 12.5 `existing-github-feature`

- Import contrôlé (repo local ou GitHub autorisé), branche dédiée, code diff, tests, checklist revue, draft PR.
- Ne pas réécrire le dépôt complet ou effacer les modifications utilisateur.

## 12.6 Extensions P1/P2

- `github-action`, `data-pipeline`, `internal-dashboard`, `documentation-site`, `scheduled-report`, `cli-tool`, `terraform-module` (génération seulement, jamais `apply` automatique), `api-connector`, `test-suite-generator`.

---

# 13. GitHub et cycle logiciel complet

1. **Connexion :** en mode local, détecter `gh auth status` sans exposer le token ; proposer connexion officielle. En mode entreprise, privilégier **GitHub App** avec permissions limitées par repository.
2. **Accès :** l'utilisateur choisit explicitement repo/organisation ; vérifier permissions read/write.
3. **Workspace :** clone ou `git worktree`, branche `nfactory/<project-slug>/<run-id>`.
4. **Code :** modifications limitées à la tâche ; conserver un manifest des fichiers créés/modifiés.
5. **Checks :** lint, typecheck, tests, SAST/dépendances autorisées, scan de secrets.
6. **Revue :** comparaison `base...head`, résumé des modifications et risque résiduel.
7. **Approval :** demander confirmation de push + création de PR (séparée du bouton « générer »).
8. **PR :** `draft: true` par défaut, titre, description, checklist, résultats de tests vérifiés, lien vers artefacts accessibles, mention des limites.
9. **Human merge :** aucun auto-merge par défaut, pas de push direct sur branches protégées.
10. **Sync :** conserver le lien PR et permettre une nouvelle itération sur la même branche tant que l'utilisateur l'autorise.

**Ne pas confondre les statuts :** `local_commit_created`, `pushed`, `pr_created`, `merged` sont des faits séparés et vérifiés depuis GitHub.

---

# 14. Observability, qualité, évaluations et coûts

## 14.1 Tracing

Chaque run a un `trace_id` transversal. Propager `trace_id/run_id/step_id` entre FastAPI, Redis, workers, LangGraph, tools et provider calls. Masquer les secrets et exclure le contenu sensible des logs par défaut.

**Métriques par provider et par agent :** appels, latence P50/P95, échecs, tokens (si fournis), coût estimé (si prix connu), tool errors, fallback et réparation.

**Métriques NFactory :**

- `end_to_end_delivery_rate` (livrables qui passent les critères réels) ;
- `first_pass_test_rate` ;
- `repair_success_rate` ;
- `time_to_preview` ;
- `time_to_draft_pr` ;
- `human_intervention_count` ;
- `cost_per_successful_delivery` ;
- `critical_policy_violation_count` (objectif zéro).

## 14.2 Evals

Créer `evals/` avec **au moins 30 scénarios** synthétiques versionnés : 10 web/API, 8 Excel, 6 PowerShell, 6 repo feature, plus cas adversariaux. Les scenarii sont distincts des tests de code.

À chaque version :

1. Vérifier respect du cahier des charges (requirements coverage).
2. Exécuter tests produits et validations déterministes.
3. Comparer l'intégrité des artefacts, citations RAG, permissions, taille du diff.
4. Comparer le taux de livraison réussi entre versions de prompts/modèles.
5. Produire un rapport JSON/HTML de régression ; **LLM-as-judge ne remplace pas les tests exécutables ni une revue humaine**.

## 14.3 Budget et cost control

- Budget configurable par run et par semaine ; les coûts d'abonnements locaux peuvent ne pas être mesurables précisément → afficher « consommation non disponible ».
- Estimation avant run lorsque la tarification et le volume sont connus, sinon « non estimable ».
- Cache intelligent avec TTL et isolement.
- Résumer le contexte, dédupliquer les appels et passer les tâches simples à un modèle adapté.
- Si quota atteint : pause, explication et choix explicite de modèle ; ne pas contourner une limite en changeant silencieusement de compte/fournisseur.

---

# 15. Sécurité, gouvernance et règles non négociables

**Ce projet est destiné à pouvoir servir un service IT d'une grande entreprise.** Aucune donnée interne réelle ne doit être transmise à un fournisseur externe sans autorisation et conformité aux règles internes. En mode démo, utiliser exclusivement des données fictives/publiques.

- **Least privilege :** par outil, repo, provider, exécution et projet.
- **Approval gates :** accès repo privé, envoi de données sensibles, command execution privilégiée, GitHub push/PR, scheduler, déploiement.
- **Séparation des plans :** instructions système/policies non modifiables par la documentation RAG ou les outputs d'agent.
- **Secrets :** `.env.example` sans secret ; clés réelles dans variable d'environnement ou stockage système chiffré. Ne pas mettre dans prompts, PR, fichiers générés, logs ou base vectorielle.
- **Isolation :** les agents ne touchent pas directement aux fichiers de configuration critiques de NFactory, aux credentials SSH/CLI ou au filesystem hors workspace.
- **Audit :** action, acteur, run, décision, diff/signature, erreurs, sans contenu secret.
- **Provenance :** mentionner les fichiers générés avec IA, vérifications effectuées, limites et approbations.
- **Données :** suppression et expiration, ACL de RAG, minimisation et contrôle d'envoi par provider.
- **GitHub :** permissions minimales, aucun `force push`, aucun auto-merge.
- **MCP :** facultatif, désactivé par défaut ; outils autorisés individuellement avec confirmation et politiques. Aucune dépendance MCP pour les flux locaux de base.

---

# 16. Monorepo attendu

```text
nfactory/
├── README.md
├── NFACTORY_MASTER_PLAN.md
├── IMPLEMENTATION_STATUS.md
├── .env.example
├── .gitignore
├── .github/workflows/ci.yml
├── compose.yaml
├── Makefile  # ou scripts/ équivalents cross-platform
├── docs/
│   ├── architecture.md
│   ├── decisions/
│   ├── security.md
│   ├── local-providers.md
│   ├── provider-matrix.md
│   └── user-guide.md
├── apps/
│   ├── dashboard/                # Next.js, TS, shadcn/ui
│   │   ├── app/
│   │   ├── components/
│   │   ├── lib/
│   │   └── tests/
│   ├── api/                      # FastAPI (Python)
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── routes/
│   │   │   ├── models/
│   │   │   ├── schemas/
│   │   │   ├── security/
│   │   │   └── services/
│   │   ├── migrations/
│   │   └── tests/
│   ├── worker/                   # LangGraph + jobs
│   │   ├── nfactory_worker/
│   │   │   ├── graph/
│   │   │   ├── agents/
│   │   │   ├── providers/
│   │   │   ├── tools/
│   │   │   ├── rag/
│   │   │   └── evaluations/
│   │   └── tests/
│   └── local-bridge/             # compagnon local (no creds extraction)
│       ├── app/
│       └── tests/
├── packages/
│   ├── shared-contracts/        # schema/OpenAPI types pour UI
│   ├── template-manifests/
│   └── ui/
├── templates/
│   ├── webapp-react-fastapi/
│   ├── python-api/
│   ├── excel-automation/
│   ├── powershell-automation/
│   └── github-feature/
├── evals/
│   ├── datasets/
│   ├── fixtures/
│   └── reports/
├── scripts/
│   ├── bootstrap.sh
│   ├── bootstrap.ps1
│   ├── doctor.py
│   ├── seed_demo.py
│   └── smoke_test.py
└── tests/
    └── e2e/
```

Les `packages` communs ne doivent pas créer une architecture inutilement compliquée : garder le strict nécessaire et documenter la raison de chaque sous-package.

---

# 17. Configuration automatique et secrets

## 17.1 `.env.example` — à générer tel quel avec valeurs adaptées

```dotenv
# NFactory core — valeurs locales sans secrets
NFACTORY_ENV=development
NFACTORY_MODE=local
NFACTORY_DEMO_MODE=true
NFACTORY_LOG_LEVEL=INFO
NFACTORY_DEFAULT_LOCALE=fr
DATABASE_URL=postgresql+asyncpg://nfactory:nfactory_dev_only@postgres:5432/nfactory
REDIS_URL=redis://redis:6379/0
ARTIFACT_STORAGE=local
ARTIFACT_ROOT=/data/artifacts
WORKSPACE_ROOT=/data/workspaces

# Guardrails
MAX_REPAIR_ATTEMPTS=3
MAX_AGENT_STEPS=100
MAX_CONCURRENT_RUNS=2
DEFAULT_RUN_TIMEOUT_SECONDS=1800
DEFAULT_PROVIDER_FALLBACK=ask_user
ALLOW_NETWORK_IN_CODE_SANDBOX=false
ALLOW_AUTO_PUSH=false
ALLOW_AUTO_MERGE=false
ALLOW_PRIVILEGED_EXECUTION=false

# API keys facultatives — laisser vides tant que l'utilisateur ne les fournit pas
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
DEEPSEEK_API_KEY=
ZAI_API_KEY=
MOONSHOT_API_KEY=
DASHSCOPE_API_KEY=
MINIMAX_API_KEY=

# Adapters custom/local
CUSTOM_LLM_BASE_URL=
CUSTOM_LLM_MODEL=
OLLAMA_BASE_URL=http://127.0.0.1:11434
LOCAL_BRIDGE_ENABLED=false
LOCAL_BRIDGE_URL=http://127.0.0.1:48321

# GitHub : utiliser de préférence gh login (local) ou GitHub App (team)
GITHUB_TOKEN=
GITHUB_APP_ID=
GITHUB_APP_INSTALLATION_ID=

# Auth : les valeurs secrètes doivent être générées avec un RNG sécurisé au bootstrap
NFACTORY_SESSION_SECRET=
```

**Attention :** les credentials de développement présents dans cet exemple sont **strictement réservés au Docker Compose local** ; les remplacer/générer automatiquement en environnement partagé. Les URL `127.0.0.1` dans les containers ne pointent pas sur la machine hôte : le bridge doit avoir une méthode de communication OS/Docker documentée, authentifiée et non exposée publiquement.

## 17.2 `doctor` automatisé

Créer `scripts/doctor.py` et une page de diagnostic affichant :

- Docker fonctionnel, version Compose, volumes/ports disponibles.
- Python/Node/pnpm/uv si utilisés hors Docker.
- Base de données, extension pgvector, Redis et API accessibles.
- `codex` installé ? version, disponibilité du runtime selon méthode publique.
- `claude` installé ? version, intégration autorisée/disponible.
- `gh` installé ? statut d'authentification **sans révéler tokens**.
- Providers API : configurés, non configurés ou test de connexion volontaire.
- Prérequis du sandbox executor.

## 17.3 Installation guidée

**Objectif :** `docker compose up --build` + ouverture du dashboard, dataset de démo en place ; l'application **ne doit pas planter** parce que les clés externes sont absentes.

- Prévoir `scripts/bootstrap.sh` et `scripts/bootstrap.ps1` (Windows).
- Créer `.env` depuis `.env.example` si absent ; générer des secrets locaux sans les imprimer dans les logs.
- Faire tourner automatiquement migrations et seed démo de façon idempotente.
- Lancer une suite de smoke tests.
- Fournir une commande unique `make dev` ou `scripts/dev.*` en complément.
- Pour les outils locaux Codex/Claude : proposer un bouton `Configurer` qui lance uniquement la procédure officielle ou affiche les commandes nécessaires ; **ne jamais demander de coller le token d'abonnement**.

**Limite honnête :** aucune application ne peut créer automatiquement les comptes, factures, clés API personnelles, consentements OAuth ou autorisations GitHub d'un utilisateur. **Préconfigurer les connecteurs ≠ authentifier les fournisseurs.**

---

# 18. Roadmap d'implémentation obligatoire

Chaque phase doit produire **une vraie démonstration fonctionnelle**. Ne pas démarrer la suivante avec une phase précédente cassée.

## PHASE 0 — Foundation et bootstrap (P0)

- [ ] Monorepo, conventions, lint/format, tests, lockfiles, Docker Compose.
- [ ] Next.js dashboard, FastAPI API, Redis, PostgreSQL + pgvector.
- [ ] SQLAlchemy/Alembic ; schéma minimal ; migrations automatisées.
- [ ] Démo sans API : fake provider, projets de démonstration, artefacts synthétiques.
- [ ] `doctor`, health/readiness, `.env.example`, setup Windows/Linux/macOS.
- [ ] README, architecture ADR et commandes de lancement.

**Validation :** un checkout propre démarre ; dashboard affiche des projets de démonstration et `GET /health` répond ; tests de base passent.

## PHASE 1 — Project Builder end-to-end (P0)

- [ ] Demande utilisateur, wizard, projet, run et étapes persistés.
- [ ] LangGraph planner → architect → builder → tester → reviewer simplifié.
- [ ] Templates `python-api` et `excel-automation` réellement générés.
- [ ] Tests sur artefacts, ZIP téléchargeable, timeline SSE.
- [ ] Checkpointing/reprise, annulation, erreurs normalisées.
- [ ] Worker Redis, limites du run, budget/cancellation.

**Validation :** générer une API avec tests passés et un Excel contenant vraies données/formules de démonstration. Vérifier que les deux sont téléchargeables et reproductibles.

## PHASE 2 — Multi-provider réel (P0/P1)

- [ ] `ModelProvider` stable, catalogue capacités et tests contractuels.
- [ ] OpenAI API et Anthropic API.
- [ ] DeepSeek, Z.ai/GLM, Moonshot/Kimi.
- [ ] Qwen, MiniMax, custom OpenAI-compatible, Ollama.
- [ ] UX configuration, validation de connection, labels honnêtes.
- [ ] Routage par rôle, fallback avec consentement, coûts et erreurs.

**Validation :** tous les adaptateurs passent tests mockés/contractuels ; un test live uniquement si l'utilisateur a connecté un provider ; aucun secret dans les logs.

## PHASE 3 — Agent factory avancée (P0/P1)

- [ ] Dix rôles, schémas structurés, exécution conditionnelle des agents.
- [ ] RAG complet : ingestion, embeddings, pgvector, full-text, ACL, citations.
- [ ] `webapp-react-fastapi` et `powershell-automation`.
- [ ] Sandbox de build/test isolé et limites strictes.
- [ ] Repair loop, static review, doc generation, artefacts et preview.
- [ ] Projet évolutif : nouvelle demande → patch sur même projet.

**Validation :** démo « IT licence manager » : preview React+API, export Excel, tests, sources RAG citées, réparations tracées si erreurs.

## PHASE 4 — Coding agents locaux + GitHub (P1)

- [ ] Local bridge et détection sûre de `codex`/`claude`.
- [ ] Codex runtime via SDK/app-server/CLI officiel selon usage autorisé.
- [ ] Claude Code : handoff natif opérationnel et runtime programmatique seulement si conformité vérifiée.
- [ ] Git local, worktrees, clone contrôlé ; `gh` auth local ou GitHub App.
- [ ] Branch/commit/push, PR brouillon **après approbation**.
- [ ] Ecran diff, tests, rollback, statut PR vérifié.

**Validation :** modifier un repo de démonstration, voir diff, réussir tests, créer une PR uniquement sur un repository de test explicitement autorisé. Sinon chemin ZIP opérationnel.

## PHASE 5 — Dashboard premium + évaluations (P1)

- [ ] Overview KPIs réels et filtres.
- [ ] Live agent graph, traces, tests, budget, benchmark par provider.
- [ ] Evals/fixtures, tests de régression, tests sécurité RAG, scoring.
- [ ] Approval center, audit et contrôles d'accès.
- [ ] Recipes réutilisables et templates configurables.
- [ ] E2E Playwright et tests de charge baseline (pas promesse « 1000 utilisateurs » sans mesure).

**Validation :** jeu de 30 cas ; rapport de succès, latence, coût et sécurité avec sources de mesures ; aucun faux chiffre.

## PHASE 6 — Enterprise-ready (P2)

- [ ] Multi-user et RBAC étendu, SSO, politique de rétention.
- [ ] Connector SDK et option MCP.
- [ ] Plugins de templates, packs internes/golden paths.
- [ ] Déploiement cloud, worker autoscaling et observability externe.
- [ ] Gestion des données sensibles et des politiques provider par workspace.
- [ ] Analyse de sécurité indépendante, revue juridique/licences avant distribution.

**Validation :** tests d'isolation multi-tenant, revue permissions, runbook incident, politique de sauvegarde/restauration.

---

# 19. Critères d'acceptation / Definition of Done

Une fonctionnalité est **DONE** seulement si :

1. Elle est branchée à une API réelle ou un mock **explicitement affiché comme tel**.
2. Les données sont persistées et retrouvées après redémarrage si cela fait partie du flux.
3. Elle a un test automatisé positif et négatif.
4. Les échecs sont visibles et compréhensibles dans l'UI.
5. Elle respecte les permissions, limites et politiques.
6. Elle est documentée et exécutable par une autre personne.
7. Elle est reliée à un scénario démo reproductible.

## 19.1 Tests indispensables

- **Unitaires :** provider adapters, state machine, validation, ACL, pricing/usage, plan outputs.
- **Intégration :** Postgres/pgvector, Redis job queue, SSE, RAG retrieval, migrations.
- **E2E :** création projet, run avec mock, ZIP, page project, reprise, approvals.
- **Sécurité :** prompt injection dans document, accès au mauvais projet, workspace path traversal, SSRF, secret leakage, absence d'auto-push, unauthorized action.
- **Sandbox :** temps/CPU limité, réseau bloqué, fichiers hors périmètre inaccessibles.
- **Durabilité :** redémarrage du worker pendant un run, idempotence, annulation, retry provider.
- **Provider contract :** stream, tool calls, unsupported features, timeouts, 401, 429, quotas.
- **Licence/intégration :** ne pas tenter de lire/extraire les credentials des binaires locaux.

## 19.2 Démo finale mesurable

| Étape | Ce qu'on doit voir |
|---|---|
| 1 | Dashboard professionnel, providers visibles, nouvelles demandes |
| 2 | Saisie « licence manager », plan généré et approuvé |
| 3 | Graphe d'agents et événements réels |
| 4 | Sources RAG récupérées avec citations vérifiables |
| 5 | Répertoire webapp React/FastAPI, Excel et tests réels |
| 6 | Échec simulé puis correction traçable, si la démo inclut le scénario de réparation |
| 7 | Preview fonctionnelle et téléchargement ZIP |
| 8 | Revue/diff et demande de validation pour GitHub |
| 9 | PR brouillon si connecté/autorisé, sinon état bloqué explicite |
| 10 | Rapport des métriques réelles du run |

**Règle de produit :** ne jamais afficher un « Project ready » alors que le build ou les tests obligatoires ont échoué. Afficher `Ready for review`, `Partial` ou `Failed`, avec détails.

---

# 20. Ce qui nécessite réellement une intervention utilisateur

Claude Code doit automatiser la **mise en place du code**, de l'infrastructure, de la configuration *non secrète*, des tests et de la démo. Il ne peut légalement ni techniquement effectuer à la place d'un utilisateur les étapes suivantes sans sa participation :

1. Créer/activer un compte et obtenir une **clé API réelle** chez un fournisseur.
2. S'authentifier dans le flux officiel **ChatGPT/Codex**, **Claude Code** ou **GitHub** et consentir aux permissions.
3. Choisir quels dépôts ou documents internes NFactory peut lire, modifier ou transmettre à un modèle.
4. Autoriser explicitement un push, une PR, un déploiement, un script privilégié ou un coût réel.
5. Faire approuver les politiques internes de l'entreprise avant d'utiliser ses données réelles.

**Pour minimiser ce travail :** dès le démarrage, toutes les fiches providers sont précréées avec noms, paramètres et statuts ; un utilisateur novice voit un simple bouton « Connecter » et non un YAML complexe. Lorsqu'une connexion manque, le système travaille en **mode démo sans clé** et n'invente jamais une connexion réelle.

---

# 21. Exécution en pratique : ordre pour Claude Code

Après lecture de ce fichier :

1. Affiche rapidement l'état initial du repository et les outils détectés.
2. Crée le plan de tâches versionné dans `IMPLEMENTATION_STATUS.md`.
3. Exécute **PHASE 0 puis PHASE 1** en priorité jusqu'à avoir un produit testable de bout en bout.
4. Construis ensuite les providers et la RAG plutôt que d'ajouter des écrans décoratifs.
5. Conserve les features P1/P2 documentées et prépare les interfaces/extensions maintenant, mais n'annonce pas leur implémentation sans preuve.
6. À chaque phase, exécute la suite de tests et répare les régressions.
7. Continue vers les phases suivantes lorsque possible.
8. Conclus avec une table : fonctionnalité, état `DONE/PARTIAL/BLOCKED`, commande de validation, preuve.

**Première démonstration requise :** l'utilisateur décrit une API Python ou une automatisation Excel → NFactory crée les fichiers → tests → ZIP → dashboard avec trace complète. Cette tranche fonctionnelle est la base des workflows plus ambitieux.

---

# 22. Sources techniques prioritaires à revérifier à l'implémentation

Les capacités, modalités d'authentification et noms de modèles évoluent. **Claude Code doit consulter les documents officiels actuels avant d'intégrer chaque runtime.**

- OpenAI Codex platform/SDK/app-server : https://developers.openai.com/blog/codex-as-a-platform
- OpenAI « Sign in with ChatGPT » (OSS/local et conditions d'éligibilité) : https://developers.openai.com/siwc/quickstart
- OpenAI shared ChatGPT plan et Codex app-server : https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server
- OpenAI SIWC limitations : https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations
- Anthropic Claude Code — **Legal and compliance** : https://code.claude.com/docs/en/legal-and-compliance
- Anthropic Claude Code CLI : https://docs.anthropic.com/en/docs/claude-code/cli-usage
- DeepSeek API : https://api-docs.deepseek.com/quick_start/agent_integrations/
- Z.ai GLM docs : https://docs.z.ai/
- Moonshot/Kimi developer console : https://platform.moonshot.ai/
- Alibaba/Qwen endpoints et régions : https://help.aliyun.com/en/model-studio/base-url
- LiteLLM provider directory (aide d'intégration, pas unique source de vérité) : https://docs.litellm.ai/docs/providers
- GitHub REST API — PR : https://docs.github.com/en/rest/pulls/pulls
- LangGraph : https://docs.langchain.com/oss/python/langgraph/overview
- pgvector : https://github.com/pgvector/pgvector
- OWASP LLM/Agent security : https://genai.owasp.org/

**Important :** ces sources décrivent les interfaces et règles accessibles au moment de la rédaction ; elles ne donnent pas une autorisation automatique de distribuer NFactory en mode commercial ou d'utiliser les abonnements privés de tiers via un backend.

---

## Résumé final du produit à construire

> **NFactory transforme une intention en projet logiciel réel.** Elle choisit un workflow adapté, utilise des modèles API ou des coding agents locaux selon les droits de l'utilisateur, exploite une base documentaire RAG via pgvector, orchestre ses dix rôles LangGraph, génère du code et des automatisations, exécute des tests dans un environnement isolé, tente de corriger les erreurs, propose une prévisualisation et prépare des livrables ou une pull request après validation. Tout est visible dans un dashboard avancé, mesurable, traçable et gouvernable.

**Priorité absolue : fonctionner réellement, puis devenir un monstre fonctionnel — jamais l'inverse.**
