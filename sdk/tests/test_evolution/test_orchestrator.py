"""Tests for EvolutionOrchestrator."""

import pytest

from quantlab.evolution.config import EvolutionConfig, EvolutionMode
from quantlab.evolution.models import EvolutionSignal
from quantlab.evolution.orchestrator import EvolutionOrchestrator


class TestEvolutionOrchestrator:
    def test_initialization(self):
        config = EvolutionConfig()
        orch = EvolutionOrchestrator(config=config)
        assert orch.enabled is False
        assert orch.active_cycle_count == 0

    def test_enabled_toggle(self):
        config = EvolutionConfig(enabled=True)
        orch = EvolutionOrchestrator(config=config)
        assert orch.enabled is True

    def test_disabled_mode(self):
        config = EvolutionConfig(enabled=True, mode=EvolutionMode.DISABLED)
        orch = EvolutionOrchestrator(config=config)
        assert orch.enabled is False

    def test_disabled_ignores_signals(self):
        config = EvolutionConfig(enabled=False)
        orch = EvolutionOrchestrator(config=config)
        signals = [
            EvolutionSignal(
                strategy_id="strat_1", mg_state="DEGRADING",
                health_score=0.4, priority=60
            )
        ]
        results = asyncio_run(orch.process_signals(signals))
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_enabled_accepts_signals(self):
        config = EvolutionConfig(enabled=True)
        orch = EvolutionOrchestrator(config=config)
        signals = [
            EvolutionSignal(
                strategy_id="strat_1", mg_state="DEGRADING",
                health_score=0.4, priority=60
            )
        ]
        results = await orch.process_signals(signals)
        assert len(results) == 1
        assert results[0].cycle_id.startswith("cycle-")

    @pytest.mark.asyncio
    async def test_signal_priority_sorting(self):
        config = EvolutionConfig(enabled=True)
        orch = EvolutionOrchestrator(config=config)
        signals = [
            EvolutionSignal(
                strategy_id="low", mg_state="MONITORING",
                health_score=0.8, priority=30
            ),
            EvolutionSignal(
                strategy_id="high", mg_state="RETIRED",
                health_score=0.2, priority=100
            ),
        ]
        results = await orch.process_signals(signals)
        # Should process both (concurrency allows 1 at a time but sequential)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_start_stop(self):
        config = EvolutionConfig(enabled=True)
        orch = EvolutionOrchestrator(config=config)
        await orch.start()
        assert orch._running is True
        await orch.stop()
        assert orch._running is False

    def test_pool_default_directory(self):
        config = EvolutionConfig()
        orch = EvolutionOrchestrator(config=config)
        assert orch.pool._pool_dir.name == ".evolution_pool"


def asyncio_run(coro):
    """Helper to run async tests in synchronous context."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)
