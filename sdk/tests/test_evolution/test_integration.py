"""Integration tests for the Strategic Evolution Engine.

Tests the end-to-end flow through the EvolutionOrchestrator with mocked
component boundaries, verifying correct dispatch, pool persistence,
concurrency enforcement, and mode selection.

Task 4.6 — Full validation pipeline integration:
    Mock PipelineRunner stages, test orchestrator process_signals flow
    end-to-end with mocked genetic/novelty/validator, verify CandidatePool
    persistence after a cycle.

Task 4.7 — NoveltyGenerator integration:
    Verify orchestrator dispatches to NoveltyGenerator at the interface
    level with correct context, and candidates flow through to the pool.
"""

from __future__ import annotations

import tempfile
from unittest.mock import AsyncMock

import pytest
from pytest import approx
import pytest_asyncio

from quantlab.evolution.config import (
    ConcurrencyConfig,
    EvolutionConfig,
    EvolutionMode,
)
from quantlab.evolution.models import (
    CandidateStatus,
    EvolutionCandidate,
    EvolutionResult,
    EvolutionSignal,
)
from quantlab.evolution.orchestrator import EvolutionOrchestrator
from quantlab.evolution.pool import CandidatePool


# ── Helpers ──────────────────────────────────────────────────────────────────


def make_signal(
    strategy_id: str,
    priority: int = 50,
    mg_state: str = "DEGRADING",
) -> EvolutionSignal:
    """Create an EvolutionSignal for testing."""
    return EvolutionSignal(
        strategy_id=strategy_id,
        mg_state=mg_state,
        health_score=0.4,
        priority=priority,
    )


def make_candidate(
    candidate_id: str,
    strategy_id: str,
    mode: EvolutionMode,
) -> EvolutionCandidate:
    """Create a PASSED candidate above the promotion threshold for testing."""
    return EvolutionCandidate(
        candidate_id=candidate_id,
        strategy_id=strategy_id,
        mode=mode,
        status=CandidateStatus.PASSED,
        fitness_score=0.85,
    )


@pytest_asyncio.fixture
async def tmp_pool_dir() -> str:
    """Provide a temporary directory for pool isolation per test."""
    with tempfile.TemporaryDirectory() as tmp:
        yield tmp


# ── Task 4.6: Full Validation Pipeline Integration ──────────────────────────


