"""Embedders (task 3.3): the local fingerprint and the provider-backed embedder."""

import math

import pytest

from nfactory_core.knowledge.embedders import LOCAL_KEY, LocalHashEmbedder, ProviderEmbedder
from nfactory_core.providers import ProviderError, Usage
from nfactory_core.providers.types import Embeddings


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


async def test_local_fingerprint_is_deterministic_and_normalized() -> None:
    embedder = LocalHashEmbedder()

    first, again = (
        await embedder.embed(["Renouveler la licence"]),
        await embedder.embed(["Renouveler la licence"]),
    )

    assert first == again
    assert len(first[0]) == embedder.dim
    assert math.isclose(math.sqrt(sum(x * x for x in first[0])), 1.0, rel_tol=1e-6)
    assert embedder.key == LOCAL_KEY


async def test_local_fingerprint_brings_close_words_together() -> None:
    query, near, far = await LocalHashEmbedder().embed(
        ["renouvellement des licences", "Renouveler une licence", "Procédure de sauvegarde"]
    )

    assert _cosine(query, near) > _cosine(query, far) + 0.1


async def test_empty_text_gets_a_zero_free_vector() -> None:
    (vector,) = await LocalHashEmbedder().embed(["  "])

    assert len(vector) == LocalHashEmbedder().dim  # still a valid vector, never NaN
    assert all(not math.isnan(x) for x in vector)


class _Provider:
    def __init__(self, fail: bool = False) -> None:
        self.batches: list[list[str]] = []
        self.fail = fail

    async def embed(self, model: str, texts: list[str]) -> Embeddings:
        if self.fail:
            raise ProviderError("quota", provider="openai_api")
        self.batches.append(list(texts))
        return Embeddings([[float(len(t)), 1.0] for t in texts], Usage(len(texts), 0))


async def test_provider_embedder_batches_and_names_its_index() -> None:
    provider = _Provider()
    embedder = ProviderEmbedder(provider, "openai_api", "embed-x", batch_size=2)

    vectors = await embedder.embed(["a", "bb", "ccc"])

    assert vectors == [[1.0, 1.0], [2.0, 1.0], [3.0, 1.0]]
    assert provider.batches == [["a", "bb"], ["ccc"]]
    assert embedder.key == "openai_api:embed-x"


async def test_provider_failure_is_never_replaced_by_another_engine() -> None:
    embedder = ProviderEmbedder(_Provider(fail=True), "openai_api", "embed-x")

    with pytest.raises(ProviderError):
        await embedder.embed(["a"])
