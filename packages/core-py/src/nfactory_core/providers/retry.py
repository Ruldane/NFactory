"""Retry transient provider failures (rate limit, timeout, overload), and only those.

A quota or an invalid key never gets better by retrying: it fails at once.
"""

import asyncio
from collections.abc import Awaitable, Callable

from nfactory_core.providers.errors import ProviderError

Sleep = Callable[[float], Awaitable[None]]


async def with_retries[T](
    call: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay_s: float = 2.0,
    max_delay_s: float = 30.0,
    sleep: Sleep = asyncio.sleep,
) -> T:
    for attempt in range(1, attempts + 1):
        try:
            return await call()
        except ProviderError as error:
            if not error.retryable or attempt == attempts:
                raise
            delay = (
                error.retry_after
                if error.retry_after is not None
                else base_delay_s * 2 ** (attempt - 1)
            )
            await sleep(min(delay, max_delay_s))
    raise AssertionError("unreachable")  # pragma: no cover
