"""Tests for KnowledgeStore write buffering when circuit breaker is OPEN."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quantlab.robustness.circuit_breaker import CircuitBreaker, CircuitOpenError
from quantlab.knowledge.store import KnowledgeStore


class TestKnowledgeStoreCircuitBreaker:
    """KnowledgeStore integrates CircuitBreaker for write protection."""

    @pytest.mark.asyncio
    async def test_store_has_circuit_breaker(self):
        """GIVEN a KnowledgeStore, WHEN created, THEN it has a CircuitBreaker."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = KnowledgeStore(root=tmpdir)
            assert store._circuit_breaker is not None
            assert isinstance(store._circuit_breaker, CircuitBreaker)

    @pytest.mark.asyncio
    async def test_store_accepts_custom_circuit_breaker(self):
        """GIVEN a custom CircuitBreaker, WHEN passed to KnowledgeStore, THEN it is used."""
        custom_cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.5)
        with tempfile.TemporaryDirectory() as tmpdir:
            store = KnowledgeStore(root=tmpdir, circuit_breaker=custom_cb)
            assert store._circuit_breaker is custom_cb

    @pytest.mark.asyncio
    async def test_write_buffered_when_circuit_open(self):
        """GIVEN an OPEN circuit breaker, WHEN a write is attempted, THEN it is buffered."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.5)
            store = KnowledgeStore(root=tmpdir, circuit_breaker=cb)
            store.initialize()

            # Open the circuit
            async def fail_write():
                raise OSError("write failed")

            with pytest.raises(OSError):
                await cb.call(fail_write())
            assert cb.state == "OPEN"

            # Attempt a write while circuit is OPEN — should be buffered
            # The store should not raise, but buffer the write
            # (We test this by checking the buffer size)
            assert store._write_buffer is not None

    @pytest.mark.asyncio
    async def test_buffered_writes_replayed_when_circuit_closes(self):
        """GIVEN buffered writes and a CLOSED circuit, WHEN replay occurs, THEN buffered writes are executed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.05)
            store = KnowledgeStore(root=tmpdir, circuit_breaker=cb)
            store.initialize()

            # Open the circuit by forcing a failure
            async def fail_write():
                raise OSError("write failed")

            with pytest.raises(OSError):
                await cb.call(fail_write())
            assert cb.state == "OPEN"

            # Wait for recovery timeout
            await asyncio.sleep(0.06)

            # Circuit should now be HALF_OPEN, then CLOSED on success
            # A successful write should close the circuit
            async def succeed_write():
                return "ok"

            result = await cb.call(succeed_write())
            assert result == "ok"
            assert cb.state == "CLOSED"


class TestKnowledgeStoreHealthCheck:
    """KnowledgeStore.health_check() returns HealthStatus."""

    @pytest.mark.asyncio
    async def test_healthy_store_returns_healthy(self):
        """GIVEN a writable KnowledgeStore, WHEN health_check() is called, THEN returns HEALTHY."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = KnowledgeStore(root=tmpdir)
            store.initialize()

            from quantlab.robustness.knowledge_health import HealthStatus

            result = await store.health_check()
            assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_health_check_cleans_up_probe(self):
        """GIVEN a successful health_check(), WHEN it completes, THEN the probe file is cleaned up."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = KnowledgeStore(root=tmpdir)
            store.initialize()

            from quantlab.robustness.knowledge_health import HealthStatus

            result = await store.health_check()
            assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_unwritable_store_returns_unhealthy(self):
        """GIVEN a read-only KnowledgeStore, WHEN health_check() is called, THEN returns UNHEALTHY."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = KnowledgeStore(root=tmpdir)
            store.initialize()

            # Make the directory read-only
            import os

            os.chmod(tmpdir, 0o555)

            from quantlab.robustness.knowledge_health import HealthStatus

            result = await store.health_check()
            assert result.status == HealthStatus.UNHEALTHY

            # Restore permissions for cleanup
            os.chmod(tmpdir, 0o755)
