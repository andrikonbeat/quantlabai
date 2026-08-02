"""Tests for DSL Pydantic models."""

import dataclasses

import pytest
import yaml

from quantlab.tools.exceptions import ValidationError

from quantlab.dsl.models import (
    AcceptanceCriterion,
    BuildingBlock,
    EntryRule,
    ExitRule,
    IndicatorConfig,
    Market,
    OptimizeBlock,
    ResearchConfig,
    RetestBlock,
    Strategy,
    StrategyDirection,
    Timeframe,
)
from quantlab.dsl.parser import parse_yaml_string, serialize
from quantlab.sqx.project_builder import BuildConfig


class TestMarket:
    def test_recognised_markets(self) -> None:
        assert Market("EURUSD").value == "EURUSD"
        assert Market("BTCUSD").value == "BTCUSD"

    def test_unknown_market_raises(self) -> None:
        with pytest.raises(ValueError):
            Market("INVALID")


class TestTimeframe:
    def test_recognised_timeframes(self) -> None:
        assert Timeframe("H1").value == "H1"
        assert Timeframe("D1").value == "D1"


class TestResearchConfig:
    def test_minimal_config(self) -> None:
        config = ResearchConfig(
            campaign="Test",
            market="EURUSD",
            timeframe="H1",
        )
        assert config.campaign == "Test"
        assert config.market == Market.EURUSD
        assert config.timeframe == Timeframe.H1
        assert config.strategies == []
        assert config.building_blocks == []

    def test_full_config(self) -> None:
        config = ResearchConfig(
            campaign="Full Test",
            market="BTCUSD",
            timeframe="D1",
            building_blocks=[
                BuildingBlock(
                    name="bb1",
                    indicator=IndicatorConfig(name="RSI", params={"period": 14}),
                    entry=EntryRule(
                        description="RSI oversold",
                        conditions=["rsi < 30"],
                    ),
                    exit=ExitRule(
                        description="RSI overbought",
                        conditions=["rsi > 70"],
                    ),
                ),
            ],
            strategies=[
                Strategy(
                    name="StratA",
                    direction="LONG",
                    building_blocks=["bb1"],
                ),
            ],
            criteria=[
                AcceptanceCriterion(metric="profit_factor", operator=">=", value=1.5),
            ],
        )
        assert len(config.strategies) == 1
        assert config.strategies[0].name == "StratA"
        assert config.criteria[0].value == 1.5

    def test_duplicate_strategy_names_raises(self) -> None:
        with pytest.raises(ValidationError, match="Duplicate"):
            ResearchConfig(
                campaign="Dups",
                market="EURUSD",
                timeframe="H1",
                strategies=[
                    Strategy(name="StratA", direction="LONG"),
                    Strategy(name="StratA", direction="SHORT"),
                ],
            )

    def test_unknown_building_block_ref_raises(self) -> None:
        with pytest.raises(ValidationError, match="unknown building block"):
            ResearchConfig(
                campaign="Missing",
                market="EURUSD",
                timeframe="H1",
                strategies=[
                    Strategy(name="S1", building_blocks=["nonexistent"]),
                ],
            )

    def test_model_dump_round_trip(self) -> None:
        config = ResearchConfig(
            campaign="RoundTrip",
            market="GBPUSD",
            timeframe="M15",
        )
        dumped = config.model_dump(mode="python")
        restored = ResearchConfig.model_validate(dumped)
        assert restored.campaign == config.campaign
        assert restored.market == config.market
        assert restored.timeframe == config.timeframe


class TestStrategyDirection:
    def test_default_is_both(self) -> None:
        strat = Strategy(name="DefaultDir")
        assert strat.direction == StrategyDirection.BOTH


class TestBuildConfigBlocks:
    """REQ-18: BuildConfig block-constraint fields with YAML round-trip."""

    def test_defaults_are_none(self) -> None:
        bc = BuildConfig()
        assert bc.enabled_blocks is None
        assert bc.block_weights is None

    def test_yaml_round_trip_with_blocks(self) -> None:
        bc = BuildConfig(
            enabled_blocks=["bb1", "bb2"],
            block_weights={"bb1": 1.0, "bb2": 2.0},
        )
        dumped = yaml.safe_dump(dataclasses.asdict(bc))
        restored = BuildConfig(**yaml.safe_load(dumped))
        assert restored.enabled_blocks == ["bb1", "bb2"]
        assert restored.block_weights == {"bb1": 1.0, "bb2": 2.0}

    def test_yaml_round_trip_without_blocks(self) -> None:
        bc = BuildConfig(population=100, generations=50)
        dumped = yaml.safe_dump(dataclasses.asdict(bc))
        restored = BuildConfig(**yaml.safe_load(dumped))
        assert restored.population == 100
        assert restored.generations == 50
        assert restored.enabled_blocks is None
        assert restored.block_weights is None


