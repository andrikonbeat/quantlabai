"""Tests for HypothesisBuilder — PR 1: Rule Mode + PR 2: LLM Mode + Fallback.

Strict TDD: tests written before implementation (RED).
PR 1: RuleMode keyword mapping (RB-4), BuildingBlockValidator (RB-5),
      HypothesisBuilder facade dispatch.
PR 2: LLMMode prompt construction, JSON parse, fallback chain (RB-6).
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from quantlab.dsl.models import (
    BuildingBlock,
    EntryRule,
    ExitRule,
    HypothesisConfig,
    IndicatorConfig,
    LLMConfig,
    Strategy,
    StrategyDirection,
)
# These imports will fail initially (RED) — that's intentional TDD:
from quantlab.agents.hypothesis_builder.rule import RuleMode
from quantlab.agents.hypothesis_builder.validate import BuildingBlockValidator
from quantlab.agents.hypothesis_builder import HypothesisBuilder
from quantlab.agents.hypothesis_builder.llm import LLMMode


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def rule_mode() -> RuleMode:
    return RuleMode()


@pytest.fixture
def validator() -> BuildingBlockValidator:
    return BuildingBlockValidator()


# ── Task 1.1 / 1.4: Rule Mode Matching (RB-4) ─────────────────────────────────


class TestRuleMode:
    """RuleMode keyword -> BuildingBlock mapping (RB-4 table)."""

    # fmt: off
    @pytest.mark.parametrize("description,expected_indicators", [
        ("mean-reversion on EURUSD",            {"RSI", "BB"}),
        ("mean reversion strategy",             {"RSI", "BB"}),
        ("breakout with volume confirmation",   {"Donchian", "Volume"}),
        ("break out of resistance",             {"Donchian", "Volume"}),
        ("momentum trend-following strategy",   {"EMA", "MACD"}),
        ("trend following system",              {"EMA", "MACD"}),
        ("divergence detection on RSI",         {"RSI", "MACD"}),
        ("volume analysis for liquidity",       {"Volume"}),
        ("volatility breakout with ATR",        {"ATR"}),
        ("pullback entry after retracement",    {"EMA", "RSI"}),
        ("support and resistance levels",       {"BB", "RSI"}),
    ])
    # fmt: on
    def test_keyword_mapping(
        self,
        rule_mode: RuleMode,
        description: str,
        expected_indicators: set[str],
    ) -> None:
        """Each RB-4 keyword pattern produces the expected indicators."""
        hyp = HypothesisConfig(name="test", description=description)
        blocks, strategies = rule_mode.build(hyp)

        indicator_names = {b.indicator.name for b in blocks}
        for ind in expected_indicators:
            assert ind in indicator_names, (
                f"Expected indicator '{ind}' for '{description}', "
                f"got {indicator_names}"
            )

    def test_default_fallback_when_no_keyword_matches(
        self, rule_mode: RuleMode
    ) -> None:
        """When no keyword matches, return a default RSI block."""
        hyp = HypothesisConfig(
            name="test", description="custom strategy idea no keywords"
        )
        blocks, strategies = rule_mode.build(hyp)
        assert len(blocks) >= 1
        assert blocks[0].indicator.name == "RSI"

    def test_parameters_override_defaults(self, rule_mode: RuleMode) -> None:
        """Hypothesis parameters override default indicator params."""
        hyp = HypothesisConfig(
            name="test",
            description="mean-reversion custom params",
            parameters={
                "rsi_period": 7,
                "rsi_oversold": 25,
                "rsi_overbought": 75,
            },
        )
        blocks, _ = rule_mode.build(hyp)
        rsi_block = next(b for b in blocks if b.indicator.name == "RSI")
        assert rsi_block.indicator.params.get("period") == 7
        assert rsi_block.indicator.params.get("oversold") == 25
        assert rsi_block.indicator.params.get("overbought") == 75

    def test_strategy_references_all_building_blocks(
        self, rule_mode: RuleMode
    ) -> None:
        """The generated strategy references every building block by name."""
        hyp = HypothesisConfig(name="test", description="mean-reversion")
        blocks, strategies = rule_mode.build(hyp)
        assert len(strategies) >= 1
        strategy_block_names = set(strategies[0].building_blocks)
        all_block_names = {b.name for b in blocks}
        for b_name in all_block_names:
            assert b_name in strategy_block_names, (
                f"Block '{b_name}' not referenced in strategy"
            )

    def test_strategy_direction_from_parameters(
        self, rule_mode: RuleMode
    ) -> None:
        """Strategy direction is inferred from hypothesis parameters."""
        hyp = HypothesisConfig(
            name="test",
            description="long only mean-reversion",
            parameters={"direction": "LONG"},
        )
        _, strategies = rule_mode.build(hyp)
        assert strategies[0].direction == StrategyDirection.LONG

    def test_overlapping_keywords_dont_duplicate_indicators(
        self, rule_mode: RuleMode
    ) -> None:
        """When multiple keyword sets share an indicator, it only appears once."""
        hyp = HypothesisConfig(
            name="test",
            description="mean-reversion and divergence detection",
        )
        blocks, _ = rule_mode.build(hyp)
        # Both patterns produce RSI — should only appear once
        rsi_blocks = [b for b in blocks if b.indicator.name == "RSI"]
        assert len(rsi_blocks) == 1

    def test_direction_inferred_from_description_text(
        self, rule_mode: RuleMode
    ) -> None:
        """Direction is inferred from description when parameters don't specify it."""
        hyp = HypothesisConfig(
            name="test",
            description="short only breakout strategy",
        )
        _, strategies = rule_mode.build(hyp)
        assert strategies[0].direction == StrategyDirection.SHORT


