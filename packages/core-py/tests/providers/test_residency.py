"""Where each engine processes data (ADR-0016): every known endpoint is stated, with a source."""

import pytest

from nfactory_core.connections import connection_facts
from nfactory_core.models import ProviderConnection
from nfactory_core.providers.residency import residency
from nfactory_core.providers.specs import SPECS


@pytest.mark.parametrize(
    ("kind", "region"),
    [(k, r.id if r else None) for k, s in SPECS.items() for r in (s.regions or (None,))],
)
def test_every_known_endpoint_is_stated_with_its_source(kind: str, region: str | None) -> None:
    found = residency(kind, region)

    if kind == "custom_openai_compatible":
        assert found.zone == "unknown"  # the user's own URL: NFactory cannot know
    elif kind == "ollama_local":
        assert found.zone == "local"
    else:
        assert found.zone != "unknown" or found.source, (kind, region)
        assert found.source.startswith("https://"), (kind, region)


def test_regions_say_their_country() -> None:
    assert residency("qwen_api", "eu-central-1").zone == "eu"
    assert residency("qwen_api", "eu-central-1").country == "Allemagne"
    assert residency("qwen_api", "us-east-1").zone == "outside_eu"
    assert residency("zai_glm_api", "cn").country == "Chine"


def test_no_region_means_the_first_one_and_an_unknown_endpoint_is_unknown() -> None:
    assert residency("qwen_api") == residency("qwen_api", "cn-beijing")
    assert residency("qwen_api", "mars-1").zone == "unknown"
    assert residency("nobody").zone == "unknown"


def test_connection_facts_carry_the_zone_of_the_saved_region() -> None:
    rows = {
        "qwen_api": ProviderConnection(
            kind="qwen_api", status="connected", config_non_secret={"region": "eu-central-1"}
        ),
        "ollama_local": ProviderConnection(
            kind="ollama_local", status="connected", config_non_secret={}
        ),
    }

    facts = connection_facts(rows)

    assert (facts["qwen_api"].zone, facts["qwen_api"].country) == ("eu", "Allemagne")
    assert facts["ollama_local"].local and facts["ollama_local"].zone == "local"