@pytest.mark.asyncio
class TestValidationPipelineIntegration:
    """Integration tests for the full validation pipeline flow."""

    async def test_process_signals_persists_to_pool(self, tmp_pool_dir: str) -> None:
        """Signals → generation → pool persistence — end-to-end with mocks."""
        config = EvolutionConfig(
            enabled=True,
            pool_directory=tmp_pool_dir,
        )
        pool = CandidatePool(pool_directory=tmp_pool_dir)
        orch = EvolutionOrchestrator(config=config, pool=pool)

        # Mock both generators — use plain AsyncMock (no spec_set, which
        # breaks the async contract on Python 3.14)
        orch._genetic = AsyncMock()
        orch._genetic.optimize = AsyncMock(return_value=[
            make_candidate("gen-001", "strat_1", EvolutionMode.GENETIC_ONLY),
        ])
        orch._novelty = AsyncMock()
        orch._novelty.generate = AsyncMock(return_value=[
            make_candidate("novel-001", "strat_1", EvolutionMode.GENERATIVE_ONLY),
        ])

        results = await orch.process_signals([make_signal("strat_1", priority=60)])

        # Result shape
        assert len(results) == 1
        result = results[0]
        assert result.candidates_generated >= 1
        assert result.cycle_id.startswith("cycle-")
        assert len(result.errors) == 0

        # Pool persistence — both candidates should be in the pool
        loaded = pool.load_all()
        candidate_ids = {c.candidate_id for c in loaded}
        assert "gen-001" in candidate_ids
        assert "novel-001" in candidate_ids

    async def test_mode_genetic_only_skips_novelty(self, tmp_pool_dir: str) -> None:
        """GENETIC_ONLY dispatches only to GeneticOptimizer."""
        config = EvolutionConfig(
            enabled=True,
            mode=EvolutionMode.GENETIC_ONLY,
            pool_directory=tmp_pool_dir,
        )
        pool = CandidatePool(pool_directory=tmp_pool_dir)
        orch = EvolutionOrchestrator(config=config, pool=pool)

        orch._genetic = AsyncMock()
        orch._genetic.optimize = AsyncMock(return_value=[
            make_candidate("gen-only-001", "strat_2", EvolutionMode.GENETIC_ONLY),
        ])
        orch._novelty = AsyncMock()
        orch._novelty.generate = AsyncMock()

        results = await orch.process_signals([make_signal("strat_2")])

        assert len(results) == 1
        orch._genetic.optimize.assert_called_once()
        orch._novelty.generate.assert_not_called()

        loaded = pool.load_all()
        assert any(c.candidate_id == "gen-only-001" for c in loaded)

    async def test_mode_generative_only_skips_genetic(self, tmp_pool_dir: str) -> None:
        """GENERATIVE_ONLY dispatches only to NoveltyGenerator."""
        config = EvolutionConfig(
            enabled=True,
            mode=EvolutionMode.GENERATIVE_ONLY,
            pool_directory=tmp_pool_dir,
        )
        pool = CandidatePool(pool_directory=tmp_pool_dir)
        orch = EvolutionOrchestrator(config=config, pool=pool)

        orch._genetic = AsyncMock()
        orch._genetic.optimize = AsyncMock()
        orch._novelty = AsyncMock()
        orch._novelty.generate = AsyncMock(return_value=[
            make_candidate("novel-only-001", "strat_3", EvolutionMode.GENERATIVE_ONLY),
        ])

        results = await orch.process_signals([make_signal("strat_3")])

        assert len(results) == 1
        orch._novelty.generate.assert_called_once()
        orch._genetic.optimize.assert_not_called()

        loaded = pool.load_all()
        assert any(c.candidate_id == "novel-only-001" for c in loaded)

    async def test_concurrency_limit_enforced(self, tmp_pool_dir: str) -> None:
        """When active_cycles reaches max_concurrent, new signals are deferred."""
        config = EvolutionConfig(
            enabled=True,
            concurrency=ConcurrencyConfig(max_concurrent_evolutions=2),
            pool_directory=tmp_pool_dir,
        )
        pool = CandidatePool(pool_directory=tmp_pool_dir)
        orch = EvolutionOrchestrator(config=config, pool=pool)

        orch._genetic = AsyncMock()
        orch._genetic.optimize = AsyncMock(return_value=[])
        orch._novelty = AsyncMock()
        orch._novelty.generate = AsyncMock(return_value=[])

        # Pre-fill _active_cycles to simulate already-running operations
        orch._active_cycles["existing-1"] = EvolutionResult(
            cycle_id="existing-1", mode=EvolutionMode.GENETIC_ONLY,
        )
        orch._active_cycles["existing-2"] = EvolutionResult(
            cycle_id="existing-2", mode=EvolutionMode.GENETIC_ONLY,
        )

        # With 2 already active and max=2, no new signals should be processed
        signals = [
            make_signal("a", priority=100),
            make_signal("b", priority=80),
            make_signal("c", priority=60),
        ]
        results = await orch.process_signals(signals)

        assert len(results) == 0

    async def test_priority_sorting(self, tmp_pool_dir: str) -> None:
        """Higher-priority signals are processed before lower-priority ones."""
        config = EvolutionConfig(
            enabled=True,
            pool_directory=tmp_pool_dir,
        )
        pool = CandidatePool(pool_directory=tmp_pool_dir)
        orch = EvolutionOrchestrator(config=config, pool=pool)

        # Track processing order via side_effect
        processed_strategies: list[str] = []

        async def track_optimize(strategy_id: str, cfx_content: str) -> list:
            processed_strategies.append(strategy_id)
            return []

        orch._genetic = AsyncMock()
        orch._genetic.optimize = AsyncMock(side_effect=track_optimize)
        orch._novelty = AsyncMock()
        orch._novelty.generate = AsyncMock(return_value=[])

        signals = [
            make_signal("low", priority=10),
            make_signal("high", priority=100),
            make_signal("medium", priority=50),
        ]
        results = await orch.process_signals(signals)

        assert len(results) == 3
        # The orchestrator sorts descending by priority before processing
        assert processed_strategies[0] == "high"
        assert processed_strategies[1] == "medium"
        assert processed_strategies[2] == "low"

    async def test_disabled_mode_ignores_signals(self, tmp_pool_dir: str) -> None:
        """When disabled, process_signals returns empty and pool unchanged."""
        config = EvolutionConfig(
            enabled=False,
            pool_directory=tmp_pool_dir,
        )
        pool = CandidatePool(pool_directory=tmp_pool_dir)
        orch = EvolutionOrchestrator(config=config, pool=pool)

        orch._genetic = AsyncMock()
        orch._genetic.optimize = AsyncMock()
        orch._novelty = AsyncMock()
        orch._novelty.generate = AsyncMock()

        results = await orch.process_signals([make_signal("strat_x")])

        assert len(results) == 0
        orch._genetic.optimize.assert_not_called()
        orch._novelty.generate.assert_not_called()

        loaded = pool.load_all()
        assert len(loaded) == 0

    async def test_scheduled_cycle_with_generators(self, tmp_pool_dir: str) -> None:
        """Scheduled _run_cycle generates candidates and persists to pool."""
        config = EvolutionConfig(
            enabled=True,
            pool_directory=tmp_pool_dir,
        )
        pool = CandidatePool(pool_directory=tmp_pool_dir)
        orch = EvolutionOrchestrator(config=config, pool=pool)

        orch._genetic = AsyncMock()
        orch._genetic.optimize = AsyncMock(return_value=[
            make_candidate("sched-gen-001", "default", EvolutionMode.GENETIC_ONLY),
        ])
        orch._novelty = AsyncMock()
        orch._novelty.generate = AsyncMock(return_value=[
            make_candidate("sched-novel-001", "default", EvolutionMode.GENERATIVE_ONLY),
        ])

        result = await orch._run_cycle()

        assert result.cycle_id.startswith("cycle-")
        assert result.candidates_generated >= 2
        assert len(result.errors) == 0

        loaded = pool.load_all()
        ids = {c.candidate_id for c in loaded}
        assert "sched-gen-001" in ids
        assert "sched-novel-001" in ids


