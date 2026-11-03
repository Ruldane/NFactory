"""AI providers ("Moteurs IA"): connections, connection tests and the model catalog."""

from fastapi import APIRouter

from app.context import CanConfigure, Context, Providers, Session
from app.schemas.providers import (
    CatalogModelIn,
    CatalogModelOut,
    CatalogOut,
    ProviderConfigIn,
    ProvidersOut,
    ProviderView,
    ValidationOut,
)
from app.services import audit, model_catalog, providers

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("")
async def list_providers(session: Session, ctx: Context, deps: Providers) -> ProvidersOut:
    return await providers.list_providers(session, ctx, deps)


@router.put("/{kind}/configuration")
async def configure(
    kind: str, data: ProviderConfigIn, session: Session, ctx: CanConfigure, deps: Providers
) -> ProviderView:
    """Save region, URL and key. The key is encrypted and never returned."""
    view = await providers.configure(session, ctx, deps, kind, data)
    # Only the kind: the key itself never leaves the secret store.
    audit.record(session, ctx, "provider.configure", kind, details={"kind": kind})
    await session.commit()
    return view


@router.delete("/{kind}/configuration")
async def remove(kind: str, session: Session, ctx: CanConfigure, deps: Providers) -> ProviderView:
    view = await providers.remove(session, ctx, deps, kind)
    audit.record(session, ctx, "provider.remove", kind, details={"kind": kind})
    await session.commit()
    return view


@router.post("/{kind}/validate")
async def validate(
    kind: str, session: Session, ctx: CanConfigure, deps: Providers
) -> ValidationOut:
    """Consented connection test: the only way a provider becomes "connected"."""
    return await providers.validate(session, ctx, deps, kind)


@router.get("/{kind}/models")
async def list_models(kind: str, session: Session) -> CatalogOut:
    return await model_catalog.list_models(session, kind)


@router.put("/{kind}/models/{model_id:path}")
async def put_model(
    kind: str, model_id: str, data: CatalogModelIn, session: Session, ctx: CanConfigure
) -> CatalogModelOut:
    model = await model_catalog.put_model(session, kind, model_id, data)
    audit.record(session, ctx, "provider.model_set", f"{kind}/{model_id}")
    await session.commit()
    return model


@router.delete("/{kind}/models/{model_id:path}")
async def delete_model(
    kind: str, model_id: str, session: Session, ctx: CanConfigure
) -> dict[str, str]:
    await model_catalog.delete_model(session, kind, model_id)
    audit.record(session, ctx, "provider.model_remove", f"{kind}/{model_id}")
    await session.commit()
    return {"removed": model_id}
