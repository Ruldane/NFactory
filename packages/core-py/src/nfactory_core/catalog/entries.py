"""Every project type NFactory knows, code and non-code (spec §12).

Adding a type = one entry here + one recipe package in the worker.
"""

from nfactory_core.catalog.types import RecipeInfo

CATALOG: tuple[RecipeInfo, ...] = (
    # Phase 1
    RecipeInfo(
        kind="python-api",
        project_type="api",
        label="API Python",
        description="API FastAPI avec CRUD, validation, OpenAPI, base SQLite et tests pytest.",
        deliverable="code",
        outputs=("Projet complet (ZIP)", "Tests exécutés", "README"),
        phase=1,
    ),
    RecipeInfo(
        kind="excel-automation",
        project_type="excel",
        label="Classeur Excel",
        description=(
            "Classeur .xlsx multi-onglets avec formules, KPI et graphique, "
            "plus le script qui le régénère."
        ),
        deliverable="non-code",
        outputs=("Fichier .xlsx", "Script reproductible", "Tests des formules"),
        phase=1,
    ),
    RecipeInfo(
        kind="document",
        project_type="document",
        label="Document Word",
        description="Procédure, rapport ou note structurée au format .docx, avec sa source.",
        deliverable="non-code",
        outputs=("Fichier .docx", "Source Markdown", "Contrôle de structure"),
        phase=1,
    ),
    # Phase 3
    RecipeInfo(
        kind="webapp-react-fastapi",
        project_type="webapp",
        label="Application web",
        description=(
            "Frontend React (Vite), backend FastAPI, Docker Compose et tests des deux côtés."
        ),
        deliverable="code",
        outputs=("Projet complet (ZIP)", "Tests backend et frontend exécutés", "README"),
        phase=3,
    ),
    RecipeInfo(
        kind="powershell-automation",
        project_type="powershell",
        label="Script PowerShell",
        description="Script .ps1 avec paramètres, mode -WhatIf, journalisation et tests Pester.",
        deliverable="code",
        outputs=("Script .ps1", "Tests Pester", "README"),
        phase=3,
    ),
    # Phase 4
    RecipeInfo(
        kind="existing-github-feature",
        project_type="feature",
        label="Repo existant",
        description="Ajout d'une fonctionnalité dans un dépôt existant, sur une branche dédiée.",
        deliverable="code",
        outputs=("Diff", "Tests", "Pull request brouillon"),
        phase=4,
    ),
    # Phase 6: extensions (spec §12.6)
    RecipeInfo(
        kind="cli-tool",
        project_type="cli",
        label="Outil en ligne de commande",
        description="Outil CLI Python avec options, aide intégrée et tests.",
        deliverable="code",
        outputs=("Projet complet (ZIP)", "Tests exécutés"),
        phase=6,
    ),
    RecipeInfo(
        kind="data-pipeline",
        project_type="data-pipeline",
        label="Pipeline de données",
        description="Extraction, transformation et chargement de fichiers ou de bases.",
        deliverable="code",
        outputs=("Projet complet (ZIP)", "Jeu de données d'exemple"),
        phase=6,
    ),
    RecipeInfo(
        kind="api-connector",
        project_type="api-connector",
        label="Connecteur d'API",
        description="Client typé pour une API tierce, avec gestion des erreurs et tests.",
        deliverable="code",
        outputs=("Projet complet (ZIP)", "Tests exécutés"),
        phase=6,
    ),
    RecipeInfo(
        kind="github-action",
        project_type="github-action",
        label="Workflow GitHub Actions",
        description="Workflow CI/CD validé, sans secret en clair.",
        deliverable="code",
        outputs=("Fichier workflow", "README"),
        phase=6,
    ),
    RecipeInfo(
        kind="terraform-module",
        project_type="terraform",
        label="Module Terraform",
        description="Module d'infrastructure (génération seule, jamais d'apply automatique).",
        deliverable="code",
        outputs=("Module Terraform", "Plan de validation"),
        phase=6,
    ),
    RecipeInfo(
        kind="test-suite-generator",
        project_type="test-suite",
        label="Suite de tests",
        description="Tests automatisés pour un code existant.",
        deliverable="code",
        outputs=("Tests", "Rapport de couverture"),
        phase=6,
    ),
    RecipeInfo(
        kind="documentation-site",
        project_type="documentation-site",
        label="Site de documentation",
        description="Site statique de documentation (guides, runbooks) prêt à publier.",
        deliverable="non-code",
        outputs=("Site statique (ZIP)", "Sources Markdown"),
        phase=6,
    ),
    RecipeInfo(
        kind="scheduled-report",
        project_type="scheduled-report",
        label="Rapport planifié",
        description="Rapport périodique (PDF ou Excel) produit à partir de sources de données.",
        deliverable="non-code",
        outputs=("Rapport", "Planification"),
        phase=6,
    ),
    RecipeInfo(
        kind="presentation",
        project_type="presentation",
        label="Présentation",
        description="Support .pptx structuré à partir d'un brief.",
        deliverable="non-code",
        outputs=("Fichier .pptx", "Plan détaillé"),
        phase=6,
    ),
)
