"""E2E: enhanced research pipeline yields >=1 accepted strategy (T9 task 5.2).

Exercises the T9 wiring end to end without network: ResearchAgent with
diversification + pre-validation, then HypothesisBuilder in rule mode.
"""

from __future__ import annotations


class TestEnhancedPipelineEndToEnd:
    def test_pipeline_produces_accepted_strategy(self) -> None:
        import asyncio

        from quantlab.agents.hypothesis_builder import HypothesisBuilder
        from quantlab.agents.research_agent import ResearchAgent

        agent = ResearchAgent()
        config = agent.generate_config(
            ["trend following breakout on EURUSD H1"],
            market_context={"market": "EURUSD", "timeframe": "H1"},
        )
        assert len(config.hypotheses) >= 1

        builder = HypothesisBuilder(mode="rule")
        blocks, strategies = asyncio.run(
            builder.build(
                config.hypotheses,
                market_context={"market": "EURUSD", "timeframe": "H1"},
            )
        )
        assert len(blocks) >= 1
        assert len(strategies) >= 1

    def test_pipeline_with_diversification(self) -> None:
        import asyncio

        from quantlab.agents.hypothesis_builder import HypothesisBuilder
        from quantlab.agents.research_agent import ResearchAgent

        agent = ResearchAgent()
        hypotheses = agent.formulate_hypotheses(
            ["mean reversion RSI on EURUSD H1"], diversify=True
        )
        builder = HypothesisBuilder(mode="rule")
        blocks, strategies = asyncio.run(builder.build(hypotheses))
        assert len(strategies) >= 1
        # Diversified variants also build
        assert any("__var" in h.name for h in hypotheses)
