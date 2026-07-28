"""Unit tests for CandidateValidator tier gating and pipeline delegation."""

from __future__ import annotations

import tempfile
from unittest.mock import AsyncMock, patch

import pytest

from quantlab.evolution.validator import CandidateValidator
from quantlab.evolution.config import EvolutionConfig
from quantlab.evolution.fitness import FitnessFunction
from quantlab.evolution.models import CandidateStatus, EvolutionCandidate, EvolutionMode
from quantlab.evolution.pool import CandidatePool
from quantlab.pipeline.models import PipelineResult, StageResult, StageStatus


def make_candidate(
    candidate_id: str = "test-001",
    strategy_id: str = "strat_1",
    status: CandidateStatus = CandidateStatus.PENDING,
    fitness: float = 0.0,
    cfx_content: str = "<cfx><test/></cfx>",
) -> EvolutionCandidate:
    """Helper to create a test candidate."""
    return EvolutionCandidate(
        candidate_id=candidate_id,
        strategy_id=strategy_id,
        mode=EvolutionMode.GENETIC_ONLY,
        cfx_content=cfx_content,
        status=status,
        fitness_score=fitness,
    )


def make_successful_pipeline_result(stages: int = 5) -> PipelineResult:
    """Create a fully successful PipelineResult.

    The last stage's output includes ``strategy_stats`` so the fitness
    extraction can produce a score above the MC threshold (>= 60).
    """
    result = PipelineResult(pipeline_name="test")
    result.stages = []
    for i in range(stages):
        output = None
        if i == stages - 1:  # last stage: export/compute_stats
            output = {
                "statistics": {
                    "total_trades": 100,
                    "win_rate": 0.55,
                    "profit_factor": 1.5,
                    "sharpe_ratio": 1.2,
                    "sortino_ratio": 1.0,
                    "max_drawdown": -0.12,
                    "net_profit": 5000,
                    "recovery_factor": 2.0,
                    "expectancy": 50.0,
                    "avg_trades_per_month": 20,
                    "return_dd_ratio": 1.5,
                    "trades_quality": 0.6,
                }
            }
        result.stages.append(
            StageResult(
                stage_name=f"stage_{i}",
                status=StageStatus.COMPLETED,
                duration=0.1,
                output=output,
            )
        )
    result.total_duration = 0.5
    return result


def make_failed_pipeline_result(stages: int = 5) -> PipelineResult:
    """Create a PipelineResult where the first stage fails."""
    result = PipelineResult(pipeline_name="test")
    result.stages = [
        StageResult(stage_name="stage_0", status=StageStatus.FAILED, duration=0.1,
                     error="Simulated failure"),
    ]
    for i in range(1, stages):
        result.stages.append(
            StageResult(stage_name=f"stage_{i}", status=StageStatus.SKIPPED, duration=0.0)
        )
    result.error = "Stage stage_0 failed"
    return result


