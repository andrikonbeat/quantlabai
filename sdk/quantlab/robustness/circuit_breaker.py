"""CircuitBreaker — async-safe state machine for protecting I/O calls from cascading failures."""

from __future__ import annotations

import asyncio
import time


class CircuitOpenError(Exception):
    """Raised when a call is rejected because the circuit breaker is OPEN."""


class CircuitBreaker:
    """Async-safe circuit breaker with CLOSED, OPEN, and HALF_OPEN states.

    Parameters
    ----------
    failure_threshold: int
        Consecutive failures needed to transition from CLOSED to OPEN.
        Default is 5.
    recovery_timeout: float
        Seconds to wait in OPEN state before transitioning to HALF_OPEN.
        Default is 30.0.
    half_open_max_calls: int
        Maximum probe calls allowed in HALF_OPEN state. Default is 1.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._failure_count = 0
        self._last_failure_time: float | None = None
        self._state = "CLOSED"
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        """Current circuit breaker state: CLOSED, OPEN, or HALF_OPEN.

        Automatically transitions from OPEN to HALF_OPEN when the
        recovery timeout has elapsed.
        """
        if self._state == "OPEN" and self._last_failure_time is not None:
            if time.time() - self._last_failure_time > self.recovery_timeout:
                return "HALF_OPEN"
        return self._state

    async def call(self, coro) -> any:
        """Execute an async coroutine through the circuit breaker.

        Parameters
        ----------
        coro: Awaitable
            The coroutine to execute.

        Returns
        -------
        The result of the coroutine.

        Raises
        ------
        CircuitOpenError
            If the circuit is OPEN and the recovery timeout has not elapsed,
            or if HALF_OPEN max calls have been exhausted.
        Exception
            Any exception raised by the coroutine is re-raised after recording
            the failure.
        """
        async with self._lock:
            if self._state == "OPEN":
                if (
                    self._last_failure_time is not None
                    and time.time() - self._last_failure_time > self.recovery_timeout
                ):
                    self._state = "HALF_OPEN"
                    self._half_open_calls = 0
                else:
                    raise CircuitOpenError("Circuit breaker is open")

            if self._state == "HALF_OPEN":
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitOpenError("Circuit breaker is open")
                self._half_open_calls += 1

        try:
            result = await coro
            await self.record_success()
            return result
        except Exception:
            await self.record_failure()
            raise

    async def record_success(self) -> None:
        """Record a successful call, resetting the failure counter and closing the circuit."""
        async with self._lock:
            self._failure_count = 0
            self._half_open_calls = 0
            self._state = "CLOSED"

    async def record_failure(self) -> None:
        """Record a failed call, incrementing the failure counter and opening the circuit if threshold is reached."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._state == "HALF_OPEN":
                self._state = "OPEN"
                self._half_open_calls = 0
            elif self._failure_count >= self.failure_threshold:
                self._state = "OPEN"