# ── Task 1.2 / 1.4: BuildingBlockValidator (RB-5) ────────────────────────────


class TestBuildingBlockValidator:
    """Validator rejects invalid building blocks / strategies (RB-5)."""

    @staticmethod
    def _make_valid_block(name: str = "RSI_1") -> BuildingBlock:
        return BuildingBlock(
            name=name,
            indicator=IndicatorConfig(name="RSI", params={"period": 14}),
            entry=EntryRule(
                description="RSI oversold", conditions=["rsi(14) < 30"]
            ),
        )

    def test_valid_blocks_pass(self, validator: BuildingBlockValidator) -> None:
        """A valid set of blocks + strategies passes without error."""
        blocks = [self._make_valid_block()]
        strategies = [Strategy(name="S1", building_blocks=["RSI_1"])]
        validator.validate(blocks, strategies)  # should not raise

    def test_unknown_indicator_rejected(
        self, validator: BuildingBlockValidator
    ) -> None:
        """An indicator name not in the known set is rejected."""
        blocks = [
            BuildingBlock(
                name="bad",
                indicator=IndicatorConfig(
                    name="UNKNOWN_INDICATOR", params={}
                ),
            )
        ]
        with pytest.raises(ValueError, match="Unknown indicator"):
            validator.validate(blocks, [])

    def test_missing_required_params_rejected(
        self, validator: BuildingBlockValidator
    ) -> None:
        """An indicator missing its required params is rejected."""
        blocks = [
            BuildingBlock(
                name="bad",
                indicator=IndicatorConfig(name="RSI", params={}),
            )
        ]
        with pytest.raises(ValueError, match="missing required"):
            validator.validate(blocks, [])

    def test_empty_entry_conditions_rejected(
        self, validator: BuildingBlockValidator
    ) -> None:
        """A building block with empty entry conditions is rejected."""
        blocks = [
            BuildingBlock(
                name="bad",
                indicator=IndicatorConfig(name="RSI", params={"period": 14}),
                entry=EntryRule(description="empty", conditions=[]),
            )
        ]
        with pytest.raises(ValueError, match="empty conditions"):
            validator.validate(blocks, [])

    def test_empty_exit_conditions_rejected(
        self, validator: BuildingBlockValidator
    ) -> None:
        """A building block with empty exit conditions is rejected."""
        blocks = [
            BuildingBlock(
                name="bad",
                indicator=IndicatorConfig(name="RSI", params={"period": 14}),
                exit=ExitRule(description="empty", conditions=[]),
            )
        ]
        with pytest.raises(ValueError, match="empty conditions"):
            validator.validate(blocks, [])

    def test_dangling_strategy_ref_rejected(
        self, validator: BuildingBlockValidator
    ) -> None:
        """A strategy referencing a non-existent block is rejected."""
        blocks = [self._make_valid_block()]
        strategies = [
            Strategy(
                name="S1",
                building_blocks=["RSI_1", "NONEXISTENT_BLOCK"],
            )
        ]
        with pytest.raises(ValueError, match="unknown building block"):
            validator.validate(blocks, strategies)

    def test_duplicate_block_name_rejected(
        self, validator: BuildingBlockValidator
    ) -> None:
        """Two building blocks with the same name are rejected."""
        blocks = [
            self._make_valid_block(name="dup"),
            self._make_valid_block(name="dup"),
        ]
        with pytest.raises(ValueError, match="Duplicate"):
            validator.validate(blocks, [])

    def test_empty_block_list_passes(
        self, validator: BuildingBlockValidator
    ) -> None:
        """An empty block list with empty strategies passes."""
        validator.validate([], [])  # should not raise

    def test_block_without_entry_exit_passes(
        self, validator: BuildingBlockValidator
    ) -> None:
        """A block with neither entry nor exit rules passes (optional)."""
        blocks = [
            BuildingBlock(
                name="raw_indicator",
                indicator=IndicatorConfig(name="RSI", params={"period": 14}),
            )
        ]
        validator.validate(blocks, [])  # should not raise

    def test_entry_conditions_referencing_known_indicator_passes(
        self, validator: BuildingBlockValidator
    ) -> None:
        """Conditions that reference the indicator itself are allowed (string only)."""
        blocks = [
            BuildingBlock(
                name="rsi_test",
                indicator=IndicatorConfig(name="RSI", params={"period": 14}),
                entry=EntryRule(
                    description="RSI based entry",
                    conditions=["rsi(14) < 30"],
                ),
            )
        ]
        validator.validate(blocks, [])  # should not raise


