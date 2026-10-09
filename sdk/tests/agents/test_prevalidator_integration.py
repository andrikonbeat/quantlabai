"""Tests for PreValidator integration in generate_config (T9 task 3.4)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from quantlab.agents.research_agent import ResearchAgent
from quantlab.dsl.models import HypothesisConfig


def _bad_hyp() -> HypothesisConfig:
    return HypothesisConfig(
        name="bad_rsi",
        description="RSI mean reversion entry",
        parameters={"rsi_period": 500, "blargatron_mode": 1},
        expected_outcome="Sharpe > 1.5",
        confidence=0.6,
    )


class TestGenerateConfigValidationPolicy:
    def test_default_lenient_attaches_without_raising(self) -> None:
        agent = ResearchAgent()
        with patch.object(
            ResearchAgent, "formulate_hypotheses", return_value=[_bad_hyp()]
        ):
            config = agent.generate_config(["momentum on EURUSD H1"])
        assert len(config.hypotheses) == 1
        warnings = config.hypotheses[0].validation_warnings
        assert any("out of range" in w for w in warnings)
        assert any("blargatron" in w for w in warnings)

    def test_lenient_dedupes_economic_warnings(self) -> None:
        agent = ResearchAgent()
        hyp = _bad_hyp()
        hyp.validation_warnings = ["RSI period 500 is out of range [2, 200]"]
        with patch.object(
            ResearchAgent, "formulate_hypotheses", return_value=[hyp]
        ):
            config = agent.generate_config(["momentum on EURUSD H1"])
        warnings = config.hypotheses[0].validation_warnings
        assert len(warnings) == len(set(warnings))

    def test_strict_raises(self) -> None:
        agent = ResearchAgent()
        with (
            patch.object(
                ResearchAgent, "formulate_hypotheses", return_value=[_bad_hyp()]
            ),
            pytest.raises(ValueError, match="blargatron|out of range"),
        ):
            agent.generate_config(["momentum on EURUSD H1"], validation_policy="strict")

    def test_off_skips_pre_validation(self) -> None:
        agent = ResearchAgent()
        with patch.object(
            ResearchAgent, "formulate_hypotheses", return_value=[_bad_hyp()]
        ):
            config = agent.generate_config(["momentum on EURUSD H1"], validation_policy="off")
        # No pre-validator warnings attached (formulate mock bypasses economic too)
        assert config.hypotheses[0].validation_warnings == []

    def test_invalid_policy_rejected(self) -> None:
        agent = ResearchAgent()
        with pytest.raises(ValueError):
            agent.generate_config(["momentum"], validation_policy="sometimes")

    def test_clean_config_unchanged(self) -> None:
        agent = ResearchAgent()
        config = agent.generate_config(["mean reversion RSI on EURUSD H1"])
        assert len(config.hypotheses) >= 1
        # Real formulated hypotheses are structurally clean
        for hyp in config.hypotheses:
            assert isinstance(hyp.validation_warnings, list)
