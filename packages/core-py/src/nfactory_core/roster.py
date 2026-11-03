"""The agent roster (spec §5) and which steps a run actually executes.

Ten roles exist, but a run only calls the models it needs: orchestration (A4), test
verdicts (A7) and delivery permissions (A10) are code, and the architect only designs
applications. `plan_steps` is the single place that decides it; the API creates the
step rows from it and the worker skips what it marks inactive.

Interface: `AgentRole`, `AGENTS`, `PlannedStep`, `plan_steps`, `new_step_rows`, `APP_TYPES`.
"""

from dataclasses import dataclass
from typing import Literal

from nfactory_core.models import RunStep
from nfactory_core.pipeline import PIPELINE_STEPS
from nfactory_core.states import StepState

# Project types that have an application architecture to design.
APP_TYPES = frozenset({"webapp", "api", "feature"})


@dataclass(frozen=True)
class AgentRole:
    code: str | None  # A1..A10 from the spec; None for roles the spec does not number
    role: str
    label: str
    kind: Literal["model", "code"]  # "model": answers through a routed engine
    duty: str


AGENTS: tuple[AgentRole, ...] = (
    AgentRole(
        "A1",
        "requirements",
        "Analyste des besoins",
        "model",
        "Transforme la demande en cahier des charges structuré.",
    ),
    AgentRole(
        "A2",
        "planner",
        "Planificateur",
        "model",
        "Découpe le travail en tâches avec critères de réussite.",
    ),
    AgentRole(
        "A3",
        "architect",
        "Architecte",
        "model",
        "Conçoit la pile, l'arborescence et la sécurité d'une application.",
    ),
    AgentRole(
        "A4",
        "orchestrator",
        "Orchestrateur",
        "code",
        "Enchaîne les étapes, reprend après une panne, applique budget et annulation.",
    ),
    AgentRole(
        "A5",
        "builder",
        "Constructeur",
        "code",
        "Produit le code de l'application à partir de la recette du type de projet.",
    ),
    AgentRole(
        "A6",
        "automation",
        "Automaticien",
        "code",
        "Produit le classeur, le document ou le script à partir de la recette.",
    ),
    AgentRole(
        "A7",
        "tester",
        "Testeur",
        "code",
        "Lance les vrais contrôles et tests ; seul leur résultat fait foi.",
    ),
    AgentRole(
        "A8",
        "debugger",
        "Correcteur",
        "model",
        "Analyse un échec et propose une correction ciblée, en nombre limité.",
    ),
    AgentRole(
        "A9",
        "reviewer",
        "Relecteur",
        "model",
        "Relit le livrable : risques, style, recommandations.",
    ),
    AgentRole(
        "A10",
        "security_delivery",
        "Sécurité et livraison",
        "code",
        "Scanne, emballe le livrable et décide des permissions.",
    ),
    AgentRole(None, "documenter", "Rédacteur", "model", "Explique le livrable à l'utilisateur."),
)


@dataclass(frozen=True)
class PlannedStep:
    name: str
    role: str
    active: bool
    reason: str | None = None  # why an inactive step is skipped, in French


_NO_ARCHITECTURE = (
    "Aucune architecture applicative à concevoir pour ce type de livrable : "
    "l'architecte n'est pas appelé."
)


def plan_steps(project_type: str) -> tuple[PlannedStep, ...]:
    app = project_type in APP_TYPES
    planned: list[PlannedStep] = []
    for name, role in PIPELINE_STEPS:
        if name == "architect" and not app:
            planned.append(PlannedStep(name, role, active=False, reason=_NO_ARCHITECTURE))
        elif name == "build":
            planned.append(PlannedStep(name, "builder" if app else "automation", active=True))
        else:
            planned.append(PlannedStep(name, role, active=True))
    return tuple(planned)


def new_step_rows(run_id: str, project_type: str) -> list[RunStep]:
    """The step rows of a new run: skipped steps are visible from the start."""
    return [
        RunStep(
            run_id=run_id,
            position=position,
            name=step.name,
            agent_role=step.role,
            state=(StepState.PENDING if step.active else StepState.SKIPPED).value,
            output={} if step.active else {"skipped": step.reason},
        )
        for position, step in enumerate(plan_steps(project_type))
    ]