# ── Task 1.3 / 1.4: HypothesisBuilder Facade ─────────────────────────────────


class TestHypothesisBuilder:
    """HypothesisBuilder facade dispatches to the correct mode."""

    @pytest.mark.asyncio
    async def test_default_mode_is_rule(self) -> None:
        """Builder defaults to rule mode when no mode is specified."""
        builder = HypothesisBuilder()
        assert builder._mode == "rule"

    @pytest.mark.asyncio
    async def test_rule_dispatch_returns_valid_building_blocks(
        self,
    ) -> None:
        """build() with rule mode dispatches to RuleMode and returns valid blocks."""
        builder = HypothesisBuilder(mode="rule")
        hyp = HypothesisConfig(
            name="test", description="mean-reversion EURUSD"
        )
        blocks, strategies = await builder.build([hyp])
        assert len(blocks) >= 1
        assert len(strategies) >= 1
        assert isinstance(blocks[0], BuildingBlock)
        assert isinstance(strategies[0], Strategy)

    @pytest.mark.asyncio
    async def test_empty_hypotheses_returns_empty_lists(self) -> None:
        """Building with no hypotheses returns empty lists."""
        builder = HypothesisBuilder(mode="rule")
        blocks, strategies = await builder.build([])
        assert blocks == []
        assert strategies == []

    @pytest.mark.asyncio
    async def test_build_accepts_market_context(self) -> None:
        """Market context is accepted without error."""
        builder = HypothesisBuilder(mode="rule")
        hyp = HypothesisConfig(name="test", description="breakout")
        blocks, strategies = await builder.build(
            [hyp], market_context={"market": "EURUSD"}
        )
        assert len(blocks) >= 1
        assert len(strategies) >= 1

    @pytest.mark.asyncio
    async def test_multiple_hypotheses_combine_results(self) -> None:
        """Multiple hypotheses produce combined building blocks."""
        builder = HypothesisBuilder(mode="rule")
        h1 = HypothesisConfig(name="h1", description="mean-reversion")
        h2 = HypothesisConfig(name="h2", description="momentum")
        blocks, strategies = await builder.build([h1, h2])
        indicator_names = {b.indicator.name for b in blocks}
        assert "RSI" in indicator_names
        assert "BB" in indicator_names
        assert "EMA" in indicator_names
        assert "MACD" in indicator_names

    @pytest.mark.asyncio
    async def test_always_returns_valid_output(self) -> None:
        """Builder always produces valid output per RB-5 (fallback to default)."""
        builder = HypothesisBuilder(mode="rule")
        hyp = HypothesisConfig(
            name="test",
            description="something that should work with default fallback",
        )
        blocks, strategies = await builder.build([hyp])
        # Even with a non-matching description, it should return valid blocks
        assert len(blocks) >= 1
        assert len(strategies) >= 1
        # Validate: all blocks should have known indicators
        known = {"RSI", "BB", "EMA", "MACD", "ATR", "Donchian", "Volume"}
        for b in blocks:
            assert b.indicator.name in known

    @pytest.mark.asyncio
    async def test_llm_mode_falls_back_to_rule(self) -> None:
        """When mode='llm' but unimplemented, falls back to rule."""
        builder = HypothesisBuilder(mode="llm")
        hyp = HypothesisConfig(name="test", description="mean-reversion")
        blocks, strategies = await builder.build([hyp])
        assert len(blocks) >= 1
        assert blocks[0].indicator.name == "RSI"

    @pytest.mark.asyncio
    async def test_build_with_none_market_context(self) -> None:
        """Market_context=None is accepted without error."""
        builder = HypothesisBuilder(mode="rule")
        hyp = HypothesisConfig(name="test", description="breakout")
        blocks, strategies = await builder.build([hyp], market_context=None)
        assert len(blocks) >= 1

    @pytest.mark.asyncio
    async def test_single_market_context_default(self) -> None:
        """Default market_context parameter works (None default)."""
        builder = HypothesisBuilder(mode="rule")
        hyp = HypothesisConfig(name="test", description="momentum")
        blocks, strategies = await builder.build([hyp])
        assert len(blocks) >= 1
        assert len(strategies) >= 1


