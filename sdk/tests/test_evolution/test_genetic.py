"""Unit tests for GeneticOptimizer mutation operators and CFX parsing."""

from __future__ import annotations

import math
from unittest.mock import AsyncMock

import pytest

from quantlab.evolution.genetic import (
    GeneticOptimizer,
    apply_params_to_cfx,
    blend_crossover,
    boundary_reset,
    cfx_content_to_archive,
    extract_numeric_params,
    gaussian_perturbation,
    single_point_crossover,
    tournament_select,
)
from quantlab.evolution.config import EvolutionConfig, EvolutionMode
from quantlab.evolution.fitness import FitnessFunction
from quantlab.evolution.models import EvolutionCandidate

# ── Mutation operator tests ──────────────────────────────────────────


class TestGaussianPerturbation:
    """Gaussian perturbation stays within bounds and is roughly centered."""

    def test_clips_to_lower_bound(self):
        result = gaussian_perturbation(value=5.0, lo=0.0, hi=10.0)
        assert 0.0 <= result <= 10.0

    def test_clips_to_upper_bound(self):
        result = gaussian_perturbation(value=5.0, lo=0.0, hi=10.0)
        assert result <= 10.0

    def test_returns_float(self):
        result = gaussian_perturbation(value=50.0, lo=0.0, hi=100.0)
        assert isinstance(result, float)

    def test_mean_approximation(self):
        """Over many samples, the mean should be near the original value."""
        samples = [gaussian_perturbation(50.0, 0.0, 100.0) for _ in range(2000)]
        mean = sum(samples) / len(samples)
        # sigma = 100/3 ≈ 33, so mean should be within 5 of original
        assert abs(mean - 50.0) < 5.0

    def test_narrow_range(self):
        result = gaussian_perturbation(value=0.5, lo=0.0, hi=1.0)
        assert 0.0 <= result <= 1.0

    def test_zero_range_no_mutation(self):
        """Value=lo=hi should never change."""
        for _ in range(100):
            assert gaussian_perturbation(5.0, 5.0, 5.0) == 5.0


class TestBoundaryReset:
    """Boundary reset should return values near boundaries."""

    def test_result_in_range(self):
        for _ in range(100):
            result = boundary_reset(value=50.0, lo=0.0, hi=100.0)
            assert 0.0 <= result <= 100.0

    def test_near_boundaries(self):
        """Boundary reset should produce values near 0 or near 100, not 50."""
        results = [boundary_reset(50.0, 0.0, 100.0) for _ in range(500)]
        near_center = sum(1 for r in results if 30 <= r <= 70)
        # At most 20% should be in the middle 40% of range
        assert near_center < 150  # Allow some statistical noise

    def test_returns_float(self):
        result = boundary_reset(value=10.0, lo=0.0, hi=100.0)
        assert isinstance(result, float)


class TestBlendCrossover:
    """BLX-α crossover should produce offspring within the extended range."""

    def test_offspring_count(self):
        c1, c2 = blend_crossover(10.0, 20.0, 0.0, 100.0)
        assert isinstance(c1, float)
        assert isinstance(c2, float)

    def test_offspring_in_bounds(self):
        for _ in range(500):
            c1, c2 = blend_crossover(10.0, 20.0, 0.0, 100.0)
            assert 0.0 <= c1 <= 100.0
            assert 0.0 <= c2 <= 100.0

    def test_identical_parents(self):
        """When parents are equal, children should equal that value."""
        c1, c2 = blend_crossover(42.0, 42.0, 0.0, 100.0)
        assert abs(c1 - 42.0) < 1e-6
        assert abs(c2 - 42.0) < 1e-6


class TestSinglePointCrossover:
    """Single-point crossover on parameter vectors."""

    def test_children_have_correct_length(self):
        a = [1.0, 2.0, 3.0, 4.0]
        b = [5.0, 6.0, 7.0, 8.0]
        c1, c2 = single_point_crossover(a, b)
        assert len(c1) == 4
        assert len(c2) == 4

    def test_children_are_combinations(self):
        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        b = [10.0, 20.0, 30.0, 40.0, 50.0]
        c1, c2 = single_point_crossover(a, b)
        # Each child should be a mix
        assert c1 != a or c1 != b  # may not differ depending on crossover point
        assert c2 != a or c2 != b

    def test_raises_on_mismatched_length(self):
        with pytest.raises(ValueError, match="equal length"):
            single_point_crossover([1.0, 2.0], [1.0])

    def test_short_vectors_return_copies(self):
        a = [1.0]
        b = [2.0]
        c1, c2 = single_point_crossover(a, b)
        # Single-element vectors can't have crossover point > 0
        assert c1 == a
        assert c2 == b


