"""Tests for EconomicSenseValidator — range and coherence checks."""

from __future__ import annotations

import pytest

from quantlab.agents.economic_sense.validator import EconomicSenseValidator
from quantlab.dsl.models import HypothesisConfig


@pytest.fixture()
def validator() -> EconomicSenseValidator:
    return EconomicSenseValidator()


class TestEconomicSenseValidator:
    """Parametrized tests for valid/invalid parameters and coherence rules."""

    # ── Valid parameters (no warnings) ─────────────────────────────────────

    def test_valid_rsi_no_warning(self, validator: EconomicSenseValidator) -> None:
        hyp = HypothesisConfig(
            name="valid_rsi",
            description="RSI mean reversion",
            parameters={"rsi_period": 14},
            confidence=0.6,
        )
        warnings = validator.validate(hyp)
        assert warnings == []

    def test_valid_bb_no_warning(self, validator: EconomicSenseValidator) -> None:
        hyp = HypothesisConfig(
            name="valid_bb",
            description="Bollinger Bands",
            parameters={"bb_period": 20, "bb_deviation": 2.0},
            confidence=0.6,
        )
        warnings = validator.validate(hyp)
        assert warnings == []

    def test_valid_sma_no_warning(self, validator: EconomicSenseValidator) -> None:
        hyp = HypothesisConfig(
            name="valid_sma",
            description="SMA trend",
            parameters={"sma_period": 50},
            confidence=0.6,
        )
        warnings = validator.validate(hyp)
        assert warnings == []

    def test_valid_ema_no_warning(self, validator: EconomicSenseValidator) -> None:
        hyp = HypothesisConfig(
            name="valid_ema",
            description="EMA trend",
            parameters={"ema_period": 200},
            confidence=0.6,
        )
        warnings = validator.validate(hyp)
        assert warnings == []

    def test_valid_atr_no_warning(self, validator: EconomicSenseValidator) -> None:
        hyp = HypothesisConfig(
            name="valid_atr",
            description="ATR filter",
            parameters={"atr_period": 14},
            confidence=0.6,
        )
        warnings = validator.validate(hyp)
        assert warnings == []

    def test_valid_macd_no_warning(self, validator: EconomicSenseValidator) -> None:
        hyp = HypothesisConfig(
            name="valid_macd",
            description="MACD trend",
            parameters={
                "macd_fast_period": 12,
                "macd_slow_period": 26,
                "macd_signal_period": 9,
            },
            confidence=0.6,
        )
        warnings = validator.validate(hyp)
        assert warnings == []

    # ── Range violations ───────────────────────────────────────────────────

    def test_rsi_below_min_warns(self, validator: EconomicSenseValidator) -> None:
        hyp = HypothesisConfig(
            name="rsi_low",
            description="RSI too short",
            parameters={"rsi_period": 1},
            confidence=0.6,
        )
        warnings = validator.validate(hyp)
        assert any("RSI period" in w and "out of range" in w for w in warnings)

    def test_rsi_above_max_warns(self, validator: EconomicSenseValidator) -> None:
        hyp = HypothesisConfig(
            name="rsi_high",
            description="RSI too long",
            parameters={"rsi_period": 500},
            confidence=0.6,
        )
        warnings = validator.validate(hyp)
        assert any("RSI period" in w and "out of range" in w for w in warnings)

    def test_bb_deviation_below_min_warns(
        self, validator: EconomicSenseValidator
    ) -> None:
        hyp = HypothesisConfig(
            name="bb_low",
            description="BB deviation too low",
            parameters={"bb_period": 20, "bb_deviation": 0.05},
            confidence=0.6,
        )
        warnings = validator.validate(hyp)
        assert any("BB deviation" in w and "out of range" in w for w in warnings)

    def test_bb_deviation_above_max_warns(
        self, validator: EconomicSenseValidator
    ) -> None:
        hyp = HypothesisConfig(
            name="bb_high",
            description="BB deviation too high",
            parameters={"bb_period": 20, "bb_deviation": 10.0},
            confidence=0.6,
        )
        warnings = validator.validate(hyp)
        assert any("BB deviation" in w and "out of range" in w for w in warnings)

    def test_sma_below_min_warns(self, validator: EconomicSenseValidator) -> None:
        hyp = HypothesisConfig(
            name="sma_low",
            description="SMA too short",
            parameters={"sma_period": 1},
            confidence=0.6,
        )
        warnings = validator.validate(hyp)
        assert any("SMA period" in w and "out of range" in w for w in warnings)

    def test_sma_above_max_warns(self, validator: EconomicSenseValidator) -> None:
        hyp = HypothesisConfig(
            name="sma_high",
            description="SMA too long",
            parameters={"sma_period": 1000},
            confidence=0.6,
        )
        warnings = validator.validate(hyp)
        assert any("SMA period" in w and "out of range" in w for w in warnings)

    def test_ema_below_min_warns(self, validator: EconomicSenseValidator) -> None:
        hyp = HypothesisConfig(
            name="ema_low",
            description="EMA too short",
            parameters={"ema_period": 1},
            confidence=0.6,
        )
        warnings = validator.validate(hyp)
        assert any("EMA period" in w and "out of range" in w for w in warnings)

    def test_ema_above_max_warns(self, validator: EconomicSenseValidator) -> None:
        hyp = HypothesisConfig(
            name="ema_high",
            description="EMA too long",
            parameters={"ema_period": 1000},
            confidence=0.6,
        )
        warnings = validator.validate(hyp)
        assert any("EMA period" in w and "out of range" in w for w in warnings)

    def test_atr_below_min_warns(self, validator: EconomicSenseValidator) -> None:
        hyp = HypothesisConfig(
            name="atr_low",
            description="ATR too short",
            parameters={"atr_period": 1},
            confidence=0.6,
        )
        warnings = validator.validate(hyp)
        assert any("ATR period" in w and "out of range" in w for w in warnings)

    def test_atr_above_max_warns(self, validator: EconomicSenseValidator) -> None:
        hyp = HypothesisConfig(
            name="atr_high",
            description="ATR too long",
            parameters={"atr_period": 500},
            confidence=0.6,
        )
        warnings = validator.validate(hyp)
        assert any("ATR period" in w and "out of range" in w for w in warnings)

    def test_macd_fast_below_min_warns(
        self, validator: EconomicSenseValidator
    ) -> None:
        hyp = HypothesisConfig(
            name="macd_fast_low",
            description="MACD fast too short",
            parameters={
                "macd_fast_period": 1,
                "macd_slow_period": 26,
                "macd_signal_period": 9,
            },
            confidence=0.6,
        )
        warnings = validator.validate(hyp)
        assert any("MACD fast period" in w and "out of range" in w for w in warnings)

    def test_macd_fast_above_max_warns(
        self, validator: EconomicSenseValidator
    ) -> None:
        hyp = HypothesisConfig(
            name="macd_fast_high",
            description="MACD fast too long",
            parameters={
                "macd_fast_period": 500,
                "macd_slow_period": 26,
                "macd_signal_period": 9,
            },
            confidence=0.6,
        )
        warnings = validator.validate(hyp)
        assert any("MACD fast period" in w and "out of range" in w for w in warnings)

    def test_macd_slow_below_min_warns(
        self, validator: EconomicSenseValidator
    ) -> None:
        hyp = HypothesisConfig(
            name="macd_slow_low",
            description="MACD slow too short",
            parameters={
                "macd_fast_period": 12,
                "macd_slow_period": 1,
                "macd_signal_period": 9,
            },
            confidence=0.6,
        )
        warnings = validator.validate(hyp)
        assert any("MACD slow period" in w and "out of range" in w for w in warnings)

    def test_macd_slow_above_max_warns(
        self, validator: EconomicSenseValidator
    ) -> None:
        hyp = HypothesisConfig(
            name="macd_slow_high",
            description="MACD slow too long",
            parameters={
                "macd_fast_period": 12,
                "macd_slow_period": 500,
                "macd_signal_period": 9,
            },
            confidence=0.6,
        )
        warnings = validator.validate(hyp)
        assert any("MACD slow period" in w and "out of range" in w for w in warnings)

    def test_macd_signal_below_min_warns(
        self, validator: EconomicSenseValidator
    ) -> None:
        hyp = HypothesisConfig(
            name="macd_signal_low",
            description="MACD signal too short",
            parameters={
                "macd_fast_period": 12,
                "macd_slow_period": 26,
                "macd_signal_period": 1,
            },
            confidence=0.6,
        )
        warnings = validator.validate(hyp)
        assert any("MACD signal period" in w and "out of range" in w for w in warnings)

    def test_macd_signal_above_max_warns(
        self, validator: EconomicSenseValidator
    ) -> None:
        hyp = HypothesisConfig(
            name="macd_signal_high",
            description="MACD signal too long",
            parameters={
                "macd_fast_period": 12,
                "macd_slow_period": 26,
                "macd_signal_period": 200,
            },
            confidence=0.6,
        )
        warnings = validator.validate(hyp)
        assert any("MACD signal period" in w and "out of range" in w for w in warnings)

    # ── Cross-parameter coherence ──────────────────────────────────────────

    def test_bb_sma_ratio_high_warns(self, validator: EconomicSenseValidator) -> None:
        hyp = HypothesisConfig(
            name="bb_sma_ratio_high",
            description="BB much wider than SMA",
            parameters={"bb_period": 20, "sma_period": 5},
            confidence=0.6,
        )
        warnings = validator.validate(hyp)
        assert any("BB/SMA period ratio" in w for w in warnings)

    def test_bb_sma_ratio_low_warns(self, validator: EconomicSenseValidator) -> None:
        hyp = HypothesisConfig(
            name="bb_sma_ratio_low",
            description="SMA much wider than BB",
            parameters={"bb_period": 5, "sma_period": 20},
            confidence=0.6,
        )
        warnings = validator.validate(hyp)
        assert any("BB/SMA period ratio" in w for w in warnings)

    def test_bb_sma_ratio_ok_no_warning(
        self, validator: EconomicSenseValidator
    ) -> None:
        hyp = HypothesisConfig(
            name="bb_sma_ratio_ok",
            description="BB and SMA aligned",
            parameters={"bb_period": 20, "sma_period": 50},
            confidence=0.6,
        )
        warnings = validator.validate(hyp)
        assert not any("BB/SMA period ratio" in w for w in warnings)

    def test_macd_fast_ge_slow_warns(self, validator: EconomicSenseValidator) -> None:
        hyp = HypothesisConfig(
            name="macd_fast_ge_slow",
            description="MACD fast not slower than slow",
            parameters={
                "macd_fast_period": 26,
                "macd_slow_period": 12,
                "macd_signal_period": 9,
            },
            confidence=0.6,
        )
        warnings = validator.validate(hyp)
        assert any("MACD fast period" in w and "slow period" in w for w in warnings)
        assert any("should be less than" in w for w in warnings)

    def test_macd_fast_lt_slow_no_warning(
        self, validator: EconomicSenseValidator
    ) -> None:
        hyp = HypothesisConfig(
            name="macd_fast_lt_slow",
            description="MACD fast slower than slow",
            parameters={
                "macd_fast_period": 12,
                "macd_slow_period": 26,
                "macd_signal_period": 9,
            },
            confidence=0.6,
        )
        warnings = validator.validate(hyp)
        assert not any("fast >= slow" in w for w in warnings)

    # ── Non-blocking contract ──────────────────────────────────────────────

    def test_never_raises(self, validator: EconomicSenseValidator) -> None:
        hyp = HypothesisConfig(
            name="garbage",
            description="Nonsense params",
            parameters={"rsi_period": "not_a_number"},
            confidence=0.6,
        )
        # Should not raise — invalid values are ignored or warned, never raise
        result = validator.validate(hyp)
        assert isinstance(result, list)
