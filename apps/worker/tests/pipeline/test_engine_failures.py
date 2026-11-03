"""Provider failures inside a run (task 2.8): retried when temporary, never silently
replaced by another engine, and paused for the user when the routing asks for it."""

from typing import Any

import pytest

from nfactory_core.providers import Completion, Pricing, ProviderError
from nfactory_worker.agents import LLM, Engines
from nfactory_worker.agents.demo import respond
from nfactory_worker.providers.fake import FakeProvider

REQUEST = "Note de cadrage du projet de gestion de stock"


class Flaky:
    """The demo brain behind a provider whose first `failures` calls raise `kind`."""

    def __init__(self, kind: str = "rate_limit", failures: int = 0) -> None:
        self.kind, self.failures, self.calls = kind, failures, 0
        self.inner = FakeProvider(responder=respond)

    async def complete(self, model: str, messages: list[Any], **kwargs: Any) -> Completion:
        self.calls += 1
        if self.calls <= self.failures:
            raise ProviderError(self.kind, provider="openai_api", status=429)  # type: ignore[arg-type]
        return await self.inner.complete(model, messages, **kwargs)


def engine(provider: Any, pricing: Pricing | None = None) -> LLM:
    return LLM(provider, "openai_api", "model-x", demo=False, pricing=pricing)


async def run(harness: Any, engines: Engines) -> Any:
    from nfactory_worker.pipeline import execute_run

    return await execute_run(
        harness.deps(engines=engines), harness.input("document", "document", REQUEST)
    )


async def test_a_rate_limited_call_is_retried_then_the_run_completes(harness: Any) -> None:
    flaky = Flaky("rate_limit", failures=1)

    result = await run(harness, Engines.single(engine(flaky)))

    assert result.outcome == "COMPLETED"
    agent_calls = len(harness.events("agent.progress"))
    assert flaky.calls >= agent_calls + 1


async def test_a_refused_key_fails_the_run_without_trying_another_engine(harness: Any) -> None:
    flaky = Flaky("auth", failures=99)

    result = await run(harness, Engines.single(engine(flaky), fallback="none"))

    assert result.outcome == "FAILED"
    assert result.error.startswith("OpenAI : clé refusée")
    assert flaky.calls == 1  # an auth error is not retried
    [failure] = harness.events("provider.failed")
    assert failure["role"] == "requirements" and failure["kind"] == "auth"
    assert not harness.events("agent.progress")  # nothing else answered in its place


async def test_with_ask_user_the_run_pauses_for_a_decision(harness: Any) -> None:
    flaky = Flaky("quota", failures=99)

    result = await run(harness, Engines.single(engine(flaky), fallback="ask_user"))

    assert result.outcome == "APPROVAL_PENDING"
    assert result.pause == {
        "role": "requirements",
        "provider": "openai_api",
        "model": "model-x",
        "kind": "quota",
        "message": result.error,
    }
    assert "quota" in result.error
    assert not harness.events("step.failed")  # paused, not failed


async def test_cost_adds_known_prices(harness: Any) -> None:
    price = Pricing(input_per_mtok=1.0, output_per_mtok=2.0)

    result = await run(harness, Engines.single(engine(Flaky(), price)))

    costs = [e["cost_usd"] for e in harness.events("agent.progress")]
    assert result.outcome == "COMPLETED"
    assert all(c is not None and c > 0 for c in costs)
    assert result.cost_usd == pytest.approx(sum(costs))


async def test_one_unpriced_engine_makes_the_run_cost_unmeasured(harness: Any) -> None:
    priced = engine(Flaky(), Pricing(input_per_mtok=1.0, output_per_mtok=2.0))
    engines = Engines.single(priced)
    engines = Engines({**engines.llms, "reviewer": engine(Flaky())})

    result = await run(harness, engines)

    assert result.outcome == "COMPLETED"
    assert result.cost_usd is None


async def test_the_demo_engine_costs_nothing(harness: Any) -> None:
    result = await run(harness, Engines.single(harness.demo()))

    assert result.cost_usd == 0.0
