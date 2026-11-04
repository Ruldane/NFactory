"""The embedder a workspace uses (ADR-0007): stored in `data_policy["knowledge"]`.

The local fingerprint is the default, so nothing leaves the machine without a choice.
A remote embedder must be connected (tested), must offer a verified embeddings API and
is refused in local-only mode. A failing embedder is reported, never replaced.
"""

import re
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from nfactory_core.connections import ProviderUnusableError, open_provider, workspace_connections
from nfactory_core.knowledge.embedders import (
    LOCAL_MODEL,
    LOCAL_PROVIDER,
    Embedder,
    EmbeddingProvider,
    LocalHashEmbedder,
    ProviderEmbedder,
)
from nfactory_core.providers import SPECS
from nfactory_core.providers.ssrf import Resolver, system_resolver
from nfactory_core.routing import ConnectionFacts, policy_violation
from nfactory_core.secrets import SecretStore

POLICY_KEY = "knowledge"
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]{0,199}$")


class EmbeddingChoice(BaseModel):
    provider: str = LOCAL_PROVIDER
    model: str = LOCAL_MODEL

    @field_validator("model")
    @classmethod
    def _valid_model(cls, value: str) -> str:
        if not _MODEL_ID.match(value):
            raise ValueError("identifiant de modèle invalide")
        return value

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.model}"

    @property
    def local(self) -> bool:
        return self.provider == LOCAL_PROVIDER or (
            self.provider in SPECS and SPECS[self.provider].local
        )


class EmbeddingUnavailableError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def embedding_choice(data_policy: Mapping[str, Any] | None) -> EmbeddingChoice:
    saved = ((data_policy or {}).get(POLICY_KEY) or {}).get("embedding")
    return EmbeddingChoice.model_validate(saved) if saved else EmbeddingChoice()


def check_choice(
    choice: EmbeddingChoice,
    connections: Mapping[str, ConnectionFacts],
    *,
    local_only: bool,
    eu_only: bool = False,
) -> None:
    if choice.provider == LOCAL_PROVIDER:
        if choice.model != LOCAL_MODEL:
            raise EmbeddingUnavailableError(
                "embeddings_unsupported", f"Empreinte locale inconnue : {choice.model}."
            )
        return
    spec = SPECS.get(choice.provider)
    if spec is None or not spec.embeddings:
        raise EmbeddingUnavailableError(
            "embeddings_unsupported",
            "Ce fournisseur ne propose pas d'embeddings vérifiés dans sa documentation.",
        )
    facts = connections.get(choice.provider)
    if facts is None or facts.status != "connected":
        raise EmbeddingUnavailableError(
            "provider_not_ready",
            f"{spec.label} n'est pas connecté : testez sa connexion dans Moteurs IA.",
        )
    violation = policy_violation(facts, local_only=local_only, eu_only=eu_only)
    if violation is not None:
        raise EmbeddingUnavailableError(violation.code, violation.message)


async def open_embedder(
    session: AsyncSession,
    workspace_id: str,
    choice: EmbeddingChoice,
    store: SecretStore,
    *,
    resolver: Resolver = system_resolver,
    allowed_private_hosts: frozenset[str] = frozenset(),
) -> Embedder:
    if choice.provider == LOCAL_PROVIDER:
        return LocalHashEmbedder()
    row = (await workspace_connections(session, workspace_id)).get(choice.provider)
    if row is None or row.status != "connected":
        raise EmbeddingUnavailableError(
            "provider_not_ready", f"{SPECS[choice.provider].label} n'est plus connecté."
        )
    try:
        provider = await open_provider(
            session, row, store, resolver=resolver, allowed_private_hosts=allowed_private_hosts
        )
    except ProviderUnusableError as exc:
        raise EmbeddingUnavailableError("provider_not_ready", str(exc)) from exc
    if not hasattr(provider, "embed"):
        raise EmbeddingUnavailableError("embeddings_unsupported", "Pas d'embeddings ici.")
    embedding_provider: EmbeddingProvider = provider  # type: ignore[assignment]
    return ProviderEmbedder(embedding_provider, choice.provider, choice.model)
