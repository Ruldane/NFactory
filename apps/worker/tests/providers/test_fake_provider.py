"""Demo-mode provider specifics: deterministic, scriptable, and clearly labelled as fake."""

from nfactory_worker.providers.fake import FAKE_MODEL_ID, FakeProvider

MESSAGES = [{"role": "user", "content": "Bonjour"}]


async def test_same_input_gives_same_output() -> None:
    a = await FakeProvider().complete(FAKE_MODEL_ID, MESSAGES)
    b = await FakeProvider().complete(FAKE_MODEL_ID, MESSAGES)
    assert a.content == b.content


async def test_different_input_gives_different_output() -> None:
    a = await FakeProvider().complete(FAKE_MODEL_ID, MESSAGES)
    b = await FakeProvider().complete(FAKE_MODEL_ID, [{"role": "user", "content": "Salut"}])
    assert a.content != b.content


async def test_scripted_reply_is_returned_when_the_prompt_matches() -> None:
    # Agents in demo mode get structured JSON from scripts, not free text.
    provider = FakeProvider(scripts={"plan": '{"tasks": []}'})

    result = await provider.complete(FAKE_MODEL_ID, [{"role": "user", "content": "Make a plan"}])

    assert result.content == '{"tasks": []}'


async def test_fake_provider_never_claims_to_be_real() -> None:
    report = await FakeProvider().check_connection()
    assert report.ok and "démo" in report.detail
    assert (await FakeProvider().list_models())[0].capabilities["demo"] is True


async def test_responder_builds_replies_from_the_whole_conversation() -> None:
    # Demo agents need structured answers computed from the prompt, not fixed strings.
    def responder(messages: list[dict[str, str]]) -> str | None:
        return "[sys]" if messages[0]["content"] == "S" else None

    provider = FakeProvider(responder=responder)
    convo = [{"role": "system", "content": "S"}, {"role": "user", "content": "x"}]

    assert (await provider.complete(FAKE_MODEL_ID, convo)).content == "[sys]"
    # Falls back to the hash reply when the responder declines.
    other = await provider.complete(FAKE_MODEL_ID, MESSAGES)
    assert other.content.startswith("[démo]")