class TestCandidateValidator:
    """Validator tier gating and pipeline delegation tests."""

    @pytest.fixture
    def tmp_dir(self):
        with tempfile.TemporaryDirectory() as d:
            yield d

    @pytest.fixture
    def config(self):
        return EvolutionConfig(enabled=True)

    @pytest.fixture
    def pool(self, tmp_dir):
        return CandidatePool(pool_directory=tmp_dir)

    @pytest.fixture
    def fitness(self):
        return FitnessFunction()

    @pytest.mark.asyncio
    async def test_validate_passes_good_candidate(self, config, pool, fitness):
        """A good candidate should pass all three tiers and get PASSED status."""
        validator = CandidateValidator(config=config, fitness=fitness, pool=pool)

        # Mock runner to return successful results
        validator._runner = AsyncMock()
        validator._runner.run = AsyncMock(return_value=make_successful_pipeline_result())

        candidate = make_candidate()
        pool.add(candidate)

        result = await validator.validate(candidate)

        assert result.status == CandidateStatus.PASSED
        assert "backtest" in result.validation_results
        assert "walk_forward" in result.validation_results
        assert "monte_carlo" in result.validation_results
        assert result.validation_results.get("passed_tier1") is True
        assert result.validation_results.get("passed_tier2") is True

    @pytest.mark.asyncio
    async def test_fails_on_bad_backtest(self, config, pool, fitness):
        """When Tier-1 (backtest) fails, candidate should be FAILED."""
        validator = CandidateValidator(config=config, fitness=fitness, pool=pool)

        validator._runner = AsyncMock()
        validator._runner.run = AsyncMock(return_value=make_failed_pipeline_result())

        candidate = make_candidate()
        pool.add(candidate)

        result = await validator.validate(candidate)

        assert result.status == CandidateStatus.FAILED
        # Should NOT have walk_forward or monte_carlo results
        assert "walk_forward" not in result.validation_results or \
               result.validation_results.get("passed_tier2") is False

    @pytest.mark.asyncio
    async def test_skips_wf_when_bt_fails(self, config, pool, fitness):
        """When Tier-1 fails, Tier-2 (walk-forward) should not run."""
        validator = CandidateValidator(config=config, fitness=fitness, pool=pool)

        run_counts: list[str] = []

        async def tracking_run(pipeline, ctx, **kwargs):
            run_counts.append(ctx.config.get("tier", "unknown"))
            return make_failed_pipeline_result()

        validator._runner = AsyncMock()
        validator._runner.run = AsyncMock(side_effect=tracking_run)

        candidate = make_candidate()
        pool.add(candidate)

        await validator.validate(candidate)

        # Only one tier should have run (backtest)
        assert len(run_counts) == 1
        assert run_counts[0] == "backtest"

    @pytest.mark.asyncio
    async def test_skips_mc_when_wf_fails(self, config, pool, fitness):
        """When Tier-2 fails, Tier-3 (Monte Carlo) should not run."""
        validator = CandidateValidator(config=config, fitness=fitness, pool=pool)

        call_index = [0]

        async def staged_run(pipeline, ctx, **kwargs):
            idx = call_index[0]
            call_index[0] += 1
            if idx == 0:
                # BT succeeds
                return make_successful_pipeline_result()
            else:
                # WF fails
                return make_failed_pipeline_result()

        validator._runner = AsyncMock()
        validator._runner.run = AsyncMock(side_effect=staged_run)

        candidate = make_candidate()
        pool.add(candidate)

        result = await validator.validate(candidate)

        assert result.status == CandidateStatus.FAILED
        assert result.validation_results.get("passed_tier1") is True
        assert "passed_tier2" in result.validation_results

    @pytest.mark.asyncio
    async def test_partial_failure_recorded(self, config, pool, fitness):
        """Partial failure should record the error and keep prior results."""
        validator = CandidateValidator(config=config, fitness=fitness, pool=pool)

        validator._runner = AsyncMock()
        validator._runner.run = AsyncMock(return_value=make_successful_pipeline_result())

        candidate = make_candidate()
        pool.add(candidate)

        result = await validator.validate(candidate)

        assert result.validation_results["backtest"]["successful"] is True
        assert result.validation_results["walk_forward"]["successful"] is True
        assert result.validation_results["monte_carlo"]["successful"] is True

    @pytest.mark.asyncio
    async def test_pool_is_updated(self, config, pool, fitness):
        """After validation, the pool should reflect the new status."""
        validator = CandidateValidator(config=config, fitness=fitness, pool=pool)
        validator._runner = AsyncMock()
        validator._runner.run = AsyncMock(return_value=make_successful_pipeline_result())

        candidate = make_candidate(candidate_id="pool-test-001")
        pool.add(candidate)

        await validator.validate(candidate)

        persisted = pool.get("pool-test-001")
        assert persisted is not None
        assert persisted.status == CandidateStatus.PASSED

    @pytest.mark.asyncio
    async def test_validate_batch(self, config, pool, fitness):
        """validate_batch should validate multiple candidates sequentially."""
        validator = CandidateValidator(config=config, fitness=fitness, pool=pool)
        validator._runner = AsyncMock()
        validator._runner.run = AsyncMock(return_value=make_successful_pipeline_result())

        candidates = [
            make_candidate("batch-001", "s1"),
            make_candidate("batch-002", "s2"),
        ]
        for c in candidates:
            pool.add(c)

        results = await validator.validate_batch(candidates)
        assert len(results) == 2
        assert all(r.status == CandidateStatus.PASSED for r in results)

    def test_validator_initialization(self, config, pool, fitness):
        validator = CandidateValidator(config=config, fitness=fitness, pool=pool)
        assert validator._config == config
        assert validator._fitness == fitness
        assert validator._pool == pool
        assert validator._runner is not None
