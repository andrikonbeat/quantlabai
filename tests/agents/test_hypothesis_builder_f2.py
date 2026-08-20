"""Tests for F2 wiring — RuleMode + LLMMode parameter validation."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from quantlab.agents.hypothesis_builder.rule import RuleMode
from quantlab.agents.hypothesis_builder.llm import LLMMode
from quantlab.dsl.models import (
    BuildingBlock,
    EntryRule,
    HypothesisConfig,
    IndicatorConfig,
    LLMConfig,
    Strategy,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def rule_mode() -> RuleMode:
    return RuleMode()


@pytest.fixture()
def llm_mode() -> LLMMode:
    return LLMMode(llm_config=LLMConfig(provider="openai"))


# ── Task T-011: RuleMode F2 wiring ───────────────────────────────────────────


class TestRuleModeF2Wiring:
    """RuleMode validates parameter overrides before applying them."""

    def test_valid_override_is_applied(self, rule_mode: RuleMode) -> None:
        hyp = HypothesisConfig(
            name="test",
            description="mean-reversion",
            parameters={"rsi_period": 7},
        )
        block = BuildingBlock(
            name="RSI_MeanReversion",
            indicator=IndicatorConfig(
                name="RSI",
                params={"period": 14, "oversold": 30, "overbought": 70},
            ),
            entry=EntryRule(
                description="RSI oversold entry",
                conditions=["rsi(14) < 30"],
            ),
        )
        result = rule_mode._apply_parameter_overrides(block, hyp)
        assert result.indicator.params["period"] == 7

    def test_invalid_override_keeps_defaults(self, rule_mode: RuleMode) -> None:
        hyp = HypothesisConfig(
            name="test",
            description="mean-reversion",
            parameters={"rsi_period": 500},
        )
        block = BuildingBlock(
            name="RSI_MeanReversion",
            indicator=IndicatorConfig(
                name="RSI",
                params={"period": 14, "oversold": 30, "overbought": 70},
            ),
            entry=EntryRule(
                description="RSI oversold entry",
                conditions=["rsi(14) < 30"],
            ),
        )
        result = rule_mode._apply_parameter_overrides(block, hyp)
        assert result.indicator.params["period"] == 14


# ── Task T-011: LLMMode F2 wiring ────────────────────────────────────────────


class TestLLMModeF2Wiring:
    """LLMMode drops invalid parsed building blocks."""

    def test_parse_response_drops_invalid_params(
        self, llm_mode: LLMMode, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from quantlab.agents.parameter_validator import ParameterValidator, ValidationResult

        mock_validator = MagicMock(spec=ParameterValidator)
        mock_validator.validate_hypothesis.return_value = ValidationResult(
            valid=False,
            errors=["rsi.period=500 out of range [2, 200]"],
        )
        monkeypatch.setattr(
            "quantlab.agents.hypothesis_builder.llm.ParameterValidator",
            lambda: mock_validator,
        )

        response = json.dumps({
            "building_blocks": [
                {
                    "name": "RSI_14",
                    "indicator": {"name": "RSI", "params": {"period": 500}},
                },
            ],
            "strategies": [
                {
                    "name": "S1",
                    "direction": "LONG",
                    "building_blocks": ["RSI_14"],
                },
            ],
        })
        blocks, strategies = llm_mode._parse_response(response)
        assert len(blocks) == 0

    def test_parse_response_keeps_valid_params(
        self, llm_mode: LLMMode, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from quantlab.agents.parameter_validator import ParameterValidator, ValidationResult

        mock_validator = MagicMock(spec=ParameterValidator)
        mock_validator.validate_hypothesis.return_value = ValidationResult(
            valid=True,
            errors=[],
        )
        monkeypatch.setattr(
            "quantlab.agents.hypothesis_builder.llm.ParameterValidator",
            lambda: mock_validator,
        )

        response = json.dumps({
            "building_blocks": [
                {
                    "name": "RSI_14",
                    "indicator": {"name": "RSI", "params": {"period": 14}},
                },
            ],
            "strategies": [
                {
                    "name": "S1",
                    "direction": "LONG",
                    "building_blocks": ["RSI_14"],
                },
            ],
        })
        blocks, strategies = llm_mode._parse_response(response)
        assert len(blocks) == 1
