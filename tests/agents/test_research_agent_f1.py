"""F1 integration tests for ResearchAgent wiring."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from quantlab.agents.economic_sense.validator import EconomicSenseValidator
from quantlab.agents.research_agent import ResearchAgent
from quantlab.agents.tag_calibrator import TagCalibrator
from quantlab.dsl.models import HypothesisConfig


class TestHypothesisConfigValidationWarnings:
    """HypothesisConfig must accept validation_warnings field."""

    def test_default_empty_warnings(self) -> None:
        hyp = HypothesisConfig(
            name="test",
            description="test",
            parameters={},
            confidence=0.5,
        )
        assert hyp.validation_warnings == []

    def test_explicit_warnings_preserved(self) -> None:
        hyp = HypothesisConfig(
            name="test",
            description="test",
            parameters={},
            confidence=0.5,
            validation_warnings=["warn1", "warn2"],
        )
        assert hyp.validation_warnings == ["warn1", "warn2"]


class TestResearchAgentF1Wiring:
    """ResearchAgent wires EconomicSenseValidator and TagCalibrator."""

    @pytest.fixture()
    def agent(self) -> ResearchAgent:
        return ResearchAgent()

    def test_formulate_attaches_economic_warnings(
        self, agent: ResearchAgent
    ) -> None:
        objectives = ["mean-reversion"]
        # Monkeypatch validator to return a deterministic warning so we can
        # verify the wiring without relying on hardcoded hypothesis params.
        with patch(
            "quantlab.agents.research_agent.EconomicSenseValidator"
        ) as MockValidator:
            instance = MockValidator.return_value
            instance.validate.return_value = ["RSI period 500 is out of range [2, 200]"]
            hypotheses = agent.formulate_hypotheses(objectives)
        assert any(h.validation_warnings for h in hypotheses)

    def test_formulate_adjusts_confidence_via_tag_calibrator(
        self, agent: ResearchAgent
    ) -> None:
        objectives = ["mean-reversion"]
        # Provide query results so TagCalibrator has data to work with
        query_results = [
            {
                "campaign_id": "c1",
                "sharpe_ratio": 1.5,
                "win_rate": 0.55,
                "tags": ["mean_reversion"],
            },
            {
                "campaign_id": "c2",
                "sharpe_ratio": 1.2,
                "win_rate": 0.50,
                "tags": ["mean_reversion"],
            },
        ]
        hypotheses = agent.formulate_hypotheses(objectives, query_results)
        # Confidence should be adjusted (not equal to the raw base values)
        confidences = [h.confidence for h in hypotheses]
        assert any(c != 0.5 for c in confidences)

    def test_validator_and_calibrator_wired_together(
        self, agent: ResearchAgent
    ) -> None:
        objectives = ["trend following"]
        query_results = [
            {
                "campaign_id": "c1",
                "sharpe_ratio": 1.8,
                "win_rate": 0.60,
                "tags": ["trend"],
            },
        ]
        hypotheses = agent.formulate_hypotheses(objectives, query_results)
        assert hypotheses
        for hyp in hypotheses:
            assert isinstance(hyp.validation_warnings, list)
            assert 0.0 <= hyp.confidence <= 1.0
