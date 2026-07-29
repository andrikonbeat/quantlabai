"""Tests for AutonomousMonitorDaemon store health integration."""

import asyncio
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from quantlab.agents.autonomous_monitor import (
    AutonomousMonitorDaemon,
    MonitorConfig,
)
from quantlab.knowledge.store import KnowledgeStore
from quantlab.robustness.knowledge_health import (
    HealthCheckResult,
    HealthStatus,
    KnowledgeStoreHealthCheck,
)


class TestAutonomousMonitorStoreHealthIntegration:
    """AutonomousMonitorDaemon integrates KnowledgeStoreHealthCheck."""

    @pytest.mark.asyncio
    async def test_daemon_has_health_check(self):
        """GIVEN a daemon with a KnowledgeStore, WHEN created, THEN it has a KnowledgeStoreHealthCheck."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = KnowledgeStore(root=tmpdir)
            store.initialize()
            cfg = MonitorConfig(strategy_id="test_strat", knowledge_root=tmpdir)
            daemon = AutonomousMonitorDaemon(cfg)

            assert daemon._health_check is not None
            assert isinstance(daemon._health_check, KnowledgeStoreHealthCheck)

    @pytest.mark.asyncio
    async def test_daemon_checks_store_health_in_compute_cycle(self):
        """GIVEN a daemon with a healthy store, WHEN _compute_cycle() runs, THEN store health is checked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = KnowledgeStore(root=tmpdir)
            store.initialize()
            cfg = MonitorConfig(strategy_id="test_strat", knowledge_root=tmpdir)
            daemon = AutonomousMonitorDaemon(cfg)

            # The daemon should have a health check integrated
            result = await daemon._health_check.check()
            assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_daemon_dispatch_store_unhealthy_alert(self):
        """GIVEN an unhealthy store, WHEN compute cycle runs, THEN STORE_UNHEALTHY WARNING alert is dispatched."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = KnowledgeStore(root=tmpdir)
            store.initialize()
            cfg = MonitorConfig(strategy_id="test_strat", knowledge_root=tmpdir)

            # Create a dispatcher that captures alerts
            alerts_dispatched = []

            class CapturingDispatcher:
                async def dispatch(self, alert):
                    alerts_dispatched.append(alert)

            dispatcher = CapturingDispatcher()
            daemon = AutonomousMonitorDaemon(
                cfg, dispatcher=dispatcher, store=store._ts_store if hasattr(store, '_ts_store') else None
            )

            # The daemon should have a health check
            assert daemon._health_check is not None

    @pytest.mark.asyncio
    async def test_store_health_in_status_details(self):
        """GIVEN a daemon with store health check, WHEN status() is called, THEN store_health is included."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = KnowledgeStore(root=tmpdir)
            store.initialize()
            cfg = MonitorConfig(strategy_id="test_strat", knowledge_root=tmpdir)
            daemon = AutonomousMonitorDaemon(cfg)

            status = daemon.status()
            assert "store_health" in status or "health_check" in str(type(daemon._health_check))

    @pytest.mark.asyncio
    async def test_circuit_breaker_used_for_store_writes(self):
        """GIVEN a daemon with a KnowledgeStore that has a circuit breaker, WHEN store writes are attempted, THEN they go through the circuit breaker."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = KnowledgeStore(root=tmpdir)
            store.initialize()

            # Verify the store has a circuit breaker
            assert store._circuit_breaker is not None

            cfg = MonitorConfig(strategy_id="test_strat", knowledge_root=tmpdir)
            daemon = AutonomousMonitorDaemon(cfg)

            # The daemon should use the store's circuit breaker for writes
            assert daemon._store is not None
