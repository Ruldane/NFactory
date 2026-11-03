"""Live provider checks (task 2.3): opt-in only, never part of the gate.

Run with NFACTORY_LIVE_TESTS=1 and the provider's key in the environment (e.g.
OPENAI_API_KEY). Each test lists the models of one real provider; a provider without
a key is skipped. Keys are read from the environment and never printed.
"""

import os

import pytest

from nfactory_core.providers import SPECS, build_provider, resolve_base_url

pytestmark = pytest.mark.live

LIVE = os.environ.get("NFACTORY_LIVE_TESTS") == "1"
KINDS = [k for k, s in SPECS.items() if s.protocol != "coding_agent" and s.discovery and s.env_key]


@pytest.mark.skipif(
    not LIVE, reason="tests live désactivés (NFACTORY_LIVE_TESTS=1 pour les lancer)"
)
@pytest.mark.parametrize("kind", KINDS)
async def test_real_provider_lists_its_models(kind: str) -> None:
    spec = SPECS[kind]
    key = os.environ.get(spec.env_key or "")
    if not key or spec.custom_url:
        pytest.skip(f"pas de clé {spec.env_key} dans l'environnement")
    provider = build_provider(kind, base_url=resolve_base_url(kind), api_key=key)

    models = await provider.list_models()

    assert models, f"{spec.label} n'a renvoyé aucun modèle"
