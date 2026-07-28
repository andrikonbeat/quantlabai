"""Token-bucket rate limiter for async providers."""

from __future__ import annotations

import asyncio
import time


class TokenBucket:
    """Async-safe token-bucket rate limiter.

    Refills tokens continuously based on elapsed time. ``acquire`` blocks
    until a token is available, making it suitable for per-provider rate
    limiting in concurrent scenarios.

    Args:
        rate: Tokens per second (refill rate).
        capacity: Maximum token count (burst allowance).

    Example::

        bucket = TokenBucket(rate=5.0, capacity=10)
        await bucket.acquire()   # may sleep if no tokens remain
    """

    def __init__(self, rate: float, capacity: int) -> None:
        if rate <= 0:
            raise ValueError("rate must be positive")
        if capacity < 1:
            raise ValueError("capacity must be at least 1")

        self.rate = rate
        self.capacity = capacity
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a token is available, then consume one.

        This method is safe to call concurrently from multiple coroutines
        because token refill and consumption are serialised by an
        ``asyncio.Lock``.
        """
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                wait = (1.0 - self._tokens) / self.rate if self.rate > 0 else 0.1

            await asyncio.sleep(max(wait, 0.001))

    def _refill(self) -> None:
        """Add tokens based on elapsed time since last refill."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last_refill = now

    @property
    def available_tokens(self) -> float:
        """Current token count (non-negative, may be fractional)."""
        return self._tokens