# ── Task 2.1 / 2.5: LLMMode — Prompt Construction ─────────────────────────────


class TestLLMModePrompt:
    """LLMMode._build_prompt() constructs a structured prompt with hypothesis context."""

    def test_build_prompt_includes_hypothesis_details(
        self,
    ) -> None:
        """Prompt includes hypothesis name, description, and expected outcome."""
        llm_mode = LLMMode(LLMConfig(provider="openai"))
        hyp = HypothesisConfig(
            name="momentum_test",
            description="Momentum strategy for tech stocks",
            expected_outcome="Positive returns over 3 months",
            llm_rationale="Tech sector showing strong momentum",
        )
        prompt = llm_mode._build_prompt(hyp)

        assert "momentum_test" in prompt
        assert "Momentum strategy for tech stocks" in prompt
        assert "Positive returns over 3 months" in prompt

    def test_build_prompt_includes_rationale_and_sources(
        self,
    ) -> None:
        """Prompt includes the llm_rationale text, source URLs, and data sources."""
        llm_mode = LLMMode(LLMConfig(provider="openai"))
        hyp = HypothesisConfig(
            name="inflation_test",
            description="Inflation and currency correlations",
            llm_rationale=(
                "Rising CPI and strong employment suggest "
                "inflationary pressure, benefiting commodity currencies"
            ),
            source_urls=["https://fred.stlouisfed.org/series/CPIAUCSL"],
            data_sources=["fred", "rss-news"],
        )
        prompt = llm_mode._build_prompt(hyp)

        assert "Rising CPI and strong employment" in prompt
        assert "fred.stlouisfed.org" in prompt
        assert "fred" in prompt
        assert "rss-news" in prompt

    def test_build_prompt_includes_json_schema(
        self,
    ) -> None:
        """Prompt includes the JSON schema for building_blocks and strategies."""
        llm_mode = LLMMode(LLMConfig(provider="openai"))
        hyp = HypothesisConfig(
            name="test",
            description="Test hypothesis",
            llm_rationale="Rationale text",
        )
        prompt = llm_mode._build_prompt(hyp)

        assert "building_blocks" in prompt
        assert "strategies" in prompt
        assert "indicator" in prompt
        assert '"name"' in prompt or '"params"' in prompt

    def test_build_prompt_handles_none_rationale(
        self,
    ) -> None:
        """None rationale is handled gracefully (shows N/A)."""
        llm_mode = LLMMode(LLMConfig(provider="openai"))
        hyp = HypothesisConfig(
            name="test",
            description="Test hypothesis",
            llm_rationale=None,
        )
        prompt = llm_mode._build_prompt(hyp)

        assert "test" in prompt
        assert "N/A" in prompt or "Rationale:" in prompt

    def test_build_prompt_handles_empty_sources(
        self,
    ) -> None:
        """Empty source lists are handled gracefully."""
        llm_mode = LLMMode(LLMConfig(provider="openai"))
        hyp = HypothesisConfig(
            name="test",
            description="Test hypothesis",
            llm_rationale="Some rationale",
            source_urls=[],
            data_sources=[],
        )
        prompt = llm_mode._build_prompt(hyp)

        assert "Some rationale" in prompt


# ── Task 2.2 / 2.5: LLMMode — JSON Parse ──────────────────────────────────────


