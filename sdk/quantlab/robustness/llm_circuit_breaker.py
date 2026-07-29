"""LLMCircuitBreaker — wraps LLM API calls with circuit breaker protection."""

from __future__ import annotations

from typing import Any

from quantlab.robustness.circuit_breaker import CircuitBreaker, CircuitOpenError


class LLMCircuitBreaker:
    """Circuit breaker for LLM API calls integrated with the fallback chain.

    Wraps LLM calls with a :class:`CircuitBreaker`. When the circuit is
    ``OPEN``, LLM calls are skipped immediately and a :class:`CircuitOpenError`
    is raised, which triggers the existing fallback chain in
    :class:`LLMResearchAgent`.

    Parameters
    ----------
    failure_threshold: int
        Consecutive failures needed to transition from CLOSED to OPEN.
        Default is 3.
    recovery_timeout: float
        Seconds to wait in OPEN state before transitioning to HALF_OPEN.
        Default is 30.0.
    circuit_breaker: CircuitBreaker, optional
        Reuse an existing :class:`CircuitBreaker` instance.  When ``None``,
        a new one is created with the given thresholds.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self._circuit_breaker = circuit_breaker or CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )

    async def call(self, coro) -> Any:
        """Execute an LLM call through the circuit breaker.

        When the circuit is ``OPEN``, :class:`CircuitOpenError` is raised
        immediately, which triggers the fallback chain in
        :class:`LLMResearchAgent.generate_config()`.

        Parameters
        ----------
        coro: Awaitable
            The LLM call coroutine to execute.

        Returns
        -------
        The result of the LLM call.

        Raises
        ------
        CircuitOpenError
            If the circuit is OPEN (triggers fallback in generate_config).
        Exception
            Any exception raised by the coroutine is re-raised after
            recording the failure.
        """
        return await self._circuit_breaker.call(coro)

    @property
    def state(self) -> str:
        """Current circuit breaker state: CLOSED, OPEN, or HALF_OPEN."""
        return self._circuit_breaker.state
