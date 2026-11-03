"""Model providers (spec §6, ADR-0006), shared by the API and the worker.

Interface:
- `build_provider(kind, base_url=..., api_key=...)` returns a `ModelProvider`;
  `resolve_base_url` picks the URL from a region, workspace or typed URL.
- Every failure raises `ProviderError` (normalized `kind`, French `message`).
- `SPECS` describes each provider kind; `with_retries`, `cost_usd`, `pricing_from`.
"""

from nfactory_core.providers.errors import ErrorKind, ProviderError
from nfactory_core.providers.factory import (
    ProviderConfigError,
    build_provider,
    resolve_base_url,
    url_policy,
)
from nfactory_core.providers.pricing import Pricing, cost_usd, pricing_from
from nfactory_core.providers.protocols import CodingAgentRuntime, ModelProvider
from nfactory_core.providers.retry import with_retries
from nfactory_core.providers.specs import SPECS, ProviderSpec, Region, label
from nfactory_core.providers.ssrf import UnsafeUrlError, UrlPolicy, check_url
from nfactory_core.providers.types import (
    Completion,
    ConnectionReport,
    Embeddings,
    Message,
    ModelInfo,
    ProviderCapabilities,
    StreamChunk,
    ToolCall,
    ToolSpec,
    Usage,
)

__all__ = [
    "SPECS",
    "CodingAgentRuntime",
    "Completion",
    "ConnectionReport",
    "Embeddings",
    "ErrorKind",
    "Message",
    "ModelInfo",
    "ModelProvider",
    "Pricing",
    "ProviderCapabilities",
    "ProviderConfigError",
    "ProviderError",
    "ProviderSpec",
    "Region",
    "StreamChunk",
    "ToolCall",
    "ToolSpec",
    "UnsafeUrlError",
    "UrlPolicy",
    "Usage",
    "build_provider",
    "check_url",
    "cost_usd",
    "label",
    "pricing_from",
    "resolve_base_url",
    "url_policy",
    "with_retries",
]