class TestLLMModeParse:
    """LLMMode._parse_response() parses LLM JSON into domain models."""

    def test_parse_valid_response(self) -> None:
        """Valid JSON response produces BuildingBlock and Strategy instances."""
        llm_mode = LLMMode(LLMConfig(provider="openai"))
        response = json.dumps({
            "building_blocks": [
                {
                    "name": "RSI_14",
                    "indicator": {"name": "RSI", "params": {"period": 14}},
                    "entry": {
                        "description": "RSI oversold",
                        "conditions": ["rsi(14) < 30"],
                    },
                    "exit": {
                        "description": "RSI overbought",
                        "conditions": ["rsi(14) > 70"],
                    },
                },
            ],
            "strategies": [
                {
                    "name": "MomentumStrategy",
                    "direction": "LONG",
                    "building_blocks": ["RSI_14"],
                },
            ],
        })
        blocks, strategies = llm_mode._parse_response(response)

        assert len(blocks) == 1
        assert blocks[0].name == "RSI_14"
        assert blocks[0].indicator.name == "RSI"
        assert blocks[0].indicator.params["period"] == 14
        assert blocks[0].entry is not None
        assert "rsi(14) < 30" in (blocks[0].entry.conditions or [])
        assert len(strategies) == 1
        assert strategies[0].name == "MomentumStrategy"
        assert strategies[0].direction == StrategyDirection.LONG
        assert strategies[0].building_blocks == ["RSI_14"]

    def test_parse_multiple_blocks_and_strategies(
        self,
    ) -> None:
        """Multiple building blocks and strategies are parsed correctly."""
        llm_mode = LLMMode(LLMConfig(provider="openai"))
        response = json.dumps({
            "building_blocks": [
                {
                    "name": "RSI_14",
                    "indicator": {"name": "RSI", "params": {"period": 14}},
                },
                {
                    "name": "EMA_200",
                    "indicator": {"name": "EMA", "params": {"period": 200}},
                },
            ],
            "strategies": [
                {
                    "name": "LongStrategy",
                    "direction": "LONG",
                    "building_blocks": ["RSI_14", "EMA_200"],
                },
                {
                    "name": "ShortStrategy",
                    "direction": "SHORT",
                    "building_blocks": ["RSI_14"],
                },
            ],
        })
        blocks, strategies = llm_mode._parse_response(response)

        assert len(blocks) == 2
        assert len(strategies) == 2
        assert strategies[0].direction == StrategyDirection.LONG
        assert strategies[1].direction == StrategyDirection.SHORT

    def test_parse_empty_response_raises(self) -> None:
        """Empty response raises ValueError."""
        llm_mode = LLMMode(LLMConfig(provider="openai"))
        with pytest.raises(ValueError, match="empty"):
            llm_mode._parse_response("")

    def test_parse_whitespace_response_raises(self) -> None:
        """Whitespace-only response raises ValueError."""
        llm_mode = LLMMode(LLMConfig(provider="openai"))
        with pytest.raises(ValueError, match="empty"):
            llm_mode._parse_response("   \n  ")

    def test_parse_invalid_json_raises(self) -> None:
        """Invalid JSON raises ValueError."""
        llm_mode = LLMMode(LLMConfig(provider="openai"))
        with pytest.raises(ValueError, match="Failed to parse"):
            llm_mode._parse_response("not valid json")

    def test_parse_missing_building_blocks_raises(self) -> None:
        """Missing building_blocks key raises ValueError."""
        llm_mode = LLMMode(LLMConfig(provider="openai"))
        with pytest.raises(ValueError, match="missing"):
            llm_mode._parse_response('{"strategies": []}')

    def test_parse_missing_strategies_raises(self) -> None:
        """Missing strategies key raises ValueError."""
        llm_mode = LLMMode(LLMConfig(provider="openai"))
        with pytest.raises(ValueError, match="missing"):
            llm_mode._parse_response('{"building_blocks": []}')

    def test_parse_blocks_without_entry_exit(
        self,
    ) -> None:
        """Building blocks without entry/exit rules parse correctly (optional)."""
        llm_mode = LLMMode(LLMConfig(provider="openai"))
        response = json.dumps({
            "building_blocks": [
                {
                    "name": "BB_20",
                    "indicator": {
                        "name": "BB",
                        "params": {"period": 20, "deviation": 2.0},
                    },
                },
            ],
            "strategies": [
                {
                    "name": "S1",
                    "direction": "BOTH",
                    "building_blocks": ["BB_20"],
                },
            ],
        })
        blocks, strategies = llm_mode._parse_response(response)

        assert len(blocks) == 1
        assert blocks[0].entry is None
        assert blocks[0].exit is None


# ── Task 2.3 / 2.6: Fallback Chain (RB-6) ───────────────────────────────────


