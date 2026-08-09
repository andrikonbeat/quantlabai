"""Tests for ResearchAgent capital-aware reasoning extensions."""

from __future__ import annotations

import pytest

from quantlab.agents.research_agent import ResearchAgent
from quantlab.dsl.models import HypothesisConfig


class TestCapitalConstraintsExtraction:
    def test_generate_config_injects_capital_constraints(self):
        agent = ResearchAgent()
        config = agent.generate_config(
            ["Find mean-reversion on EURUSD H1 with 100 USD capital"],
            capital_constraints={
                "max_drawdown": 0.12,
                "risk_per_trade_usd": 20.0,
                "instruments": ["EURUSD", "USDJPY"],
                "timeframe": "M15",
            },
        )
        assert any("tightened max drawdown" in (h.llm_rationale or "") for h in config.hypotheses)
        assert any("biased toward low-spread instruments" in (h.llm_rationale or "") for h in config.hypotheses)
        assert any("aligned to M15" in (h.llm_rationale or "") for h in config.hypotheses)
        assert any("risk per trade capped at $20.00" in (h.llm_rationale or "") for h in config.hypotheses)


class TestQueryKnowledgeLakeWithCapitalContext:
    def test_query_knowledge_lake_accepts_new_params(self):
        agent = ResearchAgent()
        results = agent.query_knowledge_lake(
            market="EURUSD",
            timeframe="H1",
            min_sharpe=1.0,
            limit=5,
        )
        assert isinstance(results, list)

    def test_extended_knowledge_query_with_capital_context(self):
        agent = ResearchAgent()
        results = agent._extended_knowledge_query(
            market="EURUSD",
            timeframe="H1",
            capital_constraints={"max_drawdown": 0.10},
        )
        assert isinstance(results, list)

    def test_extended_knowledge_query_without_capital_context(self):
        agent = ResearchAgent()
        results = agent._extended_knowledge_query(
            market="EURUSD",
            timeframe="H1",
        )
        assert isinstance(results, list)
