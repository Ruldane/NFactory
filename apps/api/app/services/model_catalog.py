"""Model catalog (task 2.7): models found by discovery or added by the admin.

No model name is hardcoded anywhere: this table is the only list. Prices are what the
admin typed; a model without a price has an unmeasured cost, never a guessed one.
The catalog is shared by the instance (one entry per provider kind and model).
"""

import re
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError, not_found
from app.schemas.providers import CatalogModelIn, CatalogModelOut, CatalogOut, pricing_out
from nfactory_core.models import ModelCatalogEntry
from nfactory_core.providers import SPECS, ModelInfo

# Provider model ids: letters, digits and . _ - : / @ (Ollama tags, Qwen paths).
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,199}$")


async def list_models(session: AsyncSession, kind: str) -> CatalogOut:
    _known(kind)
    rows = await session.scalars(
        select(ModelCatalogEntry)
        .where(ModelCatalogEntry.provider_kind == kind)
        .order_by(ModelCatalogEntry.model_id)
    )
    return CatalogOut(models=[_out(row) for row in rows])


async def first_model(session: AsyncSession, kind: str) -> str | None:
    return await session.scalar(
        select(ModelCatalogEntry.model_id)
        .where(ModelCatalogEntry.provider_kind == kind)
        .order_by(ModelCatalogEntry.model_id)
        .limit(1)
    )


async def put_model(
    session: AsyncSession, kind: str, model_id: str, data: CatalogModelIn
) -> CatalogModelOut:
    _known(kind)
    if not _MODEL_ID.match(model_id):
        raise AppError(422, "invalid_model_id", "Identifiant de modèle invalide.")
    row = await session.get(ModelCatalogEntry, (kind, model_id))
    if row is None:
        row = ModelCatalogEntry(provider_kind=kind, model_id=model_id, source="manual")
        session.add(row)
    capabilities = dict(row.capabilities or {})
    capabilities["pricing"] = data.pricing.model_dump() if data.pricing else None
    if data.context_window is not None:
        capabilities["context_window"] = data.context_window
    row.capabilities = capabilities
    row.reviewed_at = datetime.now(UTC)
    await session.commit()
    return _out(row)


async def delete_model(session: AsyncSession, kind: str, model_id: str) -> None:
    _known(kind)
    row = await session.get(ModelCatalogEntry, (kind, model_id))
    if row is None:
        raise not_found("Modèle")
    await session.delete(row)
    await session.commit()


async def record_discovered(session: AsyncSession, kind: str, models: Sequence[ModelInfo]) -> None:
    """Upsert what the provider listed; the admin's price and source are kept."""
    for info in models:
        if not _MODEL_ID.match(info.id):
            continue
        row = await session.get(ModelCatalogEntry, (kind, info.id))
        if row is None:
            row = ModelCatalogEntry(provider_kind=kind, model_id=info.id, source="discovered")
            session.add(row)
        capabilities = {**(row.capabilities or {}), **info.capabilities}
        capabilities["pricing"] = (row.capabilities or {}).get("pricing")
        if info.context_window is not None:
            capabilities["context_window"] = info.context_window
        if info.display_name:
            capabilities["display_name"] = info.display_name
        row.capabilities = capabilities


async def price_of(session: AsyncSession, kind: str, model_id: str) -> dict[str, float] | None:
    row = await session.get(ModelCatalogEntry, (kind, model_id))
    if row is None:
        return None
    pricing = pricing_out(row.capabilities or {})
    return pricing.model_dump() if pricing else None


def _known(kind: str) -> None:
    spec = SPECS.get(kind)
    if spec is None or spec.protocol == "coding_agent":
        raise not_found("Fournisseur")


def _out(row: ModelCatalogEntry) -> CatalogModelOut:
    capabilities = row.capabilities or {}
    window = capabilities.get("context_window")
    return CatalogModelOut(
        model_id=row.model_id,
        source="discovered" if row.source == "discovered" else "manual",
        pricing=pricing_out(capabilities),
        context_window=window if isinstance(window, int) else None,
    )
