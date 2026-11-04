"""Open a provider from a stored connection; shared by the API (test, discovery) and
the worker (runs). The key is read from the secret store at the last moment and never
leaves this function.

Interface: `open_provider`, `connection_facts`, `STATUS_BY_ERROR`, `ProviderUnusableError`.
"""

from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nfactory_core.models import ProviderConnection
from nfactory_core.providers import (
    SPECS,
    ModelProvider,
    ProviderConfigError,
    build_provider,
    resolve_base_url,
)
from nfactory_core.providers.residency import residency
from nfactory_core.providers.ssrf import Resolver, system_resolver
from nfactory_core.routing import ConnectionFacts
from nfactory_core.secrets import SecretStore

# Connection status after a failed test, by error kind. "connected" only ever comes
# from a successful test.
STATUS_BY_ERROR: dict[str, str] = {
    "auth": "invalid_credentials",
    "quota": "quota_exceeded",
    "rate_limit": "rate_limited",
    "timeout": "unreachable",
    "unavailable": "unreachable",
    "blocked": "blocked",
    "unsupported": "needs_model",
}


class ProviderUnusableError(Exception):
    """The connection cannot be opened (missing key, bad config); message in French."""


async def open_provider(
    session: AsyncSession,
    connection: ProviderConnection,
    store: SecretStore,
    *,
    resolver: Resolver = system_resolver,
    allowed_private_hosts: frozenset[str] = frozenset(),
) -> ModelProvider:
    config = connection.config_non_secret or {}
    spec = SPECS[connection.kind]
    key = await store.get(session, connection.secret_ref)
    if spec.needs_key and connection.kind != "custom_openai_compatible" and not key:
        raise ProviderUnusableError(
            f"Aucune clé utilisable pour {spec.label} : enregistrez-la dans Moteurs IA."
        )
    try:
        base_url = resolve_base_url(
            connection.kind,
            region=config.get("region"),
            workspace_id=config.get("workspace_id"),
            base_url=config.get("base_url"),
        )
        return build_provider(
            connection.kind,
            base_url=base_url,
            api_key=key,
            options=config.get("options") or {},
            resolver=resolver,
            allowed_private_hosts=allowed_private_hosts,
        )
    except ProviderConfigError as exc:
        raise ProviderUnusableError(str(exc)) from exc


async def workspace_connections(
    session: AsyncSession, workspace_id: str
) -> dict[str, ProviderConnection]:
    rows = await session.scalars(
        select(ProviderConnection).where(ProviderConnection.workspace_id == workspace_id)
    )
    return {row.kind: row for row in rows}


def connection_facts(rows: Mapping[str, ProviderConnection]) -> dict[str, ConnectionFacts]:
    facts: dict[str, ConnectionFacts] = {}
    for kind, row in rows.items():
        if kind not in SPECS:
            continue
        where = residency(kind, (row.config_non_secret or {}).get("region"))
        facts[kind] = ConnectionFacts(
            kind=kind,
            status=row.status,
            local=SPECS[kind].local,
            zone=where.zone,
            country=where.country,
        )
    return facts