# ── Task 4.7: NoveltyGenerator Integration ───────────────────────────────────


@pytest.mark.asyncio
class TestNoveltyGeneratorIntegration:
    """Integration tests for NoveltyGenerator dispatch at interface level."""

    async def test_novelty_called_with_signal_context(self, tmp_pool_dir: str) -> None:
        """Orchestrator calls NoveltyGenerator with signal data in context."""
        config = EvolutionConfig(
            enabled=True,
            mode=EvolutionMode.GENERATIVE_ONLY,
            pool_directory=tmp_pool_dir,
        )
        pool = CandidatePool(pool_directory=tmp_pool_dir)
        orch = EvolutionOrchestrator(config=config, pool=pool)

        orch._novelty = AsyncMock()
        orch._novelty.generate = AsyncMock(return_value=[
            make_candidate("int-novel-001", "strat_sig", EvolutionMode.GENERATIVE_ONLY),
        ])

        results = await orch.process_signals([make_signal("strat_sig", priority=60)])

        # Verify orchestrator passed context with signal data
        orch._novelty.generate.assert_called_once()
        call_kwargs = orch._novelty.generate.call_args.kwargs
        assert "context" in call_kwargs
        ctx = call_kwargs["context"]
        assert "signal" in ctx
        assert ctx["signal"]["strategy_id"] == "strat_sig"

        # Candidates flow through to result
        assert len(results) == 1
        assert results[0].candidates_generated >= 1

        # Pool persistence
        loaded = pool.load_all()
        assert any(c.candidate_id == "int-novel-001" for c in loaded)

    async def test_both_generators_in_full_mode(self, tmp_pool_dir: str) -> None:
        """In FULL mode, both NoveltyGenerator and GeneticOptimizer are called."""
        config = EvolutionConfig(
            enabled=True,
            mode=EvolutionMode.FULL,
            pool_directory=tmp_pool_dir,
        )
        pool = CandidatePool(pool_directory=tmp_pool_dir)
        orch = EvolutionOrchestrator(config=config, pool=pool)

        orch._genetic = AsyncMock()
        orch._genetic.optimize = AsyncMock(return_value=[
            make_candidate("full-gen-001", "strat_full", EvolutionMode.GENETIC_ONLY),
        ])
        orch._novelty = AsyncMock()
        orch._novelty.generate = AsyncMock(return_value=[
            make_candidate("full-novel-001", "strat_full", EvolutionMode.GENERATIVE_ONLY),
        ])

        results = await orch.process_signals([make_signal("strat_full")])

        orch._genetic.optimize.assert_called_once()
        orch._novelty.generate.assert_called_once()

        # Both candidates in pool
        loaded = pool.load_all()
        ids = {c.candidate_id for c in loaded}
        assert "full-gen-001" in ids
        assert "full-novel-001" in ids

        assert len(results) == 1
        assert results[0].candidates_generated >= 2

    async def test_novelty_empty_result_graceful(self, tmp_pool_dir: str) -> None:
        """Empty list from NoveltyGenerator is handled without error."""
        config = EvolutionConfig(
            enabled=True,
            mode=EvolutionMode.GENERATIVE_ONLY,
            pool_directory=tmp_pool_dir,
        )
        pool = CandidatePool(pool_directory=tmp_pool_dir)
        orch = EvolutionOrchestrator(config=config, pool=pool)

        orch._novelty = AsyncMock()
        orch._novelty.generate = AsyncMock(return_value=[])

        results = await orch.process_signals([make_signal("strat_empty")])

        assert len(results) == 1
        assert results[0].candidates_generated == 0
        assert len(pool.load_all()) == 0

    async def test_novelty_disabled_early_return(self, tmp_pool_dir: str) -> None:
        """When orchestrator is disabled, NoveltyGenerator is never called."""
        config = EvolutionConfig(
            enabled=False,
            pool_directory=tmp_pool_dir,
        )
        pool = CandidatePool(pool_directory=tmp_pool_dir)
        orch = EvolutionOrchestrator(config=config, pool=pool)

        orch._novelty = AsyncMock()
        orch._novelty.generate = AsyncMock()

        results = await orch.process_signals([make_signal("strat_disable")])

        assert len(results) == 0
        orch._novelty.generate.assert_not_called()
        assert len(pool.load_all()) == 0
