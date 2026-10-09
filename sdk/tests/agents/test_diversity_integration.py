"""Tests for DiversityEngine integration (T9 task 3.3)."""

from __future__ import annotations

import json


class TestFormulateDiversify:
    def test_default_off_preserves_behavior(self) -> None:
        from quantlab.agents.research_agent import ResearchAgent

        agent = ResearchAgent()
        base = agent.formulate_hypotheses(["mean reversion RSI"])
        again = agent.formulate_hypotheses(["mean reversion RSI"], diversify=False)
        assert [h.name for h in base] == [h.name for h in again]

    def test_diversify_adds_variants(self) -> None:
        from quantlab.agents.research_agent import ResearchAgent

        agent = ResearchAgent()
        base = agent.formulate_hypotheses(["mean reversion RSI"])
        diversified = agent.formulate_hypotheses(["mean reversion RSI"], diversify=True)
        base_names = {h.name for h in base}
        div_names = {h.name for h in diversified}
        assert base_names <= div_names
        assert len(diversified) > len(base)
        assert any("__var" in n for n in div_names)


class TestParseResponseDiversify:
    def _response(self) -> str:
        return json.dumps(
            {
                "campaign": "Test",
                "market": "EURUSD",
                "timeframe": "H1",
                "hypotheses": [
                    {
                        "name": "mean_reversion_rsi",
                        "description": "RSI mean reversion entry",
                        "parameters": {"rsi_period": 14},
                        "expected_outcome": "Sharpe > 1.5",
                        "confidence": 0.6,
                    }
                ],
            }
        )

    def test_default_off_preserves_behavior(self) -> None:
        from quantlab.agents.llm_research_agent import LLMResearchAgent

        agent = LLMResearchAgent()
        base = agent.parse_response(self._response())
        again = agent.parse_response(self._response(), diversify=False)
        assert [h.name for h in base.hypotheses] == [h.name for h in again.hypotheses]

    def test_diversify_adds_variants(self) -> None:
        from quantlab.agents.llm_research_agent import LLMResearchAgent

        agent = LLMResearchAgent()
        config = agent.parse_response(self._response(), diversify=True)
        names = [h.name for h in config.hypotheses]
        assert "mean_reversion_rsi" in names
        assert any("__var" in n for n in names)
