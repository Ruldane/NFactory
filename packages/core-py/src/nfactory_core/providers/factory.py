"""Build an adapter from a provider kind, its base URL and its key.

Interface: `build_provider`, `resolve_base_url`, `ProviderConfigError`.
"""

import re
from collections.abc import Mapping
from functools import partial
from typing import Any

from nfactory_core.providers.anthropic import AnthropicProvider, anthropic_headers
from nfactory_core.providers.http import ProviderHttp
from nfactory_core.providers.ollama import OllamaProvider
from nfactory_core.providers.openai_compat import (
    PROFILES,
    OpenAICompatibleProvider,
    custom_profile,
)
from nfactory_core.providers.protocols import ModelProvider
from nfactory_core.providers.specs import SPECS
from nfactory_core.providers.ssrf import Resolver, UrlPolicy, check_url, system_resolver

_WORKSPACE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")


class ProviderConfigError(ValueError):
    """A configuration NFactory refuses; the message is French and user-facing."""


def resolve_base_url(
    kind: str,
    *,
    region: str | None = None,
    workspace_id: str | None = None,
    base_url: str | None = None,
) -> str:
    spec = SPECS.get(kind)
    if spec is None or spec.protocol == "coding_agent":
        raise ProviderConfigError(f"Fournisseur inconnu ou non pris en charge ici : {kind}.")
    if spec.custom_url:
        if not base_url:
            raise ProviderConfigError("Indiquez l'URL de base du fournisseur.")
        return base_url.rstrip("/")
    chosen = spec.region(region)
    if chosen is None:
        raise ProviderConfigError(f"Région inconnue pour {spec.label} : {region}.")
    if "{workspace_id}" in chosen.base_url:
        if not workspace_id or not _WORKSPACE_ID.match(workspace_id):
            raise ProviderConfigError(
                "Indiquez l'identifiant d'espace de travail Model Studio (lettres minuscules, "
                "chiffres et tirets), visible dans la console Alibaba Cloud."
            )
        return chosen.base_url.replace("{workspace_id}", workspace_id)
    return chosen.base_url


def url_policy(kind: str, allowed_private_hosts: frozenset[str]) -> UrlPolicy | None:
    """The SSRF policy for URLs the user types; None for fixed official hosts."""
    if kind == "ollama_local":
        return UrlPolicy(allow_http=True, allow_private=True)
    if kind == "custom_openai_compatible":
        return UrlPolicy(allowed_private_hosts=allowed_private_hosts)
    return None


def build_provider(
    kind: str,
    *,
    base_url: str,
    api_key: str | None,
    options: Mapping[str, Any] | None = None,
    resolver: Resolver = system_resolver,
    allowed_private_hosts: frozenset[str] = frozenset(),
    timeout_s: float | None = None,
) -> ModelProvider:
    spec = SPECS.get(kind)
    if spec is None or spec.protocol == "coding_agent":
        raise ProviderConfigError(f"Fournisseur inconnu ou non pris en charge ici : {kind}.")
    if spec.needs_key and kind != "custom_openai_compatible" and not api_key:
        raise ProviderConfigError(f"Aucune clé enregistrée pour {spec.label}.")
    policy = url_policy(kind, allowed_private_hosts)
    guard = partial(check_url, policy=policy, resolver=resolver) if policy else None
    extra: dict[str, Any] = {"guard": guard}
    if timeout_s is not None:
        extra["timeout_s"] = timeout_s

    if spec.protocol == "anthropic":
        headers = anthropic_headers(api_key or "")
        return AnthropicProvider(ProviderHttp(kind, base_url, headers, **extra))
    bearer = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    http = ProviderHttp(kind, base_url, bearer, **extra)
    if spec.protocol == "ollama":
        return OllamaProvider(http)
    profile = (
        custom_profile(options or {}) if kind == "custom_openai_compatible" else PROFILES[kind]
    )
    return OpenAICompatibleProvider(kind, http, profile)
