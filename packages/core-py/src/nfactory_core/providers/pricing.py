"""Cost of a call, from a price the admin typed into the model catalog.

No price is hard-coded: prices change and differ per account. Without a known price
the cost is None ("Non mesuré"), never 0.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from nfactory_core.providers.types import Usage


@dataclass(frozen=True)
class Pricing:
    input_per_mtok: float
    output_per_mtok: float
    cached_input_per_mtok: float | None = None


def pricing_from(capabilities: Mapping[str, Any]) -> Pricing | None:
    """Read `capabilities["pricing"]` of a catalog entry (USD per million tokens)."""
    raw = capabilities.get("pricing")
    if not isinstance(raw, Mapping):
        return None
    try:
        cached = raw.get("cached_input_per_mtok")
        return Pricing(
            input_per_mtok=float(raw["input_per_mtok"]),
            output_per_mtok=float(raw["output_per_mtok"]),
            cached_input_per_mtok=float(cached) if cached is not None else None,
        )
    except (KeyError, TypeError, ValueError):
        return None


def cost_usd(usage: Usage, pricing: Pricing | None) -> float | None:
    if pricing is None:
        return None
    cached = min(usage.cached_input_tokens, usage.input_tokens)
    cached_rate = (
        pricing.cached_input_per_mtok
        if pricing.cached_input_per_mtok is not None
        else pricing.input_per_mtok
    )
    total = (
        (usage.input_tokens - cached) * pricing.input_per_mtok
        + cached * cached_rate
        + usage.output_tokens * pricing.output_per_mtok
    )
    return total / 1_000_000
