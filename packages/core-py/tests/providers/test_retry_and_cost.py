"""Retries only for transient errors; cost only when the price is known (task 2.1)."""

import pytest

from nfactory_core.providers.errors import ProviderError
from nfactory_core.providers.pricing import Pricing, cost_usd, pricing_from
from nfactory_core.providers.retry import with_retries
from nfactory_core.providers.types import Usage


class Flaky:
    def __init__(self, *errors: ProviderError) -> None:
        self.errors = list(errors)
        self.calls = 0

    async def __call__(self) -> str:
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return "ok"


async def test_rate_limit_is_retried_after_the_announced_delay() -> None:
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    call = Flaky(ProviderError("rate_limit", provider="openai_api", retry_after=4))

    assert await with_retries(call, sleep=sleep) == "ok"
    assert call.calls == 2
    assert slept == [4]


async def test_quota_is_never_retried() -> None:
    call = Flaky(ProviderError("quota", provider="openai_api"))

    with pytest.raises(ProviderError) as caught:
        await with_retries(call, sleep=_no_sleep)

    assert caught.value.kind == "quota"
    assert call.calls == 1


async def test_retries_stop_after_the_last_attempt() -> None:
    call = Flaky(*[ProviderError("unavailable", provider="deepseek_api") for _ in range(5)])

    with pytest.raises(ProviderError):
        await with_retries(call, attempts=3, sleep=_no_sleep)

    assert call.calls == 3


async def test_announced_delays_are_capped() -> None:
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    call = Flaky(ProviderError("rate_limit", provider="openai_api", retry_after=3600))
    await with_retries(call, sleep=sleep, max_delay_s=30)

    assert slept == [30]


async def _no_sleep(seconds: float) -> None:
    return None


def test_cost_uses_the_admin_price_and_counts_cached_tokens_at_their_rate() -> None:
    price = Pricing(input_per_mtok=2.0, output_per_mtok=10.0, cached_input_per_mtok=0.2)
    usage = Usage(input_tokens=1_000_000, output_tokens=100_000, cached_input_tokens=500_000)

    # 500k uncached x 2 + 500k cached x 0.2 + 100k output x 10, per million
    assert cost_usd(usage, price) == pytest.approx(1.0 + 0.1 + 1.0)


def test_unknown_price_means_unmeasured_not_zero() -> None:
    assert cost_usd(Usage(10, 10), None) is None


def test_price_is_read_from_catalog_capabilities() -> None:
    assert pricing_from({"pricing": {"input_per_mtok": 1, "output_per_mtok": 4}}) == Pricing(1, 4)
    assert pricing_from({}) is None
    assert pricing_from({"pricing": {"input_per_mtok": "x"}}) is None
