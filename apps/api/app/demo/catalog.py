"""Synthetic demo content (spec F40). Pure data, no database access.

User-facing text is French (product default locale).
"""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

from nfactory_core.pipeline import PIPELINE_STEPS
from nfactory_core.roster import plan_steps as roster_plan
from nfactory_core.states import RunState, StepState

DEMO_EPOCH = datetime(2026, 10, 28, 9, 0, tzinfo=UTC)

# Demo runs use the real pipeline steps, so the UI shows them the same way.
PIPELINE = PIPELINE_STEPS


@dataclass(frozen=True)
class DemoProject:
    slug: str
    title: str
    type: str
    template: str
    description: str
    run_state: RunState
    duration_minutes: int
    cost_usd: float | None
    error: str | None = None
    approval_summary: str | None = None


DEMO_PROJECTS: tuple[DemoProject, ...] = (
    DemoProject(
        slug="licences",
        title="Gestionnaire de licences IT",
        type="webapp",
        template="webapp-react-fastapi",
        description="Dashboard React, API Python, export Excel et alertes d'expiration.",
        run_state=RunState.COMPLETED,
        duration_minutes=14,
        cost_usd=0.42,
    ),
    DemoProject(
        slug="inventory",
        title="API d'inventaire matériel",
        type="api",
        template="python-api",
        description="API FastAPI avec CRUD des équipements, OpenAPI et tests pytest.",
        run_state=RunState.COMPLETED,
        duration_minutes=6,
        cost_usd=0.11,
    ),
    DemoProject(
        slug="kpi",
        title="Rapport KPI hebdomadaire",
        type="excel",
        template="excel-automation",
        description="Fusion de deux exports CSV en un Excel multi-onglets avec formules.",
        run_state=RunState.FAILED,
        duration_minutes=9,
        cost_usd=0.18,
        error="Tests en échec après 3 tentatives de réparation.",
    ),
    DemoProject(
        slug="ps",
        title="Inventaire logiciel PowerShell",
        type="powershell",
        template="powershell-automation",
        description="Script d'inventaire avec -WhatIf, tests Pester et rapport CSV.",
        run_state=RunState.APPROVAL_PENDING,
        duration_minutes=3,
        cost_usd=None,
        approval_summary="Valider le plan avant de générer le script PowerShell.",
    ),
)


@dataclass(frozen=True)
class StepPlan:
    name: str
    role: str
    state: StepState
    attempts: int
    error: str | None = None
    output: dict[str, Any] = field(default_factory=dict)


# Repair history of the failed demo run, shaped like the worker's repair_log.
_DEMO_REPAIRS = [
    {
        "attempt": attempt,
        "step": "tests",
        "failure": "Tests (pytest) : test_kpi_hebdo : KeyError 'semaine'",
        "cause": cause,
        "files": files,
    }
    for attempt, cause, files in (
        (1, "Colonne « semaine » absente du second export CSV.", ["kpi/fusion.py"]),
        (2, "Normalisation des en-têtes avant la fusion.", ["kpi/lecture.py", "kpi/fusion.py"]),
        (3, "Valeur par défaut pour les semaines manquantes.", ["kpi/fusion.py"]),
    )
]


def plan_steps(run_state: RunState, project_type: str) -> list[StepPlan]:
    """Step outcomes consistent with the run's final state and its project type."""
    planned = {step.name: step for step in roster_plan(project_type)}
    return [
        StepPlan(s.name, planned[s.name].role, StepState.SKIPPED, 0)
        if not planned[s.name].active
        else replace(s, role=planned[s.name].role)
        for s in _outcomes(run_state)
    ]


def _outcomes(run_state: RunState) -> list[StepPlan]:
    if run_state is RunState.COMPLETED:
        return [StepPlan(n, r, StepState.SUCCEEDED, 1) for n, r in PIPELINE]
    if run_state is RunState.FAILED:
        # Tests keep failing after 3 repairs: later steps never run.
        steps: list[StepPlan] = []
        for n, r in PIPELINE:
            if n == "tests":
                failed = StepPlan(n, r, StepState.FAILED, 4, "3 tests pytest en échec")
                steps.append(replace(failed, output={"repairs": _DEMO_REPAIRS}))
            elif steps and steps[-1].state in {StepState.FAILED, StepState.SKIPPED}:
                steps.append(StepPlan(n, r, StepState.SKIPPED, 0))
            else:
                steps.append(StepPlan(n, r, StepState.SUCCEEDED, 1))
        return steps
    # Waiting for approval: only requirements and plan are done.
    return [
        StepPlan(n, r, StepState.SUCCEEDED if i < 2 else StepState.PENDING, 1 if i < 2 else 0)
        for i, (n, r) in enumerate(PIPELINE)
    ]
