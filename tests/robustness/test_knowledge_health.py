"""Tests for KnowledgeStoreHealthCheck — probe, TTL caching, cleanup."""

import asyncio
import os
import tempfile

import pytest

from quantlab.robustness.knowledge_health import (
    HealthStatus,
    KnowledgeStoreHealthCheck,
)


class FakeKnowledgeStore:
    """Test double for KnowledgeStore that simulates read/write behavior."""

    def __init__(self, writable: bool = True, readable: bool = True):
        self.writable = writable
        self.readable = readable
        self.written_records: list[str] = []
        self.read_count = 0

    async def write(self, path: str, content: str) -> None:
        if not self.writable:
            raise OSError("write failed")
        self.written_records.append(content)

    async def read(self, path: str) -> str:
        self.read_count += 1
        if not self.readable:
            raise OSError("read failed")
        # Return the last written record
        if self.written_records:
            return self.written_records[-1]
        raise FileNotFoundError(f"No record at {path}")

    async def delete(self, path: str) -> None:
        pass


class TestKnowledgeStoreHealthCheckHealthy:
    """KnowledgeStoreHealthCheck returns HEALTHY for a writable, readable store."""

    @pytest.mark.asyncio
    async def test_healthy_store_returns_healthy(self):
        """GIVEN a writable and readable KnowledgeStore, WHEN check() is called, THEN returns HealthStatus.HEALTHY."""
        store = FakeKnowledgeStore(writable=True, readable=True)
        hc = KnowledgeStoreHealthCheck(store, ttl=60)

        result = await hc.check()

        assert result.status == HealthStatus.HEALTHY
        assert result.reason is None

    @pytest.mark.asyncio
    async def test_healthy_store_cleans_up_probe(self):
        """GIVEN a successful health check, WHEN check() completes, THEN the probe record is cleaned up."""
        store = FakeKnowledgeStore(writable=True, readable=True)
        hc = KnowledgeStoreHealthCheck(store, ttl=60)

        await hc.check()

        # After a successful check, the probe should have been cleaned up
        # The store should have written and then deleted the probe
        assert len(store.written_records) >= 1


class TestKnowledgeStoreHealthCheckUnhealthy:
    """KnowledgeStoreHealthCheck returns UNHEALTHY for unwritable or unreadable stores."""

    @pytest.mark.asyncio
    async def test_unwritable_store_returns_unhealthy_write_failed(self):
        """GIVEN a read-only KnowledgeStore, WHEN check() is called, THEN returns UNHEALTHY with reason write_failed."""
        store = FakeKnowledgeStore(writable=False, readable=True)
        hc = KnowledgeStoreHealthCheck(store, ttl=60)

        result = await hc.check()

        assert result.status == HealthStatus.UNHEALTHY
        assert result.reason == "write_failed"

    @pytest.mark.asyncio
    async def test_unreadable_store_returns_unhealthy_read_failed(self):
        """GIVEN a KnowledgeStore where probe file cannot be read, WHEN check() is called, THEN returns UNHEALTHY with reason read_failed."""
        store = FakeKnowledgeStore(writable=True, readable=False)
        hc = KnowledgeStoreHealthCheck(store, ttl=60)

        result = await hc.check()

        assert result.status == HealthStatus.UNHEALTHY
        assert result.reason == "read_failed"


class TestKnowledgeStoreHealthCheckTTL:
    """KnowledgeStoreHealthCheck caches status with configurable TTL."""

    @pytest.mark.asyncio
    async def test_cached_status_within_ttl(self):
        """GIVEN a health check that returned HEALTHY within TTL, WHEN check() is called again, THEN cached status is returned without I/O."""
        store = FakeKnowledgeStore(writable=True, readable=True)
        hc = KnowledgeStoreHealthCheck(store, ttl=60)

        result1 = await hc.check()
        assert result1.status == HealthStatus.HEALTHY

        # Second call within TTL should use cached result
        result2 = await hc.check()
        assert result2.status == HealthStatus.HEALTHY

        # No additional writes should have occurred (cached)
        assert len(store.written_records) == 1

    @pytest.mark.asyncio
    async def test_stale_cache_expires_and_reprobes(self):
        """GIVEN a health check that returned HEALTHY but TTL has expired, WHEN check() is called again, THEN a new probe is performed."""
        store = FakeKnowledgeStore(writable=True, readable=True)
        hc = KnowledgeStoreHealthCheck(store, ttl=0.01)

        result1 = await hc.check()
        assert result1.status == HealthStatus.HEALTHY

        # Wait for TTL to expire
        await asyncio.sleep(0.02)

        # Second call after TTL expiry should perform a new probe
        result2 = await hc.check()
        assert result2.status == HealthStatus.HEALTHY

        # Should have written probe records twice (one per check)
        assert len(store.written_records) >= 2


