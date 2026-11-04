"""Provider connections: configure, test, remove. Keys go to the secret store only.

A connection becomes "connected" only after a successful test the user asked for
(ADR-0006). Any change to its configuration sends it back to "configured".
"""

import os
import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError, not_found
from app.schemas.providers import (
    LastError,
    ProviderConfigIn,
    ProvidersOut,
    ProviderView,
    RegionOut,
    ResidencyOut,
    ValidationOut,
)
from app.services import model_catalog
from app.services.identity import RequestContext
from nfactory_core.connections import (
    STATUS_BY_ERROR,
    ProviderUnusableError,
    open_provider,
    workspace_connections,
)
from nfactory_core.models import ProviderConnection
from nfactory_core.providers import (
    SPECS,
    ProviderConfigError,
    ProviderError,
    ProviderSpec,
    UnsafeUrlError,
    check_url,
    resolve_base_url,
    url_policy,
)
from nfactory_core.providers.residency import residency
from nfactory_core.providers.ssrf import Resolver
from nfactory_core.secrets import SecretKeyMissingError, SecretStore, SecretUnreadableError


@dataclass(frozen=True)
class ProviderDeps:
    store: SecretStore
    resolver: Resolver
    allowed_private_hosts: frozenset[str]
    ollama_base_url: str
    env: Mapping[str, str] = field(default_factory=lambda: os.environ)


async def list_providers(
    session: AsyncSession, ctx: RequestContext, deps: ProviderDeps
) -> ProvidersOut:
    rows = await workspace_connections(session, ctx.default_workspace_id)
    return ProvidersOut(
        providers=[_view(spec, rows.get(kind), deps) for kind, spec in SPECS.items()]
    )


async def configure(
    session: AsyncSession,
    ctx: RequestContext,
    deps: ProviderDeps,
    kind: str,
    data: ProviderConfigIn,
) -> ProviderView:
    spec = _chat_spec(kind)
    config = _validated_config(spec, data, deps)
    rows = await workspace_connections(session, ctx.default_workspace_id)
    row = rows.get(kind)
    if row is None:
        row = ProviderConnection(
            workspace_id=ctx.default_workspace_id, kind=kind, display_name=spec.label
        )
        session.add(row)
    ref = await _key_ref(session, ctx, deps, spec, data, row.secret_ref)
    row.secret_ref = ref
    row.config_non_secret = config
    row.status = "configured" if (ref or not _key_required(spec)) else "missing_key"
    row.last_error = None
    row.last_checked_at = None
    await session.commit()
    return _view(spec, row, deps)


async def remove(
    session: AsyncSession, ctx: RequestContext, deps: ProviderDeps, kind: str
) -> ProviderView:
    spec = _chat_spec(kind)
    row = (await workspace_connections(session, ctx.default_workspace_id)).get(kind)
    if row is not None:
        await deps.store.delete(session, row.secret_ref)
        await session.delete(row)
        await session.commit()
    return _view(spec, None, deps)


async def validate(
    session: AsyncSession, ctx: RequestContext, deps: ProviderDeps, kind: str
) -> ValidationOut:
    """Run the consented connection test and store its honest outcome."""
    spec = _chat_spec(kind)
    row = (await workspace_connections(session, ctx.default_workspace_id)).get(kind)
    if row is None:
        raise AppError(
            409,
            "provider_not_configured",
            f"{spec.label} n'est pas configuré : enregistrez d'abord sa configuration.",
        )
    started = time.monotonic()
    try:
        result = await _run_test(session, deps, spec, row)
    except ProviderError as exc:
        status = STATUS_BY_ERROR.get(exc.kind, "error")
        result = _failed(row, status, exc.kind, exc.message)
    except (ProviderUnusableError, SecretUnreadableError, SecretKeyMissingError) as exc:
        result = _failed(row, "missing_key", "config", str(exc))
    else:
        row.status, row.last_error = "connected", None
    row.last_checked_at = datetime.now(UTC)
    await session.commit()
    if result.ok:
        result.latency_ms = int((time.monotonic() - started) * 1000)
    return result


async def _run_test(
    session: AsyncSession, deps: ProviderDeps, spec: ProviderSpec, row: ProviderConnection
) -> ValidationOut:
    provider = await open_provider(
        session,
        row,
        deps.store,
        resolver=deps.resolver,
        allowed_private_hosts=deps.allowed_private_hosts,
    )
    if _discovers(spec, row.config_non_secret or {}):
        models = await provider.list_models()
        await model_catalog.record_discovered(session, spec.kind, models)
        return ValidationOut(
            ok=True,
            status="connected",
            message=f"{spec.label} : connexion réussie, {len(models)} modèle(s) trouvé(s).",
            models_found=len(models),
        )
    probe = await model_catalog.first_model(session, spec.kind)
    if probe is None:
        return ValidationOut(
            ok=False,
            status="needs_model",
            message=f"{spec.label} ne publie pas sa liste de modèles : ajoutez un modèle au "
            "catalogue, puis relancez le test.",
        )
    await provider.check_connection(probe)
    return ValidationOut(
        ok=True,
        status="connected",
        message=f"{spec.label} : connexion réussie avec le modèle {probe}.",
    )