class TestHypothesisBuilderLLMFallback:
    """HypothesisBuilder fallback chain (RB-6) — LLM error → Rule mode."""

    @pytest.mark.asyncio
    async def test_llm_mode_fallback_on_exception(
        self,
    ) -> None:
        """When LLM mode raises, builder falls back to rule mode."""
        builder = HypothesisBuilder(
            mode="llm",
            llm_config=LLMConfig(provider="openai"),
        )
        with patch.object(builder, "_llm_mode") as mock_llm:
            mock_llm.build = AsyncMock(
                side_effect=Exception("LLM API error")
            )

            hyp = HypothesisConfig(
                name="test", description="mean-reversion EURUSD"
            )
            blocks, strategies = await builder.build([hyp])

            # Should return valid rule-mode output
            assert len(blocks) >= 1
            assert blocks[0].indicator.name in {
                "RSI", "BB", "EMA", "MACD", "ATR",
                "Donchian", "Volume",
            }

    @pytest.mark.asyncio
    async def test_llm_mode_fallback_on_import_error(
        self,
    ) -> None:
        """When LLM SDK is not installed (ImportError), falls back to rule."""
        builder = HypothesisBuilder(
            mode="llm",
            llm_config=LLMConfig(provider="openai"),
        )
        with patch.object(builder, "_llm_mode") as mock_llm:
            mock_llm.build = AsyncMock(
                side_effect=ImportError(
                    "openai SDK is not installed"
                ),
            )

            hyp = HypothesisConfig(
                name="test", description="breakout with volume"
            )
            blocks, strategies = await builder.build([hyp])

            assert len(blocks) >= 1
            # Breakout keyword → Donchian + Volume
            indicator_names = {b.indicator.name for b in blocks}
            assert "Donchian" in indicator_names
            assert "Volume" in indicator_names

    @pytest.mark.asyncio
    async def test_fallback_logs_warning(
        self,
    ) -> None:
        """Fallback logs a warning message."""
        builder = HypothesisBuilder(
            mode="llm",
            llm_config=LLMConfig(provider="openai"),
        )
        with patch.object(builder, "_llm_mode") as mock_llm:
            mock_llm.build = AsyncMock(
                side_effect=Exception("API error")
            )
            with patch(
                "quantlab.agents.hypothesis_builder.logger"
            ) as mock_logger:
                hyp = HypothesisConfig(
                    name="test", description="momentum"
                )
                await builder.build([hyp])

                mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_mode_success_returns_llm_output(
        self,
    ) -> None:
        """When LLM succeeds, return LLM-generated blocks/strategies."""
        builder = HypothesisBuilder(
            mode="llm",
            llm_config=LLMConfig(provider="openai"),
        )
        expected_blocks = [
            BuildingBlock(
                name="RSI_14",
                indicator=IndicatorConfig(
                    name="RSI", params={"period": 14}
                ),
            ),
        ]
        expected_strategies = [
            Strategy(
                name="S1", building_blocks=["RSI_14"]
            ),
        ]

        with patch.object(builder, "_llm_mode") as mock_llm:
            mock_llm.build = AsyncMock(
                return_value=(expected_blocks, expected_strategies),
            )

            hyp = HypothesisConfig(
                name="test", description="momentum"
            )
            blocks, strategies = await builder.build([hyp])

            assert blocks == expected_blocks
            assert strategies == expected_strategies

    @pytest.mark.asyncio
    async def test_llm_without_config_uses_rule(
        self,
    ) -> None:
        """mode='llm' but no LLMConfig → uses rule mode."""
        builder = HypothesisBuilder(mode="llm")
        hyp = HypothesisConfig(
            name="test", description="mean-reversion EURUSD"
        )
        blocks, strategies = await builder.build([hyp])
        assert len(blocks) >= 1
        # Should have RSI (from rule mode fallback)
        assert blocks[0].indicator.name == "RSI"


# ── Task 2.4 / 2.7: S-1 LLM mode with rationale + per-call mode override ────


