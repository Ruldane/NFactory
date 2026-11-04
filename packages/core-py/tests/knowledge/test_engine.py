"""Which embedder a workspace uses (task 3.3): local by default, remote only when ready."""

import pytest

from nfactory_core.knowledge.embedders import LOCAL_KEY, LocalHashEmbedder
from nfactory_core.knowledge.engine import (
    EmbeddingChoice,
    EmbeddingUnavailableError,
    check_choice,
    embedding_choice,
    open_embedder,
)
from nfactory_core.routing import ConnectionFacts

CONNECTED = {
    "openai_api": ConnectionFacts("openai_api", "connected", local=False),
    "ollama_local": ConnectionFacts("ollama_local", "connected", local=True),
    "anthropic_api": ConnectionFacts("anthropic_api", "connected", local=False),
    "custom_openai_compatible": ConnectionFacts(
        "custom_openai_compatible", "invalid_credentials", local=False
    ),
}


def test_the_default_is_the_local_fingerprint() -> None:
    choice = embedding_choice({})

    assert choice.key == LOCAL_KEY
    assert (
        embedding_choice(
            {"knowledge": {"embedding": {"provider": "ollama_local", "model": "nomic"}}}
        ).key
        == "ollama_local:nomic"
    )


@pytest.mark.parametrize(
    ("choice", "local_only", "code"),
    [
        (EmbeddingChoice(provider="anthropic_api", model="x"), False, "embeddings_unsupported"),
        (EmbeddingChoice(provider="deepseek_api", model="x"), False, "embeddings_unsupported"),
        (
            EmbeddingChoice(provider="custom_openai_compatible", model="x"),
            False,
            "provider_not_ready",
        ),
        (EmbeddingChoice(provider="openai_api", model="embed-x"), True, "local_only_violation"),
        (EmbeddingChoice(provider="local", model="autre"), False, "embeddings_unsupported"),
    ],
)
def test_unusable_choices_are_refused(choice: EmbeddingChoice, local_only: bool, code: str) -> None:
    with pytest.raises(EmbeddingUnavailableError) as caught:
        check_choice(choice, CONNECTED, local_only=local_only)

    assert caught.value.code == code


def test_ready_choices_pass() -> None:
    check_choice(
        EmbeddingChoice(provider="openai_api", model="embed-x"), CONNECTED, local_only=False
    )
    check_choice(
        EmbeddingChoice(provider="ollama_local", model="nomic"), CONNECTED, local_only=True
    )
    check_choice(EmbeddingChoice(), {}, local_only=True)


def test_eu_only_refuses_a_remote_embedder_outside_the_eu() -> None:
    with pytest.raises(EmbeddingUnavailableError) as caught:
        check_choice(
            EmbeddingChoice(provider="openai_api", model="embed-x"),
            CONNECTED,
            local_only=False,
            eu_only=True,
        )

    assert caught.value.code == "eu_only_violation"
    check_choice(
        EmbeddingChoice(provider="ollama_local", model="nomic"),
        CONNECTED,
        local_only=False,
        eu_only=True,
    )


def test_model_ids_are_validated() -> None:
    with pytest.raises(ValueError):
        EmbeddingChoice(provider="openai_api", model="bad model; drop")


async def test_the_local_choice_opens_without_database_or_network() -> None:
    embedder = await open_embedder(None, "wks", EmbeddingChoice(), store=None)  # type: ignore[arg-type]

    assert isinstance(embedder, LocalHashEmbedder)
