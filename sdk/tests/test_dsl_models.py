"""Tests for DSL Pydantic models."""

import pytest
from pydantic import ValidationError as PydanticValidationError

from quantlab.dsl.models import (
    AcceptanceCriterion,
    BuildingBlock,
    EntryRule,
    ExitRule,
    IndicatorConfig,
    Market,
    ResearchConfig,
    Strategy,
    StrategyDirection,
    Timeframe,
)


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
        with pytest.raises(PydanticValidationError, match="Duplicate"):
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
        with pytest.raises(PydanticValidationError, match="unknown building block"):
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
