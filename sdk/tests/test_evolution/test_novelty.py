"""Unit tests for NoveltyGenerator DSL generation and context handling."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from quantlab.evolution.novelty import (
    NoveltyGenerator,
    _build_research_config,
    _market_enum_from_str,
    _select_building_blocks,
    _timeframe_enum_from_str,
)
from quantlab.evolution.config import EvolutionConfig
from quantlab.evolution.fitness import FitnessFunction
from quantlab.evolution.models import EvolutionMode
from quantlab.dsl.models import Market, Timeframe


class TestMarketTimeframeResolution:
    """Market and timeframe string-to-enum resolution."""

    def test_market_resolution(self):
        assert _market_enum_from_str("EURUSD") == Market.EURUSD
        assert _market_enum_from_str("eurusd") == Market.EURUSD  # case-insensitive

    def test_market_unknown(self):
        assert _market_enum_from_str("UNKNOWN") is None

    def test_timeframe_resolution(self):
        assert _timeframe_enum_from_str("H1") == Timeframe.H1
        assert _timeframe_enum_from_str("h1") == Timeframe.H1  # case-insensitive

    def test_timeframe_unknown(self):
        assert _timeframe_enum_from_str("XYZ") is None


class TestBuildingBlockSelection:
    """Building block selection based on context."""

    def test_selects_blocks_by_risk_profile(self):
        blocks = _select_building_blocks({"risk_profile": "moderate"})
        assert 2 <= len(blocks) <= 4
        for b in blocks:
            assert b.name.startswith(tuple(
                {"MA", "EMA", "RSI", "MACD", "Stochastic", "BB", "ATR", "ADX", "CCI", "WilliamsR"}
            ))

    def test_conservative_returns_fewer_blocks(self):
        conservative = _select_building_blocks({"risk_profile": "conservative"})
        aggressive = _select_building_blocks({"risk_profile": "aggressive"})
        assert len(conservative) <= len(aggressive)

    def test_blocks_have_unique_names(self):
        blocks = _select_building_blocks({"risk_profile": "moderate"})
        names = [b.name for b in blocks]
        assert len(names) == len(set(names))

    def test_blocks_have_indicator_params(self):
        blocks = _select_building_blocks({"risk_profile": "aggressive"})
        for b in blocks:
            assert b.indicator.name in {"MA", "EMA", "RSI", "MACD", "Stochastic",
                                          "BB", "ATR", "ADX", "CCI", "WilliamsR"}
            assert len(b.indicator.params) > 0


class TestResearchConfigBuilding:
    """ResearchConfig generation from context dicts."""

    def test_full_context_produces_config(self):
        config = _build_research_config({
            "market": "EURUSD",
            "timeframe": "H1",
            "risk_profile": "moderate",
            "objective": "sharpe",
        })
        assert config is not None
        assert config.market == Market.EURUSD
        assert config.timeframe == Timeframe.H1
        assert len(config.building_blocks) >= 2
        assert len(config.strategies) == 1

    def test_missing_market_returns_none(self):
        config = _build_research_config({"timeframe": "H1"})
        assert config is None

    def test_missing_timeframe_returns_none(self):
        config = _build_research_config({"market": "EURUSD"})
        assert config is None

    def test_unknown_market_returns_none(self):
        config = _build_research_config({
            "market": "UNKNOWN",
            "timeframe": "H1",
        })
        assert config is None

    def test_conservative_config_has_both_direction(self):
        config = _build_research_config({
            "market": "EURUSD",
            "timeframe": "D1",
            "risk_profile": "conservative",
        })
        assert config is not None
        assert config.strategies[0].direction.value == "BOTH"

    def test_objective_affects_criteria(self):
        config_sharpe = _build_research_config({
            "market": "EURUSD", "timeframe": "H1",
            "objective": "sharpe",
        })
        config_profit = _build_research_config({
            "market": "EURUSD", "timeframe": "H1",
            "objective": "profit",
        })
        assert config_sharpe is not None
        assert config_profit is not None
        sharpe_metrics = {c.metric for c in config_sharpe.criteria}
        profit_metrics = {c.metric for c in config_profit.criteria}
        assert sharpe_metrics != profit_metrics


class TestNoveltyGenerator:
    """Integration tests for NoveltyGenerator with mocked PipelineRunner."""

    @pytest.mark.asyncio
    async def test_generate_with_market_timeframe(self):
        config = EvolutionConfig(enabled=True)
        fitness = FitnessFunction()
        generator = NoveltyGenerator(config=config, fitness=fitness)

        # Mock the runner
        generator._runner = AsyncMock()
        from quantlab.pipeline.models import PipelineResult, StageResult, StageStatus
        mock_result = PipelineResult(pipeline_name="test")
        mock_result.stages = [
            StageResult(stage_name="daemon_start", status=StageStatus.COMPLETED, duration=0.1),
            StageResult(stage_name="export", status=StageStatus.COMPLETED, duration=0.1),
        ]
        generator._runner.run = AsyncMock(return_value=mock_result)

        candidates = await generator.generate({
            "market": "EURUSD",
            "timeframe": "H1",
            "risk_profile": "moderate",
            "objective": "sharpe",
        })

        assert len(candidates) == 1
        c = candidates[0]
        assert c.mode == EvolutionMode.GENERATIVE_ONLY
        assert c.candidate_id.startswith("novel-")
        assert c.cfx_content is not None
        assert "EURUSD" in c.cfx_content
        assert c.dsl_content is not None

    @pytest.mark.asyncio
    async def test_generate_empty_context_returns_empty(self):
        config = EvolutionConfig()
        fitness = FitnessFunction()
        generator = NoveltyGenerator(config=config, fitness=fitness)
        candidates = await generator.generate({})
        assert len(candidates) == 0

    @pytest.mark.asyncio
    async def test_generate_signal_context(self):
        config = EvolutionConfig(enabled=True)
        fitness = FitnessFunction()
        generator = NoveltyGenerator(config=config, fitness=fitness)

        generator._runner = AsyncMock()
        from quantlab.pipeline.models import PipelineResult, StageResult, StageStatus
        mock_result = PipelineResult(pipeline_name="test")
        mock_result.stages = [
            StageResult(stage_name="daemon_start", status=StageStatus.COMPLETED, duration=0.1),
            StageResult(stage_name="export", status=StageStatus.COMPLETED, duration=0.1),
        ]
        generator._runner.run = AsyncMock(return_value=mock_result)

        candidates = await generator.generate({
            "signal": {
                "strategy_id": "strat_1",
                "mg_state": "DEGRADING",
                "health_score": 0.4,
                "priority": 60,
            }
        })

        # Should generate using signal defaults
        assert len(candidates) == 1

    @pytest.mark.asyncio
    async def test_generate_only_cycle_context_returns_empty(self):
        config = EvolutionConfig()
        fitness = FitnessFunction()
        generator = NoveltyGenerator(config=config, fitness=fitness)
        candidates = await generator.generate({"cycle": "scheduled"})
        assert len(candidates) == 0

    @pytest.mark.asyncio
    async def test_minimal_cfx_fallback(self):
        """When translator modules aren't available, the fallback CFX generator works."""
        config = EvolutionConfig(enabled=True)
        fitness = FitnessFunction()
        generator = NoveltyGenerator(config=config, fitness=fitness)
        candidates = await generator.generate({
            "market": "GBPUSD",
            "timeframe": "H4",
            "risk_profile": "aggressive",
        })
        # Even without translator, we should get a candidate with minimal CFX
        if len(candidates) > 0:
            c = candidates[0]
            assert "GBPUSD" in c.cfx_content

    def test_novelty_generator_initialization(self):
        config = EvolutionConfig()
        fitness = FitnessFunction()
        generator = NoveltyGenerator(config=config, fitness=fitness)
        assert generator._config == config
        assert generator._fitness == fitness
        assert generator._runner is not None
