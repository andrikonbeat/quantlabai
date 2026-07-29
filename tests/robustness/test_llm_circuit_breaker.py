"""Tests for LLMCircuitBreaker — state transitions, fallback integration."""

import asyncio

import pytest

from quantlab.robustness.circuit_breaker import CircuitOpenError
from quantlab.robustness.llm_circuit_breaker import LLMCircuitBreaker


class TestLLMCircuitBreakerInitialState:
    """LLMCircuitBreaker starts in CLOSED state."""

    @pytest.mark.asyncio
    async def test_initial_state_is_closed(self):
        lb = LLMCircuitBreaker()
        assert lb.state == "CLOSED"

    @pytest.mark.asyncio
    async def test_initial_failure_count_is_zero(self):
        lb = LLMCircuitBreaker()
        assert lb._circuit_breaker._failure_count == 0


class TestLLMCircuitBreakerClosedToOpen:
    """CLOSED → OPEN transition after threshold failures."""

    @pytest.mark.asyncio
    async def test_opens_after_threshold_failures(self):
        lb = LLMCircuitBreaker(failure_threshold=3)
        assert lb.state == "CLOSED"
        await lb._circuit_breaker.record_failure()
        await lb._circuit_breaker.record_failure()
        assert lb.state == "CLOSED"
        await lb._circuit_breaker.record_failure()
        assert lb.state == "OPEN"

    @pytest.mark.asyncio
    async def test_raises_circuit_open_error_when_open(self):
        lb = LLMCircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        await lb._circuit_breaker.record_failure()
        await lb._circuit_breaker.record_failure()
        assert lb.state == "OPEN"
        with pytest.raises(CircuitOpenError):
            await lb.call(asyncio.sleep(0))

    @pytest.mark.asyncio
    async def test_custom_threshold_opens_at_limit(self):
        lb = LLMCircuitBreaker(failure_threshold=2)
        await lb._circuit_breaker.record_failure()
        assert lb.state == "CLOSED"
        await lb._circuit_breaker.record_failure()
        assert lb.state == "OPEN"


class TestLLMCircuitBreakerOpenToHalfOpen:
    """OPEN → HALF_OPEN transition after recovery timeout."""

    @pytest.mark.asyncio
    async def test_half_open_after_recovery_timeout(self):
        lb = LLMCircuitBreaker(failure_threshold=2, recovery_timeout=0.05)
        await lb._circuit_breaker.record_failure()
        await lb._circuit_breaker.record_failure()
        assert lb.state == "OPEN"
        await asyncio.sleep(0.06)
        assert lb.state == "HALF_OPEN"

    @pytest.mark.asyncio
    async def test_open_stays_open_before_timeout(self):
        lb = LLMCircuitBreaker(failure_threshold=2, recovery_timeout=0.5)
        await lb._circuit_breaker.record_failure()
        await lb._circuit_breaker.record_failure()
        assert lb.state == "OPEN"
        await asyncio.sleep(0.05)
        assert lb.state == "OPEN"


class TestLLMCircuitBreakerHalfOpenToClosed:
    """HALF_OPEN → CLOSED transition on probe success."""

    @pytest.mark.asyncio
    async def test_half_open_closes_on_success(self):
        lb = LLMCircuitBreaker(failure_threshold=2, recovery_timeout=0.05)
        await lb._circuit_breaker.record_failure()
        await lb._circuit_breaker.record_failure()
        assert lb.state == "OPEN"
        await asyncio.sleep(0.06)
        assert lb.state == "HALF_OPEN"
        await lb._circuit_breaker.record_success()
        assert lb.state == "CLOSED"
        assert lb._circuit_breaker._failure_count == 0


class TestLLMCircuitBreakerHalfOpenToOpen:
    """HALF_OPEN → OPEN transition on probe failure."""

    @pytest.mark.asyncio
    async def test_half_open_reopens_on_failure(self):
        lb = LLMCircuitBreaker(failure_threshold=2, recovery_timeout=0.05)
        await lb._circuit_breaker.record_failure()
        await lb._circuit_breaker.record_failure()
        assert lb.state == "OPEN"
        await asyncio.sleep(0.06)
        assert lb.state == "HALF_OPEN"
        await lb._circuit_breaker.record_failure()
        assert lb.state == "OPEN"


