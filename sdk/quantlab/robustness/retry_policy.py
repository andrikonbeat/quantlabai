"""RetryPolicy — configurable retry with exponential backoff and jitter."""

from __future__ import annotations

import asyncio
import random


class RetryPolicy:
    """Async retry policy with exponential backoff and optional jitter.

    Parameters
    ----------
    max_retries: int
        Maximum number of retry attempts. Default is 3.
    base_delay: float
        Initial delay in seconds. Default is 1.0.
    max_delay: float
        Maximum delay cap in seconds. Default is 60.0.
    jitter: bool
        Whether to add random jitter to each delay. Default is True.
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        jitter: bool = True,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter

    def _compute_delay(self, attempt: int) -> float:
        """Compute the delay for a given retry attempt.

        delay = min(base_delay * 2^attempt, max_delay)
        If jitter is enabled, a random value in [delay, delay * 1.3] is returned.
        """
        delay = min(self.base_delay * (2**attempt), self.max_delay)
        if self.jitter:
            delay = delay * (1.0 + random.random() * 0.3)
        return delay

    async def retry(self, coro, *, max_retries: int | None = None) -> any:
        """Execute an async coroutine with retry logic.

        Parameters
        ----------
        coro: Awaitable
            The coroutine to execute.
        max_retries: int, optional
            Override the policy's max_retries for this call.

        Returns
        -------
        The result of the coroutine.

        Raises
        ------
        Exception
            The last exception raised by the coroutine after all retries
            are exhausted.
        """
        effective_max_retries = max_retries if max_retries is not None else self.max_retries
        last_exception: Exception | None = None

        for attempt in range(effective_max_retries + 1):
            try:
                return await coro()
            except Exception as exc:
                last_exception = exc
                if attempt < effective_max_retries:
                    delay = self._compute_delay(attempt)
                    await asyncio.sleep(delay)

        raise last_exception