class TestResearchConfigRetestOptimize:
    """REQ-19: optional retest/optimize blocks on ResearchConfig."""

    def test_absent_blocks_default_to_none(self) -> None:
        config = ResearchConfig(
            campaign="NoBlocks",
            market="EURUSD",
            timeframe="H1",
        )
        assert config.retest is None
        assert config.optimize is None

    def test_retest_present_optimize_absent(self) -> None:
        config = ResearchConfig(
            campaign="RetestOnly",
            market="EURUSD",
            timeframe="H1",
            retest=RetestBlock(
                strategy_id="S1",
                databanks=["EURUSD_M1_dukas"],
            ),
        )
        assert config.retest is not None
        assert config.retest.strategy_id == "S1"
        assert config.retest.databanks == ["EURUSD_M1_dukas"]
        assert config.optimize is None

    def test_optimize_present_retest_absent(self) -> None:
        config = ResearchConfig(
            campaign="OptimizeOnly",
            market="EURUSD",
            timeframe="H1",
            optimize=OptimizeBlock(strategy_id="S1"),
        )
        assert config.optimize is not None
        assert config.optimize.strategy_id == "S1"
        assert config.retest is None

    def test_retest_mirrors_retester_config_with_max_iterations(self) -> None:
        block = RetestBlock(
            strategy_id="S1",
            databanks=["EURUSD_M1_dukas"],
            monte_carlo_runs=250,
            mc_percentile=90,
            walkforward_cycles=3,
            min_trades=50,
            confidence_level=0.90,
            max_iterations=7,
        )
        assert block.monte_carlo_runs == 250
        assert block.mc_percentile == 90
        assert block.walkforward_cycles == 3
        assert block.min_trades == 50
        assert block.confidence_level == 0.90
        assert block.max_iterations == 7

    def test_retest_defaults_match_retester_config(self) -> None:
        block = RetestBlock(strategy_id="S1", databanks=["EURUSD_M1_dukas"])
        assert block.monte_carlo_runs == 100
        assert block.mc_percentile == 95
        assert block.walkforward_cycles == 5
        assert block.min_trades == 30
        assert block.confidence_level == 0.95
        assert block.max_iterations is None

    def test_optimize_mirrors_optimizer_config(self) -> None:
        block = OptimizeBlock(
            strategy_id="S1",
            method="Genetic",
            objective="SharpeRatio",
            walkforward_cycles=8,
            population=150,
            generations=60,
            crossover=0.9,
            mutation=0.05,
            databanks=["EURUSD_M1_dukas"],
        )
        assert block.method == "Genetic"
        assert block.objective == "SharpeRatio"
        assert block.walkforward_cycles == 8
        assert block.population == 150
        assert block.generations == 60
        assert block.crossover == 0.9
        assert block.mutation == 0.05
        assert block.databanks == ["EURUSD_M1_dukas"]

    def test_yaml_round_trip_with_retest_optimize(self) -> None:
        original = ResearchConfig(
            campaign="RT",
            market="EURUSD",
            timeframe="H1",
            building_blocks=[
                BuildingBlock(
                    name="bb1",
                    indicator=IndicatorConfig(name="RSI", params={"period": 14}),
                ),
            ],
            retest=RetestBlock(strategy_id="S1", databanks=["EURUSD_M1_dukas"]),
            optimize=OptimizeBlock(strategy_id="S1"),
        )
        restored = parse_yaml_string(serialize(original))
        assert restored.building_blocks[0].name == "bb1"
        assert restored.retest is not None
        assert restored.retest.strategy_id == "S1"
        assert restored.retest.databanks == ["EURUSD_M1_dukas"]
        assert restored.optimize is not None
        assert restored.optimize.strategy_id == "S1"
        assert restored.optimize.method == "Genetic"