class TestLLMCircuitBreakerCall:
    """call() method wraps coroutines with circuit breaker logic."""

    @pytest.mark.asyncio
    async def test_call_passes_through_in_closed_state(self):
        lb = LLMCircuitBreaker()

        async def fetch_llm():
            return "llm response"

        result = await lb.call(fetch_llm())
        assert result == "llm response"

    @pytest.mark.asyncio
    async def test_call_records_success_on_completion(self):
        lb = LLMCircuitBreaker(failure_threshold=3)

        async def fetch_llm():
            return "ok"

        await lb.call(fetch_llm())
        assert lb.state == "CLOSED"
        assert lb._circuit_breaker._failure_count == 0

    @pytest.mark.asyncio
    async def test_call_records_failure_on_exception(self):
        lb = LLMCircuitBreaker(failure_threshold=2)

        async def fail_llm():
            raise RuntimeError("LLM timeout")

        with pytest.raises(RuntimeError, match="LLM timeout"):
            await lb.call(fail_llm())
        assert lb._circuit_breaker._failure_count == 1

    @pytest.mark.asyncio
    async def test_call_raises_circuit_open_error_when_open(self):
        lb = LLMCircuitBreaker(failure_threshold=1, recovery_timeout=0.5)

        async def fail_llm():
            raise RuntimeError("LLM timeout")

        with pytest.raises(RuntimeError):
            await lb.call(fail_llm())
        assert lb.state == "OPEN"
        with pytest.raises(CircuitOpenError):
            await lb.call(asyncio.sleep(0))

    @pytest.mark.asyncio
    async def test_call_recovers_after_timeout(self):
        lb = LLMCircuitBreaker(failure_threshold=1, recovery_timeout=0.05)

        async def fail_llm():
            raise RuntimeError("LLM timeout")

        async def succeed_llm():
            return "recovered"

        with pytest.raises(RuntimeError):
            await lb.call(fail_llm())
        assert lb.state == "OPEN"
        await asyncio.sleep(0.06)
        result = await lb.call(succeed_llm())
        assert result == "recovered"
        assert lb.state == "CLOSED"

    @pytest.mark.asyncio
    async def test_call_half_open_success_closes_circuit(self):
        """call() in HALF_OPEN that succeeds transitions to CLOSED."""
        lb = LLMCircuitBreaker(failure_threshold=1, recovery_timeout=0.05)

        async def fail_llm():
            raise RuntimeError("LLM timeout")

        async def succeed_llm():
            return "ok"

        with pytest.raises(RuntimeError):
            await lb.call(fail_llm())
        assert lb.state == "OPEN"
        await asyncio.sleep(0.06)
        result = await lb.call(succeed_llm())
        assert result == "ok"
        assert lb.state == "CLOSED"

    @pytest.mark.asyncio
    async def test_call_half_open_failure_reopens_circuit(self):
        """call() in HALF_OPEN that fails transitions back to OPEN."""
        lb = LLMCircuitBreaker(failure_threshold=1, recovery_timeout=0.05)

        async def fail_llm():
            raise RuntimeError("LLM timeout")

        with pytest.raises(RuntimeError):
            await lb.call(fail_llm())
        assert lb.state == "OPEN"
        await asyncio.sleep(0.06)
        with pytest.raises(RuntimeError):
            await lb.call(fail_llm())
        assert lb.state == "OPEN"


class TestLLMCircuitBreakerFallbackIntegration:
    """LLMCircuitBreaker integrates with LLMResearchAgent fallback chain."""

    @pytest.mark.asyncio
    async def test_open_circuit_triggers_fallback(self):
        """GIVEN an OPEN circuit breaker, WHEN call_llm is invoked, THEN CircuitOpenError is raised
        which triggers the existing fallback chain in LLMResearchAgent."""
        lb = LLMCircuitBreaker(failure_threshold=1, recovery_timeout=0.5)

        async def fail_llm():
            raise RuntimeError("LLM timeout")

        # First call fails and opens the circuit
        with pytest.raises(RuntimeError):
            await lb.call(fail_llm())
        assert lb.state == "OPEN"

        # Subsequent calls raise CircuitOpenError immediately (skipping LLM)
        with pytest.raises(CircuitOpenError):
            await lb.call(fail_llm())

    @pytest.mark.asyncio
    async def test_closed_circuit_allows_llm_call(self):
        """GIVEN a CLOSED circuit breaker, WHEN call_llm is invoked, THEN the LLM call proceeds normally."""
        lb = LLMCircuitBreaker()

        async def succeed_llm():
            return "research result"

        result = await lb.call(succeed_llm())
        assert result == "research result"
        assert lb.state == "CLOSED"

    @pytest.mark.asyncio
    async def test_custom_failure_threshold(self):
        """GIVEN a custom failure_threshold, WHEN failures reach threshold, THEN circuit opens."""
        lb = LLMCircuitBreaker(failure_threshold=5)

        for _ in range(4):
            await lb._circuit_breaker.record_failure()
        assert lb.state == "CLOSED"
        await lb._circuit_breaker.record_failure()
        assert lb.state == "OPEN"

    @pytest.mark.asyncio
    async def test_custom_recovery_timeout(self):
        """GIVEN a custom recovery_timeout, WHEN timeout elapses, THEN circuit transitions to HALF_OPEN."""
        lb = LLMCircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        await lb._circuit_breaker.record_failure()
        assert lb.state == "OPEN"
        await asyncio.sleep(0.12)
        assert lb.state == "HALF_OPEN"