class TestHypothesisBuilderLLMModeScenario:
    """S-1: LLM mode with detailed rationale produces valid output."""

    @pytest.mark.asyncio
    async def test_s1_llm_mode_with_rationale(
        self,
    ) -> None:
        """S-1: Detailed rationale → LLM → valid blocks/strategies."""
        builder = HypothesisBuilder(
            mode="llm",
            llm_config=LLMConfig(provider="openai"),
        )
        hyp = HypothesisConfig(
            name="inflation_hypothesis",
            description="Inflation and currency correlations",
            expected_outcome="Commodity currencies strengthen",
            llm_rationale=(
                "Rising CPI and strong employment suggest "
                "inflationary pressure, benefiting commodity currencies"
            ),
            data_sources=["fred", "rss-news"],
        )

        expected_blocks = [
            BuildingBlock(
                name="RSI_14",
                indicator=IndicatorConfig(
                    name="RSI", params={"period": 14}
                ),
                entry={
                    "description": "RSI oversold",
                    "conditions": ["rsi(14) < 30"],
                },
            ),
        ]
        expected_strategies = [
            Strategy(
                name="InflationStrategy",
                direction="LONG",
                building_blocks=["RSI_14"],
            ),
        ]

        with patch.object(builder, "_llm_mode") as mock_llm:
            mock_llm.build = AsyncMock(
                return_value=(expected_blocks, expected_strategies),
            )
            blocks, strategies = await builder.build([hyp])

            assert len(blocks) >= 1
            assert len(strategies) >= 1
            for block in blocks:
                assert isinstance(block.indicator, IndicatorConfig)

    @pytest.mark.asyncio
    async def test_per_call_mode_override_to_llm(
        self,
    ) -> None:
        """Per-call mode='llm' overrides construction-time mode='rule'."""
        builder = HypothesisBuilder(mode="rule")
        hyp = HypothesisConfig(
            name="test", description="custom indicator"
        )

        expected_blocks = [
            BuildingBlock(
                name="ATR_14",
                indicator=IndicatorConfig(
                    name="ATR", params={"period": 14}
                ),
            ),
        ]
        expected_strategies = [
            Strategy(
                name="ATRStrategy",
                building_blocks=["ATR_14"],
            ),
        ]

        with patch.object(builder, "_llm_mode") as mock_llm:
            mock_llm.build = AsyncMock(
                return_value=(expected_blocks, expected_strategies),
            )
            blocks, strategies = await builder.build(
                [hyp], mode="llm"
            )

            assert blocks == expected_blocks
            assert strategies == expected_strategies

    @pytest.mark.asyncio
    async def test_per_call_mode_override_to_rule(
        self,
    ) -> None:
        """Per-call mode='rule' overrides construction-time mode='llm'."""
        builder = HypothesisBuilder(
            mode="llm",
            llm_config=LLMConfig(provider="openai"),
        )
        hyp = HypothesisConfig(
            name="test", description="mean-reversion"
        )
        # Should use rule even though construction mode is llm
        blocks, strategies = await builder.build([hyp], mode="rule")

        assert len(blocks) >= 1
        assert blocks[0].indicator.name == "RSI"

    @pytest.mark.asyncio
    async def test_llm_mode_multiple_hypotheses(
        self,
    ) -> None:
        """LLM mode with multiple hypotheses calls LLM for each."""
        builder = HypothesisBuilder(
            mode="llm",
            llm_config=LLMConfig(provider="openai"),
        )
        h1 = HypothesisConfig(
            name="h1", description="mean-reversion"
        )
        h2 = HypothesisConfig(
            name="h2", description="momentum"
        )

        with patch.object(builder, "_llm_mode") as mock_llm:
            mock_llm.build = AsyncMock(
                return_value=(
                    [BuildingBlock(
                        name="RSI_14",
                        indicator=IndicatorConfig(
                            name="RSI", params={"period": 14}
                        ),
                    )],
                    [Strategy(
                        name="S1", building_blocks=["RSI_14"]
                    )],
                ),
            )
            blocks, strategies = await builder.build([h1, h2])

            assert mock_llm.build.call_count == 2
            assert len(blocks) >= 1

    @pytest.mark.asyncio
    async def test_llm_output_validated_after_parse(
        self,
    ) -> None:
        """LLM output is validated by BuildingBlockValidator after parsing."""
        builder = HypothesisBuilder(
            mode="llm",
            llm_config=LLMConfig(provider="openai"),
        )

        with patch.object(builder, "_llm_mode") as mock_llm:
            mock_llm.build = AsyncMock(
                return_value=(
                    [BuildingBlock(
                        name="RSI_14",
                        indicator=IndicatorConfig(
                            name="RSI", params={"period": 14}
                        ),
                    )],
                    [Strategy(
                        name="S1", building_blocks=["RSI_14"]
                    )],
                ),
            )
            with patch.object(
                builder, "_validator"
            ) as mock_validator:
                hyp = HypothesisConfig(
                    name="test", description="momentum"
                )
                await builder.build([hyp])

                mock_validator.validate.assert_called_once()

    # ── Triangulation ───────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_llm_mode_empty_hypotheses(
        self,
    ) -> None:
        """Empty hypotheses returns empty lists even in LLM mode."""
        builder = HypothesisBuilder(
            mode="llm",
            llm_config=LLMConfig(provider="openai"),
        )
        blocks, strategies = await builder.build([])
        assert blocks == []
        assert strategies == []

    @pytest.mark.asyncio
    async def test_llm_mode_with_market_context(
        self,
    ) -> None:
        """Market context is passed through in LLM mode."""
        builder = HypothesisBuilder(
            mode="llm",
            llm_config=LLMConfig(provider="openai"),
        )
        hyp = HypothesisConfig(
            name="test",
            description="momentum strategy",
            llm_rationale="Strong momentum signal",
        )

        with patch.object(builder, "_llm_mode") as mock_llm:
            mock_llm.build = AsyncMock(
                return_value=(
                    [BuildingBlock(
                        name="RSI_14",
                        indicator=IndicatorConfig(
                            name="RSI", params={"period": 14}
                        ),
                    )],
                    [Strategy(
                        name="S1", building_blocks=["RSI_14"]
                    )],
                ),
            )
            blocks, strategies = await builder.build(
                [hyp], market_context={"market": "EURUSD"}
            )
            assert len(blocks) == 1
            assert blocks[0].name == "RSI_14"

    @pytest.mark.asyncio
    async def test_llm_mode_validates_after_llm_success(
        self,
    ) -> None:
        """Validation runs on LLM output before returning."""
        builder = HypothesisBuilder(
            mode="llm",
            llm_config=LLMConfig(provider="openai"),
        )
        hyp = HypothesisConfig(
            name="test",
            description="mean-reversion",
            llm_rationale="Test rationale",
        )

        blocks = [
            BuildingBlock(
                name="RSI_14",
                indicator=IndicatorConfig(
                    name="RSI", params={"period": 14}
                ),
            ),
            BuildingBlock(
                name="BB_20",
                indicator=IndicatorConfig(
                    name="BB",
                    params={"period": 20, "deviation": 2.0},
                ),
            ),
        ]
        strategies = [
            Strategy(
                name="Strategy_1",
                building_blocks=["RSI_14", "BB_20"],
            ),
        ]

        with patch.object(builder, "_llm_mode") as mock_llm:
            mock_llm.build = AsyncMock(
                return_value=(blocks, strategies),
            )
            result_blocks, result_strategies = await builder.build(
                [hyp]
            )

            assert len(result_blocks) == 2
            assert len(result_strategies) == 1
            assert result_strategies[0].building_blocks == [
                "RSI_14",
                "BB_20",
            ]