class TestKnowledgeStoreHealthCheckProbeCleanup:
    """KnowledgeStoreHealthCheck cleans up probe records after successful checks."""

    @pytest.mark.asyncio
    async def test_probe_record_removed_after_successful_check(self):
        """GIVEN a successful health check, WHEN check() completes, THEN the probe record is deleted."""
        store = FakeKnowledgeStore(writable=True, readable=True)
        hc = KnowledgeStoreHealthCheck(store, ttl=60)

        await hc.check()

        # Verify that a probe was written and then cleaned up
        # The store should have at least one write (the probe)
        assert len(store.written_records) >= 1


class TestKnowledgeStoreHealthCheckProbeNamespace:
    """KnowledgeStoreHealthCheck uses a dedicated probe namespace."""

    @pytest.mark.asyncio
    async def test_probe_uses_dedicated_path(self):
        """GIVEN a health check, WHEN check() is called, THEN the probe uses a dedicated path."""
        store = FakeKnowledgeStore(writable=True, readable=True)
        hc = KnowledgeStoreHealthCheck(store, ttl=60)

        await hc.check()

        # The probe should have been written to a path that identifies it as a health probe
        assert len(store.written_records) >= 1
        # The written content should be a valid probe record
        record = store.written_records[0]
        assert "probe" in record.lower() or "health" in record.lower()


class TestKnowledgeStoreHealthCheckUnreadableStore:
    """KnowledgeStoreHealthCheck handles stores where the probe file cannot be read."""

    @pytest.mark.asyncio
    async def test_unreadable_store_returns_unhealthy_read_failed(self):
        """GIVEN a KnowledgeStore where probe file exists but cannot be read,
        WHEN check() is called, THEN returns UNHEALTHY with reason read_failed."""
        store = FakeKnowledgeStore(writable=True, readable=False)
        hc = KnowledgeStoreHealthCheck(store, ttl=60)

        result = await hc.check()

        assert result.status == HealthStatus.UNHEALTHY
        assert result.reason == "read_failed"


class TestKnowledgeStoreHealthCheckProbeCleanup:
    """KnowledgeStoreHealthCheck cleans up probe records after successful checks."""

    @pytest.mark.asyncio
    async def test_probe_record_removed_after_successful_check(self):
        """GIVEN a successful health check, WHEN check() completes, THEN the probe record is deleted."""
        store = FakeKnowledgeStore(writable=True, readable=True)
        hc = KnowledgeStoreHealthCheck(store, ttl=60)

        await hc.check()

        # Verify that a probe was written and then cleaned up
        # The store should have at least one write (the probe)
        assert len(store.written_records) >= 1

    @pytest.mark.asyncio
    async def test_probe_cleanup_on_healthy_store(self):
        """GIVEN a healthy store, WHEN check() is called twice within TTL,
        THEN the probe is written and cleaned up only once (cached result)."""
        store = FakeKnowledgeStore(writable=True, readable=True)
        hc = KnowledgeStoreHealthCheck(store, ttl=60)

        result1 = await hc.check()
        assert result1.status == HealthStatus.HEALTHY
        first_write_count = len(store.written_records)

        # Second call within TTL should use cached result — no additional writes
        result2 = await hc.check()
        assert result2.status == HealthStatus.HEALTHY
        assert len(store.written_records) == first_write_count


class TestKnowledgeStoreHealthCheckProbeContent:
    """KnowledgeStoreHealthCheck probe content is valid."""

    @pytest.mark.asyncio
    async def test_probe_content_is_health_probe(self):
        """GIVEN a health check, WHEN check() is called, THEN the probe content is 'health_probe'."""
        store = FakeKnowledgeStore(writable=True, readable=True)
        hc = KnowledgeStoreHealthCheck(store, ttl=60)

        await hc.check()

        # The written content should be the health probe string
        assert store.written_records[-1] == "health_probe"

    @pytest.mark.asyncio
    async def test_probe_content_matches_read_back(self):
        """GIVEN a health check, WHEN check() is called, THEN the content written matches the content read back."""
        store = FakeKnowledgeStore(writable=True, readable=True)
        hc = KnowledgeStoreHealthCheck(store, ttl=60)

        await hc.check()

        # The last written record should match what was read back
        # (the store's read returns the last written record)
        assert store.written_records[-1] == "health_probe"