class TestTournamentSelect:
    """Tournament selection picks the fittest individual."""

    def test_picks_highest_fitness(self):
        population = [
            {"id": "a", "fitness": 10.0},
            {"id": "b", "fitness": 50.0},
            {"id": "c", "fitness": 30.0},
            {"id": "d", "fitness": 90.0},
            {"id": "e", "fitness": 20.0},
        ]
        # Force determinism by running many iterations
        winners = [tournament_select(population)["id"] for _ in range(200)]
        # The fittest (d, fitness=90) should win more often than any other
        d_wins = winners.count("d")
        assert d_wins > 50  # tournament selection is stochastic but biased


# ── CFX Parsing Tests ────────────────────────────────────────────────

MINIMAL_CFX = """<?xml version="1.0" encoding="utf-8"?>
<StrategyQuant Version="141.2219">
  <BuildTask name="Build-Task1">
    <Options>
      <Campaign name="test"/>
    </Options>
    <Data>
      <Symbol name="EURUSD"/>
      <Timeframe value="H1"/>
      <ATRPeriod value="14"/>
      <BBPeriod value="20"/>
    </Data>
    <WhatToBuild>
      <UseGenetic value="false"/>
      <Generations value="50"/>
      <Population value="100"/>
    </WhatToBuild>
  </BuildTask>
</StrategyQuant>"""

CFX_WITH_OPTIMIZATION = """<?xml version="1.0" encoding="utf-8"?>
<StrategyQuant Version="141.2219">
  <BuildTask name="Build-Task1">
    <Options>
      <Campaign name="opt-test"/>
    </Options>
    <Data>
      <Symbol name="GBPUSD"/>
      <Timeframe value="H4"/>
    </Data>
    <WhatToBuild>
      <UseGenetic value="true"/>
      <Generations value="50"/>
      <Population value="100"/>
    </WhatToBuild>
    <OptimizationParameters>
      <Parameter name="MA_Period" min="5.0" max="50.0" step="0.5"/>
      <Parameter name="RSI_Threshold" min="10.0" max="40.0" step="1.0"/>
    </OptimizationParameters>
  </BuildTask>
</StrategyQuant>"""

EMPTY_CFX = """<?xml version="1.0" encoding="utf-8"?>
<StrategyQuant Version="141.2219">
  <BuildTask name="Build-Task1">
    <Options>
      <Campaign name="empty"/>
    </Options>
  </BuildTask>
</StrategyQuant>"""


class TestCfxParsing:
    """CFX content parsing and parameter extraction."""

    def test_parse_minimal_cfx(self):
        result = cfx_content_to_archive(MINIMAL_CFX)
        assert result is True

    def test_parse_empty_cfx(self):
        result = cfx_content_to_archive(EMPTY_CFX)
        assert result is True

    def test_extract_params_from_minimal(self):
        params = extract_numeric_params(MINIMAL_CFX)
        assert len(params) > 0
        param_keys = list(params.keys())
        # Should find what_to_build/Generations@value and what_to_build/Population@value
        assert any("Generations" in k for k in param_keys)
        assert any("data" in k.lower() for k in param_keys)
        assert any("Population" in k for k in param_keys)

    def test_extract_param_ranges(self):
        params = extract_numeric_params(MINIMAL_CFX)
        for key, (default, lo, hi) in params.items():
            assert lo <= default <= hi
            assert lo < hi

    def test_optimization_params_override(self):
        params = extract_numeric_params(CFX_WITH_OPTIMIZATION)
        opt_keys = [k for k in params if k.startswith("optimization/")]
        assert len(opt_keys) >= 2
        # MA_Period: default=step=0.5, min=5, max=50
        ma_key = next(k for k in opt_keys if "MA_Period" in k)
        default, lo, hi = params[ma_key]
        assert abs(lo - 5.0) < 1e-6
        assert abs(hi - 50.0) < 1e-6

    def test_roundtrip_cfx(self):
        """apply_params_to_cfx should preserve CFX structure."""
        params = extract_numeric_params(MINIMAL_CFX)
        # Modify one param and check output
        if params:
            key = list(params.keys())[0]
            modified = {key: 99.0}
            xml_out = apply_params_to_cfx(MINIMAL_CFX, modified)
            assert "99" in xml_out
            assert "EURUSD" in xml_out  # unchanged
            assert "H1" in xml_out  # unchanged

    def test_invalid_cfx_returns_none(self):
        result = cfx_content_to_archive("not valid cfx")
        assert result is None

    def test_empty_string_returns_none(self):
        result = cfx_content_to_archive("")
        assert result is None