# ── Triangulation: prompt edge cases ────────────────────────────────────────


class TestLLMModePromptEdgeCases:
    """Additional edge cases for LLMMode prompt construction."""

    def test_build_prompt_with_exact_s1_rationale(
        self,
    ) -> None:
        """S-1 exact rationale text appears in prompt."""
        llm_mode = LLMMode(LLMConfig(provider="openai"))
        hyp = HypothesisConfig(
            name="inflation_hypothesis",
            description="Inflation and currency correlations",
            llm_rationale=(
                "Rising CPI and strong employment suggest "
                "inflationary pressure, benefiting commodity currencies"
            ),
            data_sources=["fred", "rss-news"],
        )
        prompt = llm_mode._build_prompt(hyp)

        assert "Rising CPI and strong employment" in prompt
        assert "fred" in prompt
        assert "rss-news" in prompt
        assert "inflation_hypothesis" in prompt

    def test_parse_strategy_default_direction(
        self,
    ) -> None:
        """Strategy without direction defaults to BOTH."""
        llm_mode = LLMMode(LLMConfig(provider="openai"))
        response = json.dumps({
            "building_blocks": [
                {
                    "name": "RSI_14",
                    "indicator": {"name": "RSI", "params": {"period": 14}},
                },
            ],
            "strategies": [
                {
                    "name": "DefaultStrategy",
                    "building_blocks": ["RSI_14"],
                },
            ],
        })
        _, strategies = llm_mode._parse_response(response)
        assert strategies[0].direction == StrategyDirection.BOTH

    def test_parse_strategy_lowercase_direction(
        self,
    ) -> None:
        """Lowercase direction is normalised to uppercase enum."""
        llm_mode = LLMMode(LLMConfig(provider="openai"))
        response = json.dumps({
            "building_blocks": [
                {
                    "name": "RSI_14",
                    "indicator": {"name": "RSI", "params": {"period": 14}},
                },
            ],
            "strategies": [
                {
                    "name": "LongStrategy",
                    "direction": "long",
                    "building_blocks": ["RSI_14"],
                },
            ],
        })
        _, strategies = llm_mode._parse_response(response)
        assert strategies[0].direction == StrategyDirection.LONG

    def test_parse_blocks_with_entry_only(
        self,
    ) -> None:
        """Block with entry but no exit parses correctly."""
        llm_mode = LLMMode(LLMConfig(provider="openai"))
        response = json.dumps({
            "building_blocks": [
                {
                    "name": "EntryOnly",
                    "indicator": {
                        "name": "Donchian",
                        "params": {"period": 20},
                    },
                    "entry": {
                        "description": "Breakout entry",
                        "conditions": ["high > donchian_high(20)"],
                    },
                },
            ],
            "strategies": [
                {
                    "name": "S1",
                    "direction": "LONG",
                    "building_blocks": ["EntryOnly"],
                },
            ],
        })
        blocks, _ = llm_mode._parse_response(response)
        assert blocks[0].entry is not None
        assert blocks[0].entry.conditions == [
            "high > donchian_high(20)",
        ]
        assert blocks[0].exit is None
