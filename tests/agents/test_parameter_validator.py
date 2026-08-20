"""Tests for ParameterValidator — blocking validation against SQXDocProvider."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from quantlab.agents.parameter_validator import ParameterValidator, ValidationResult
from quantlab.dsl.models import HypothesisConfig


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def mock_provider() -> MagicMock:
    provider = MagicMock()
    provider.get_description.return_value = "RSI"
    provider.get_valid_range.return_value = (2, 200)
    provider.get_enum_values.return_value = None

    def _get_type(indicator: str, param: str, version: str) -> str:
        if param in {"period", "oversold", "overbought"}:
            return "int"
        if param in {"deviation"}:
            return "float"
        return "string"

    provider.get_type.side_effect = _get_type
    return provider


@pytest.fixture()
def validator(mock_provider: MagicMock) -> ParameterValidator:
    return ParameterValidator(doc_provider=mock_provider)


# ── Task T-005: Valid parameters pass ────────────────────────────────────────


class TestParameterValidatorValid:
    """Valid parameter sets pass validation."""

    def test_valid_params_pass(self, validator: ParameterValidator) -> None:
        hyp = HypothesisConfig(
            name="valid_rsi",
            description="RSI mean reversion",
            parameters={"rsi_period": 14, "rsi_oversold": 30},
            confidence=0.6,
        )
        result = validator.validate_hypothesis(hyp, sqx_version="144.2953")
        assert result.valid is True
        assert result.errors == []

    def test_valid_bb_params_pass(self, validator: ParameterValidator) -> None:
        hyp = HypothesisConfig(
            name="valid_bb",
            description="Bollinger Bands",
            parameters={"bb_period": 20, "bb_deviation": 2.0},
            confidence=0.6,
        )
        result = validator.validate_hypothesis(hyp, sqx_version="144.2953")
        assert result.valid is True


# ── Task T-005: Invalid parameters rejected ──────────────────────────────────


class TestParameterValidatorRejection:
    """Invalid parameters are rejected with descriptive errors."""

    def test_out_of_range_rejected(self, validator: ParameterValidator) -> None:
        validator._provider.get_valid_range.return_value = (2, 200)
        hyp = HypothesisConfig(
            name="bad_rsi",
            description="RSI with bad period",
            parameters={"rsi_period": 500},
            confidence=0.6,
        )
        result = validator.validate_hypothesis(hyp, sqx_version="144.2953")
        assert result.valid is False
        assert any("out of range" in e for e in result.errors)

    def test_unknown_indicator_rejected(self, validator: ParameterValidator) -> None:
        validator._provider.get_description.return_value = ""
        validator._provider.has_indicator.return_value = False
        hyp = HypothesisConfig(
            name="bad_indicator",
            description="Unknown indicator",
            parameters={"unknown_period": 14},
            confidence=0.6,
        )
        result = validator.validate_hypothesis(hyp, sqx_version="144.2953")
        assert result.valid is False
        assert any("Unknown indicator" in e for e in result.errors)

    def test_enum_value_rejected(self, validator: ParameterValidator) -> None:
        validator._provider.get_enum_values.return_value = ["fast", "slow"]
        hyp = HypothesisConfig(
            name="bad_enum",
            description="Invalid enum",
            parameters={"macd_mode": "invalid"},
            confidence=0.6,
        )
        result = validator.validate_hypothesis(hyp, sqx_version="144.2953")
        assert result.valid is False
        assert any("not in enum" in e for e in result.errors)

    def test_type_mismatch_rejected(self, validator: ParameterValidator) -> None:
        validator._provider.get_valid_range.return_value = (2, 200)
        hyp = HypothesisConfig(
            name="type_mismatch",
            description="String for int param",
            parameters={"rsi_period": "fourteen"},
            confidence=0.6,
        )
        result = validator.validate_hypothesis(hyp, sqx_version="144.2953")
        assert result.valid is False
        assert any("type mismatch" in e for e in result.errors)
