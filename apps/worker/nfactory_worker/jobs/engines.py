"""Turn a run's frozen `provider_config` into its engines (one LLM per agent role).

Keys are read from the secret store here, at the last moment, and stay inside the
adapters. A route whose connection is gone or unusable fails the run with the reason.
"""

from collections.abc import Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from nfactory_core.config import Settings
from nfactory_core.connections import ProviderUnusableError, open_provider, workspace_connections
from nfactory_core.providers import ModelProvider, Pricing, label
from nfactory_core.routing import DEMO_PROVIDER, demo_routing
from nfactory_core.secrets import SecretKeyMissingError, SecretStore, SecretUnreadableError
from nfactory_worker.agents import LLM, Engines, demo_llm


class NoModelConfiguredError(RuntimeError):
    """No engine for this run: nothing is called rather than a silent pick."""


async def build_engines(
    session: AsyncSession,
    provider_config: Mapping[str, Any] | None,
    workspace_id: str,
    settings: Settings,
) -> Engines:
    config = dict(provider_config or {})
    if not isinstance(config.get("routes"), Mapping):
        # Runs launched before routing existed ran on the demo engine.
        if not settings.nfactory_demo_mode and config.get("default") != "demo":
            raise NoModelConfiguredError(
                "Aucun moteur IA pour ce run : connectez un fournisseur dans Moteurs IA "
                "ou activez le mode démo."
            )
        config = demo_routing()
    store = SecretStore(settings.nfactory_secret_key.get_secret_value())
    rows = await workspace_connections(session, workspace_id)
    providers: dict[str, ModelProvider] = {}
    llms: dict[str, LLM] = {}
    for role, route in config["routes"].items():
        kind, model = str(route["provider"]), str(route["model"])
        if kind == DEMO_PROVIDER:
            llms[role] = demo_llm()
            continue
        if kind not in providers:
            row = rows.get(kind)
            if row is None:
                raise NoModelConfiguredError(
                    f"{label(kind)} n'est plus configuré : reconnectez-le dans Moteurs IA."
                )
            try:
                providers[kind] = await open_provider(
                    session,
                    row,
                    store,
                    allowed_private_hosts=frozenset(settings.nfactory_allowed_private_llm_hosts),
                )
            except (ProviderUnusableError, SecretUnreadableError, SecretKeyMissingError) as exc:
                raise NoModelConfiguredError(str(exc)) from None
        pricing = route.get("pricing")
        llms[role] = LLM(
            providers[kind],
            kind,
            model,
            demo=False,
            pricing=Pricing(**pricing) if isinstance(pricing, Mapping) else None,
        )
    return Engines(llms, fallback="ask_user" if config.get("fallback") == "ask_user" else "none")
