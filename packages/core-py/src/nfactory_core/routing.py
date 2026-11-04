"""Role routing (spec §6.3): which engine answers for which agent.

The workspace keeps a `RoutingConfig`. At launch, `freeze_routing` turns it into the
run's `provider_config`, so a run keeps the engines it started with. A routed run never
switches engine on its own: on failure it asks the user (`fallback="ask_user"`) or
fails (`"none"`).

Interface: `ROLES`, `ROLE_LABELS`, `Route`, `RoutingConfig`, `ConnectionFacts`,
`freeze_routing`, `policy_violation`, `demo_routing`, `engines`, `RoutingError`, `DEMO_PROVIDER`,
`DEMO_MODEL_ID`.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from nfactory_core.providers.residency import Zone
from nfactory_core.providers.specs import SPECS, label

# The agents that call a model; builder and tester are deterministic (recipes, runner).
ROLE_LABELS: dict[str, str] = {
    "requirements": "Analyste des besoins",
    "planner": "Planificateur",
    "architect": "Architecte",
    "debugger": "Correcteur",
    "reviewer": "Relecteur",
    "documenter": "Rédacteur",
}
ROLES: tuple[str, ...] = tuple(ROLE_LABELS)

# The offline demo engine (ADR-0004); it lives in the worker, its name lives here.
DEMO_PROVIDER = "demo"
DEMO_MODEL_ID = "fake-demo-1"

FallbackMode = Literal["ask_user", "none"]
PriceLookup = Callable[[str, str], dict[str, Any] | None]


class Route(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    model: str = Field(min_length=1, max_length=200)

    @field_validator("provider")
    @classmethod
    def _chat_engine(cls, value: str) -> str:
        spec = SPECS.get(value)
        if spec is None or spec.protocol == "coding_agent":
            raise ValueError(f"moteur inconnu ou non conversationnel : {value}")
        return value


class RoutingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default: Route | None = None
    roles: dict[str, Route] = Field(default_factory=dict)
    fallback: FallbackMode = "ask_user"
    local_only: bool = False
    # Data policy (legal review §2): remote engines must process in the EU/EEA.
    eu_only: bool = False

    @field_validator("roles")
    @classmethod
    def _known_roles(cls, value: dict[str, Route]) -> dict[str, Route]:
        unknown = set(value) - set(ROLES)
        if unknown:
            raise ValueError(f"rôles inconnus : {', '.join(sorted(unknown))}")
        return value

    @property
    def configured(self) -> bool:
        return self.default is not None or bool(self.roles)

    def route_for(self, role: str) -> Route | None:
        return self.roles.get(role) or self.default


@dataclass(frozen=True)
class ConnectionFacts:
    kind: str
    status: str
    local: bool
    zone: Zone = "unknown"  # where a remote engine processes the data
    country: str = ""


class RoutingError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def freeze_routing(
    config: RoutingConfig,
    connections: Mapping[str, ConnectionFacts],
    price: PriceLookup,
) -> dict[str, Any]:
    """The run's `provider_config`: one resolved route per role, with its price."""
    routes: dict[str, dict[str, Any]] = {}
    for role in ROLES:
        route = config.route_for(role)
        if route is None:
            raise RoutingError(
                "routing_incomplete",
                f"Aucun moteur pour le rôle « {ROLE_LABELS[role]} » : choisissez un moteur "
                "par défaut ou un moteur pour ce rôle dans Moteurs IA.",
            )
        facts = connections.get(route.provider)
        if facts is None or facts.status != "connected":
            raise RoutingError(
                "provider_not_ready",
                f"{label(route.provider)} n'est pas connecté : testez la connexion dans "
                "Moteurs IA avant de lancer un run.",
            )
        violation = policy_violation(facts, local_only=config.local_only, eu_only=config.eu_only)
        if violation is not None:
            raise violation
        routes[role] = {
            "provider": route.provider,
            "model": route.model,
            "pricing": price(route.provider, route.model),
        }
    return {
        "mode": "routed",
        "routes": routes,
        "fallback": config.fallback,
        "local_only": config.local_only,
        "eu_only": config.eu_only,
    }


def policy_violation(
    facts: ConnectionFacts, *, local_only: bool, eu_only: bool
) -> RoutingError | None:
    """Why the workspace's data policy refuses this engine, or None."""
    name = label(facts.kind)
    if local_only and not facts.local:
        return RoutingError(
            "local_only_violation",
            f"Mode « local uniquement » : {name} est un service distant. "
            "Choisissez un moteur local ou désactivez ce mode.",
        )
    if eu_only and not facts.local and facts.zone != "eu":
        where = (
            f"hors de l'Union européenne ({facts.country})"
            if facts.zone == "outside_eu"
            else "dans un pays non documenté"
        )
        return RoutingError(
            "eu_only_violation",
            f"Politique « UE ou local uniquement » : {name} traite les données {where}. "
            "Choisissez un moteur hébergé dans l'UE ou local, ou changez cette politique "
            "dans Moteurs IA.",
        )
    return None


def demo_routing() -> dict[str, Any]:
    """`provider_config` of a run answered by the demo engine: no AI, flagged DEMO."""
    route = {"provider": DEMO_PROVIDER, "model": DEMO_MODEL_ID, "pricing": None}
    return {
        "mode": "demo",
        "routes": {role: dict(route) for role in ROLES},
        "fallback": "none",
        "local_only": True,
        "eu_only": False,
    }


def engines(provider_config: Mapping[str, Any] | None) -> dict[str, dict[str, str]]:
    """Role -> {provider, model} of a run, also for runs launched before routing existed."""
    config = provider_config or {}
    routes = config.get("routes")
    if not isinstance(routes, Mapping):
        routes = demo_routing()["routes"] if config.get("default") == "demo" else {}
    return {
        role: {"provider": str(route["provider"]), "model": str(route["model"])}
        for role, route in routes.items()
        if isinstance(route, Mapping) and "provider" in route and "model" in route
    }