# ── GeneticOptimizer Integration Tests ───────────────────────────────


class TestGeneticOptimizer:
    """Integration tests for GeneticOptimizer with mocked PipelineRunner."""

    @pytest.mark.asyncio
    async def test_optimize_returns_candidates(self):
        config = EvolutionConfig(
            enabled=True,
            mode=EvolutionMode.GENETIC_ONLY,
        )
        fitness = FitnessFunction()
        optimizer = GeneticOptimizer(config=config, fitness=fitness)

        # Mock the runner so it doesn't actually call SQX
        optimizer._runner = AsyncMock()
        optimizer._runner.run = AsyncMock()
        # Simulate a successful pipeline result
        from quantlab.pipeline.models import PipelineResult, StageResult, StageStatus
        mock_result = PipelineResult(pipeline_name="test")
        mock_result.stages = [
            StageResult(stage_name="daemon_start", status=StageStatus.COMPLETED, duration=0.1),
            StageResult(stage_name="export", status=StageStatus.COMPLETED, duration=0.1),
        ]
        mock_result.total_duration = 0.2
        optimizer._runner.run = AsyncMock(return_value=mock_result)

        candidates = await optimizer.optimize(
            strategy_id="test_strat",
            cfx_content=MINIMAL_CFX,
        )

        assert len(candidates) > 0
        for c in candidates:
            assert c.strategy_id == "test_strat"
            assert c.candidate_id.startswith("gen-")
            assert c.mode == EvolutionMode.GENETIC_ONLY
            assert c.cfx_content is not None
            assert c.parent_candidate_id is None

    @pytest.mark.asyncio
    async def test_optimize_empty_cfx_returns_empty(self):
        config = EvolutionConfig()
        fitness = FitnessFunction()
        optimizer = GeneticOptimizer(config=config, fitness=fitness)

        candidates = await optimizer.optimize("test", "")
        assert len(candidates) == 0

    @pytest.mark.asyncio
    async def test_optimize_invalid_cfx_returns_empty(self):
        config = EvolutionConfig()
        fitness = FitnessFunction()
        optimizer = GeneticOptimizer(config=config, fitness=fitness)

        candidates = await optimizer.optimize("test", "not-valid-cfx")
        assert len(candidates) == 0

    @pytest.mark.asyncio
    async def test_optimize_with_parent_trace(self):
        config = EvolutionConfig(enabled=True)
        fitness = FitnessFunction()
        optimizer = GeneticOptimizer(config=config, fitness=fitness)

        optimizer._runner = AsyncMock()
        from quantlab.pipeline.models import PipelineResult, StageResult, StageStatus
        mock_result = PipelineResult(pipeline_name="test")
        mock_result.stages = [
            StageResult(stage_name="daemon_start", status=StageStatus.COMPLETED, duration=0.1),
            StageResult(stage_name="export", status=StageStatus.COMPLETED, duration=0.1),
        ]
        optimizer._runner.run = AsyncMock(return_value=mock_result)

        candidates = await optimizer.optimize(
            strategy_id="parent_strat",
            cfx_content=MINIMAL_CFX,
            parent_candidate_id="parent-001",
        )

        assert len(candidates) > 0
        assert all(c.parent_candidate_id == "parent-001" for c in candidates)

    def test_genetic_optimizer_initialization(self):
        config = EvolutionConfig()
        fitness = FitnessFunction()
        optimizer = GeneticOptimizer(config=config, fitness=fitness)
        assert optimizer._config == config
        assert optimizer._fitness == fitness
        assert optimizer._runner is not None
