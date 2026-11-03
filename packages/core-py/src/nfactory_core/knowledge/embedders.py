"""Embedders turn chunk text into vectors (ADR-0007).

Each embedder has a `key` naming its index: vectors of different keys are never
compared. The local fingerprint needs no model and no network; a provider embedder
calls a connected provider and lets its errors through (no silent fallback).
"""

import hashlib
import math
import re
import unicodedata
from collections.abc import Sequence
from typing import Protocol

from nfactory_core.providers.types import Embeddings

LOCAL_PROVIDER = "local"
LOCAL_MODEL = "empreinte-v1"
LOCAL_KEY = f"{LOCAL_PROVIDER}:{LOCAL_MODEL}"

_WORD = re.compile(r"\w+")


class Embedder(Protocol):
    key: str

    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class EmbeddingProvider(Protocol):
    async def embed(self, model: str, texts: Sequence[str]) -> Embeddings: ...


class LocalHashEmbedder:
    """Lexical fingerprint: hashed words and character trigrams, L2-normalized.

    Honest about its limits: close spellings match ("licence" / "licences"),
    synonyms do not. A real embedding model is needed for semantic search.
    """

    key = LOCAL_KEY

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for feature, weight in _features(text):
            digest = int.from_bytes(hashlib.blake2b(feature.encode(), digest_size=8).digest())
            vector[digest % self.dim] += weight if (digest >> 40) & 1 else -weight
        norm = math.sqrt(sum(x * x for x in vector))
        if norm == 0:  # no word at all: a fixed unit vector keeps cosine defined
            return [1.0] + [0.0] * (self.dim - 1)
        return [x / norm for x in vector]


def _features(text: str) -> list[tuple[str, float]]:
    plain = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    features: list[tuple[str, float]] = []
    for word in _WORD.findall(plain):
        features.append((f"w:{word}", 1.0))
        padded = f"#{word}#"
        features.extend((f"t:{padded[i : i + 3]}", 0.5) for i in range(len(padded) - 2))
    return features


class ProviderEmbedder:
    """Vectors from a connected provider, sent in batches."""

    def __init__(
        self, provider: EmbeddingProvider, kind: str, model: str, batch_size: int = 64
    ) -> None:
        self._provider = provider
        self._model = model
        self._batch = batch_size
        self.key = f"{kind}:{model}"

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch):
            result = await self._provider.embed(
                self._model, list(texts[start : start + self._batch])
            )
            vectors.extend(result.vectors)
        return vectors
