"""AI provider contracts (spec §6). No field ever carries a key back to the client."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from nfactory_core.routing import RoutingConfig

# not_configured -> configured / missing_key (saved, untested) -> connected (test passed)
# or invalid_credentials, quota_exceeded, rate_limited, unreachable, blocked, needs_model.
ConnectionStatus = str


Zone = Literal["local", "eu", "outside_eu", "unknown"]


class RegionOut(BaseModel):
    id: str
    label: str
    needs_workspace: bool  # the host embeds a workspace id (Qwen dedicated regions)
    zone: Zone
    country: str


class ResidencyOut(BaseModel):
    """Where the engine processes data (ADR-0016), for the saved or the default region."""

    zone: Zone
    country: str
    source: str
    note: str  # a condition the user must meet; "" when none


class LastError(BaseModel):
    kind: str
    message: str


class ProviderView(BaseModel):
    kind: str
    label: str
    family: Literal["api", "local", "coding_agent"]
    phase: int
    available: bool  # False: listed for honesty, built in a later phase
    status: ConnectionStatus
    needs_key: bool
    key_source: Literal["stored", "env"] | None  # where the key lives; never the key
    env_key: str | None
    env_key_available: bool
    regions: list[RegionOut]
    region: str | None
    residency: ResidencyOut
    workspace_id: str | None
    custom_url: bool
    base_url: str | None
    discovery: bool
    docs_url: str
    last_checked_at: datetime | None
    last_error: LastError | None


class ProvidersOut(BaseModel):
    providers: list[ProviderView]


class CustomOptions(BaseModel):
    """What the admin declares about a custom OpenAI-compatible endpoint."""

    model_config = ConfigDict(extra="forbid")
    json_mode: Literal["json_schema", "json_object", "none"] = "none"
    stream_usage: bool = False
    discovery: bool = True


class ProviderConfigIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Write-only: stored encrypted, then forgotten by this request.
    api_key: str | None = Field(default=None, min_length=8, max_length=500, repr=False)
    use_env_key: bool = False
    region: str | None = Field(default=None, max_length=40)
    workspace_id: str | None = Field(default=None, max_length=63)
    base_url: str | None = Field(default=None, max_length=300)
    options: CustomOptions | None = None


class ValidationOut(BaseModel):
    ok: bool
    status: ConnectionStatus
    message: str
    latency_ms: int | None = None
    models_found: int | None = None


class PricingIn(BaseModel):
    """USD per million tokens, as the provider's price page shows them."""

    model_config = ConfigDict(extra="forbid")
    input_per_mtok: float = Field(ge=0, le=10_000)
    output_per_mtok: float = Field(ge=0, le=10_000)
    cached_input_per_mtok: float | None = Field(default=None, ge=0, le=10_000)


class CatalogModelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pricing: PricingIn | None = None
    context_window: int | None = Field(default=None, ge=1, le=100_000_000)


class CatalogModelOut(BaseModel):
    model_id: str
    source: Literal["manual", "discovered"]
    pricing: PricingIn | None
    context_window: int | None


class CatalogOut(BaseModel):
    models: list[CatalogModelOut]


class RoleOut(BaseModel):
    id: str
    label: str


class RoutingOut(BaseModel):
    routing: RoutingConfig
    roles: list[RoleOut]


def pricing_out(capabilities: dict[str, Any]) -> PricingIn | None:
    raw = capabilities.get("pricing")
    return PricingIn.model_validate(raw) if isinstance(raw, dict) else None