def _failed(row: ProviderConnection, status: str, kind: str, message: str) -> ValidationOut:
    row.status = status
    row.last_error = {"kind": kind, "message": message}
    return ValidationOut(ok=False, status=status, message=message)


# --- configuration ----------------------------------------------------------------------


def _chat_spec(kind: str) -> ProviderSpec:
    spec = SPECS.get(kind)
    if spec is None:
        raise not_found("Fournisseur")
    if spec.protocol == "coding_agent":
        raise AppError(
            409,
            "provider_unavailable",
            f"{spec.label} est un agent de code local : il arrive en phase {spec.phase}.",
        )
    return spec


def _key_required(spec: ProviderSpec) -> bool:
    # A custom endpoint may run without a key (a LAN vLLM, for instance).
    return spec.needs_key and spec.kind != "custom_openai_compatible"


def _discovers(spec: ProviderSpec, config: Mapping[str, Any]) -> bool:
    if spec.kind == "custom_openai_compatible":
        return bool((config.get("options") or {}).get("discovery", True))
    return spec.discovery


def _validated_config(
    spec: ProviderSpec, data: ProviderConfigIn, deps: ProviderDeps
) -> dict[str, Any]:
    base_url = data.base_url
    if spec.kind == "ollama_local" and not base_url:
        base_url = deps.ollama_base_url
    try:
        resolved = resolve_base_url(
            spec.kind, region=data.region, workspace_id=data.workspace_id, base_url=base_url
        )
    except ProviderConfigError as exc:
        raise AppError(422, "invalid_provider_config", str(exc)) from None
    policy = url_policy(spec.kind, deps.allowed_private_hosts)
    if policy is not None:
        try:
            check_url(resolved, policy=policy, resolver=deps.resolver)
        except UnsafeUrlError as exc:
            raise AppError(422, "unsafe_base_url", str(exc)) from None
    config: dict[str, Any] = {}
    if spec.regions:
        config["region"] = (spec.region(data.region) or spec.regions[0]).id
    if (
        data.workspace_id
        and "{workspace_id}" in (spec.region(data.region) or spec.regions[0]).base_url
    ):
        config["workspace_id"] = data.workspace_id
    if spec.custom_url:
        config["base_url"] = resolved
    if data.options is not None and spec.kind == "custom_openai_compatible":
        config["options"] = data.options.model_dump()
    return config


async def _key_ref(
    session: AsyncSession,
    ctx: RequestContext,
    deps: ProviderDeps,
    spec: ProviderSpec,
    data: ProviderConfigIn,
    current: str | None,
) -> str | None:
    if data.api_key:
        try:
            ref = await deps.store.put(session, ctx.default_workspace_id, data.api_key.strip())
        except SecretKeyMissingError as exc:
            raise AppError(503, "secret_key_missing", str(exc)) from None
        await deps.store.delete(session, current)
        return ref
    if data.use_env_key:
        if not spec.env_key or not deps.env.get(spec.env_key):
            raise AppError(
                422,
                "env_key_missing",
                f"La variable {spec.env_key or '(aucune)'} n'est pas définie dans l'environnement "
                "du serveur.",
            )
        await deps.store.delete(session, current)
        return f"env:{spec.env_key}"
    return current


def _view(spec: ProviderSpec, row: ProviderConnection | None, deps: ProviderDeps) -> ProviderView:
    config = (row.config_non_secret if row else None) or {}
    ref = row.secret_ref if row else None
    base_url: str | None = None
    if row is not None:
        try:
            base_url = resolve_base_url(
                spec.kind,
                region=config.get("region"),
                workspace_id=config.get("workspace_id"),
                base_url=config.get("base_url"),
            )
        except ProviderConfigError:
            base_url = None
    elif spec.kind == "ollama_local":
        base_url = deps.ollama_base_url  # a suggestion until the user saves one
    return ProviderView(
        kind=spec.kind,
        label=spec.label,
        family=spec.family,
        phase=spec.phase,
        available=spec.protocol != "coding_agent",
        status=row.status if row else "not_configured",
        needs_key=_key_required(spec),
        key_source="env" if (ref or "").startswith("env:") else ("stored" if ref else None),
        env_key=spec.env_key,
        env_key_available=bool(spec.env_key and deps.env.get(spec.env_key)),
        regions=[
            RegionOut(
                id=r.id,
                label=r.label,
                needs_workspace="{workspace_id}" in r.base_url,
                zone=residency(spec.kind, r.id).zone,
                country=residency(spec.kind, r.id).country,
            )
            for r in spec.regions
        ],
        region=config.get("region"),
        residency=ResidencyOut(**asdict(residency(spec.kind, config.get("region")))),
        workspace_id=config.get("workspace_id"),
        custom_url=spec.custom_url,
        base_url=base_url,
        discovery=_discovers(spec, config),
        docs_url=spec.docs_url,
        last_checked_at=row.last_checked_at if row else None,
        last_error=LastError.model_validate(row.last_error) if row and row.last_error else None,
    )
