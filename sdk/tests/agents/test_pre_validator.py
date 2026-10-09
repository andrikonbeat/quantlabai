"""Tests for PreValidator (T9 task 3.2)."""

from __future__ import annotations

import pytest

from quantlab.dsl.models import HypothesisConfig


def _hyp(**overrides) -> HypothesisConfig:
    base = {
        "name": "mean_reversion_rsi_bb",
        "description": "RSI(14) < 30 long entry, take profit at middle band",
        "parameters": {"rsi_period": 14, "bb_deviation": 2.0, "direction": "LONG"},
        "expected_outcome": "Sharpe > 1.5",
        "confidence": 0.6,
    }
    base.update(overrides)
    return HypothesisConfig(**base)


class TestPreValidator:
    def test_clean_hypothesis_no_warnings(self) -> None:
        from quantlab.agents.pre_validator import PreValidator

        assert PreValidator().validate(_hyp()) == []

    def test_unknown_indicator_warns(self) -> None:
        from quantlab.agents.pre_validator import PreValidator

        warnings = PreValidator().validate(_hyp(parameters={"blargatron_period": 5}))
        assert any("blargatron" in w for w in warnings)

    def test_out_of_range_delegates_to_economic_validator(self) -> None:
        from quantlab.agents.pre_validator import PreValidator

        warnings = PreValidator().validate(_hyp(parameters={"rsi_period": 500}))
        assert any("out of range" in w for w in warnings)

    def test_empty_description_warns(self) -> None:
        from quantlab.agents.pre_validator import PreValidator

        warnings = PreValidator().validate(_hyp(description=""))
        assert any("description" in w for w in warnings)

    def test_invalid_direction_warns(self) -> None:
        from quantlab.agents.pre_validator import PreValidator

        warnings = PreValidator().validate(_hyp(parameters={"direction": "SIDEWAYS"}))
        assert any("direction" in w for w in warnings)

    def test_contradictory_direction_warns(self) -> None:
        from quantlab.agents.pre_validator import PreValidator

        warnings = PreValidator().validate(
            _hyp(
                description="go short when RSI overbought",
                parameters={"direction": "LONG"},
            )
        )
        assert any("direction" in w.lower() for w in warnings)

    def test_policy_off_skips(self) -> None:
        from quantlab.agents.pre_validator import PreValidator

        validator = PreValidator(validation_policy="off")
        assert validator.validate(_hyp(parameters={"blargatron_period": 5})) == []

    def test_policy_strict_raises(self) -> None:
        from quantlab.agents.pre_validator import PreValidator

        with pytest.raises(ValueError, match="blargatron"):
            PreValidator(validation_policy="strict").validate(
                _hyp(parameters={"blargatron_period": 5})
            )

    def test_policy_lenient_returns_warnings(self) -> None:
        from quantlab.agents.pre_validator import PreValidator

        warnings = PreValidator(validation_policy="lenient").validate(
            _hyp(parameters={"blargatron_period": 5})
        )
        assert len(warnings) == 1

    def test_invalid_policy_rejected(self) -> None:
        from quantlab.agents.pre_validator import PreValidator

        with pytest.raises(ValueError):
            PreValidator(validation_policy="sometimes")

    def test_missing_kb_degrades_gracefully(self) -> None:
        from unittest.mock import patch

        from quantlab.agents.pre_validator import PreValidator

        with patch(
            "quantlab.agents.pre_validator.SQXDocProvider", None
        ):
            # Indicator checks skipped; coherence checks still run
            warnings = PreValidator().validate(_hyp(description=""))
        assert any("description" in w for w in warnings)
