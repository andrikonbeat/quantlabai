"""Tests for CircuitBreaker — state transitions, thresholds, async call()."""

import asyncio
import time

import pytest

from quantlab.robustness.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
)


class TestCircuitBreakerInitialState:
    """CircuitBreaker starts in CLOSED state."""

    @pytest.mark.asyncio
    async def test_initial_state_is_closed(self):
        cb = CircuitBreaker()
        assert cb.state == "CLOSED"

    @pytest.mark.asyncio
    async def test_initial_failure_count_is_zero(self):
        cb = CircuitBreaker()
        assert cb._failure_count == 0


class TestCircuitBreakerClosedToOpen:
    """CLOSED → OPEN transition after threshold failures."""

    @pytest.mark.asyncio
    async def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.state == "CLOSED"
        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == "CLOSED"
        await cb.record_failure()
        assert cb.state == "OPEN"

    @pytest.mark.asyncio
    async def test_raises_circuit_open_error_when_open(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == "OPEN"
        with pytest.raises(CircuitOpenError):
            await cb.call(asyncio.sleep(0))

    @pytest.mark.asyncio
    async def test_custom_threshold_opens_at_limit(self):
        cb = CircuitBreaker(failure_threshold=2)
        await cb.record_failure()
        assert cb.state == "CLOSED"
        await cb.record_failure()
        assert cb.state == "OPEN"


class TestCircuitBreakerOpenToHalfOpen:
    """OPEN → HALF_OPEN transition after recovery timeout."""

    @pytest.mark.asyncio
    async def test_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.05)
        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == "OPEN"
        await asyncio.sleep(0.06)
        assert cb.state == "HALF_OPEN"

    @pytest.mark.asyncio
    async def test_open_stays_open_before_timeout(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.5)
        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == "OPEN"
        await asyncio.sleep(0.05)
        assert cb.state == "OPEN"


class TestCircuitBreakerHalfOpenToClosed:
    """HALF_OPEN → CLOSED transition on probe success."""

    @pytest.mark.asyncio
    async def test_half_open_closes_on_success(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.05)
        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == "OPEN"
        await asyncio.sleep(0.06)
        assert cb.state == "HALF_OPEN"
        await cb.record_success()
        assert cb.state == "CLOSED"
        assert cb._failure_count == 0

    @pytest.mark.asyncio
    async def test_half_open_resets_failure_count_on_success(self):
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=0.05)
        for _ in range(4):
            await cb.record_failure()
        assert cb.state == "CLOSED"
        await cb.record_failure()
        assert cb.state == "OPEN"
        await asyncio.sleep(0.06)
        assert cb.state == "HALF_OPEN"
        await cb.record_success()
        assert cb.state == "CLOSED"
        assert cb._failure_count == 0


class TestCircuitBreakerHalfOpenToOpen:
    """HALF_OPEN → OPEN transition on probe failure."""

    @pytest.mark.asyncio
    async def test_half_open_reopens_on_failure(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.05)
        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == "OPEN"
        await asyncio.sleep(0.06)
        assert cb.state == "HALF_OPEN"
        await cb.record_failure()
        assert cb.state == "OPEN"

    @pytest.mark.asyncio
    async def test_half_open_reopens_resets_half_open_calls(self):
        cb = CircuitBreaker(
            failure_threshold=2, recovery_timeout=0.05, half_open_max_calls=1
        )
        await cb.record_failure()
        await cb.record_failure()
        assert cb.state == "OPEN"
        await asyncio.sleep(0.06)
        assert cb.state == "HALF_OPEN"
        await cb.record_failure()
        assert cb.state == "OPEN"
        await asyncio.sleep(0.06)
        assert cb.state == "HALF_OPEN"


class TestCircuitBreakerAsyncCall:
    """async call() method wraps coroutines with circuit breaker logic."""

    @pytest.mark.asyncio
    async def test_call_passes_through_in_closed_state(self):
        cb = CircuitBreaker()

        async def fetch_data():
            return "data"

        result = await cb.call(fetch_data())
        assert result == "data"

    @pytest.mark.asyncio
    async def test_call_records_success_on_completion(self):
        cb = CircuitBreaker(failure_threshold=3)

        async def fetch_data():
            return "ok"

        await cb.call(fetch_data())
        assert cb.state == "CLOSED"
        assert cb._failure_count == 0

    @pytest.mark.asyncio
    async def test_call_records_failure_on_exception(self):
        cb = CircuitBreaker(failure_threshold=2)

        async def fail():
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            await cb.call(fail())
        assert cb._failure_count == 1

    @pytest.mark.asyncio
    async def test_call_raises_circuit_open_error_when_open(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.5)

        async def fail():
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await cb.call(fail())
        assert cb.state == "OPEN"
        with pytest.raises(CircuitOpenError):
            await cb.call(asyncio.sleep(0))

    @pytest.mark.asyncio
    async def test_call_recovers_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.05)

        async def fail():
            raise RuntimeError("boom")

        async def succeed():
            return "recovered"

        with pytest.raises(RuntimeError):
            await cb.call(fail())
        assert cb.state == "OPEN"
        await asyncio.sleep(0.06)
        result = await cb.call(succeed())
        assert result == "recovered"
        assert cb.state == "CLOSED"

    @pytest.mark.asyncio
    async def test_call_half_open_success_closes_circuit(self):
        """call() in HALF_OPEN that succeeds transitions to CLOSED."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.05)

        async def fail():
            raise RuntimeError("boom")

        async def succeed():
            return "ok"

        with pytest.raises(RuntimeError):
            await cb.call(fail())
        assert cb.state == "OPEN"
        await asyncio.sleep(0.06)
        result = await cb.call(succeed())
        assert result == "ok"
        assert cb.state == "CLOSED"

    @pytest.mark.asyncio
    async def test_call_half_open_failure_reopens_circuit(self):
        """call() in HALF_OPEN that fails transitions back to OPEN."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.05)

        async def fail():
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await cb.call(fail())
        assert cb.state == "OPEN"
        await asyncio.sleep(0.06)
        with pytest.raises(RuntimeError):
            await cb.call(fail())
        assert cb.state == "OPEN"

    @pytest.mark.asyncio
    async def test_half_open_allows_multiple_probes_with_high_max(self):
        """half_open_max_calls > 1 allows multiple probe calls."""
        cb = CircuitBreaker(
            failure_threshold=1, recovery_timeout=0.05, half_open_max_calls=3
        )

        async def succeed():
            return "ok"

        await cb.record_failure()
        assert cb.state == "OPEN"
        await asyncio.sleep(0.06)

        result1 = await cb.call(succeed())
        assert result1 == "ok"
        assert cb.state == "CLOSED"
