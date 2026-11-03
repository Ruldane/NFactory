"""Engines an eval bench may run on (task 5.5, spec F35).

`demo` is the deterministic engine. Any other engine is `<connection kind>:<model>` and
must be a connection the user saved and tested in Moteurs IA ("connected"): the bench
freezes it like a run's routing (catalog price included) and opens it through
`build_engines`, so the key is read from the secret store at the last moment and never
leaves the adapter. A real engine is called for real: the user asks for it by name.

Interface: EngineSpec, EngineError, parse_engine, open_engine.
"""

from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from nfactory_core.config import Settings
from nfactory_core.connections import connection_facts, workspace_connections
from nfactory_core.models import ModelCatalogEntry
from nfactory_core.providers import SPECS, pricing_from
from nfactory_core.routing import Route, RoutingConfig, RoutingError, freeze_routing
from nfactory_worker.agents import Engines, demo_llm
from nfactory_worker.jobs.engines import NoModelConfiguredError, build_engines
from nfactory_worker.providers.fake import FAKE_MODEL_ID

DEMO = "demo"


class EngineError(Exception):
    """The engine cannot be used for a bench; message in French."""


@dataclass(frozen=True)
class EngineSpec:
    provider: str  # "demo" or a connection kind
    model: str

    @property
    def demo(self) -> bool:
        return self.provider == DEMO

    @property
    def label(self) -> str:
        return DEMO if self.demo else f"{self.provider}:{self.model}"

    def meta(self) -> dict[str, Any]:
        if self.demo:
            return {"label": DEMO, "provider": "fake", "model": FAKE_MODEL_ID, "demo": True}
        return {"label": self.label, "provider": self.provider, "model": self.model, "demo": False}


def parse_engine(text: str) -> EngineSpec:
    if text == DEMO:
        return EngineSpec(DEMO, FAKE_MODEL_ID)
    provider, _, model = text.partition(":")
    spec = SPECS.get(provider)
    if spec is None or spec.protocol == "coding_agent":
        raise EngineError(f"Moteur inconnu ou non conversationnel : « {provider} ».")
    if not model.strip():
        raise EngineError(f"Indiquez le modèle : « {provider}:<modèle> ».")
    return EngineSpec(provider, model.strip())


async def open_engine(
    spec: EngineSpec, session: AsyncSession, workspace_id: str, settings: Settings
) -> Engines:
    if spec.demo:
        return Engines.single(demo_llm())
    route = Route(provider=spec.provider, model=spec.model)
    facts = connection_facts(await workspace_connections(session, workspace_id))
    entry = await session.get(ModelCatalogEntry, (spec.provider, spec.model))
    pricing = pricing_from(entry.capabilities or {}) if entry else None
    price = asdict(pricing) if pricing else None
    try:
        config = freeze_routing(
            RoutingConfig(default=route, fallback="none"), facts, lambda _p, _m: price
        )
        engines = await build_engines(session, config, workspace_id, settings)
    except RoutingError as exc:
        raise EngineError(exc.message) from None
    except NoModelConfiguredError as exc:
        raise EngineError(str(exc)) from None
    # A bench never pauses for a human decision: a failing engine fails its case.
    return Engines(engines.llms, fallback="none")
