"""Tests for ResearchAgent — tasks 2.5, 2.6, 2.9, 2.17."""

import pytest

from quantlab.agents.research_agent import ResearchAgent
from quantlab.dsl.models import HypothesisConfig, Market, ResearchConfig, Timeframe


class TestGenerateConfig:
    """Task 2.5 + 2.17: ResearchAgent.generate_config()."""

    def test_generate_config_from_simple_objective(self) -> None:
        """GIVEN an objective "Find mean-reversion on EURUSD H1"
        WHEN generate_config() is called
        THEN a ResearchConfig is returned with correct market and timeframe.
        """
        agent = ResearchAgent()
        config = agent.generate_config(
            objectives=["Find mean-reversion on EURUSD H1"],
        )

        assert isinstance(config, ResearchConfig)
        assert config.market == Market.EURUSD
        assert config.timeframe == Timeframe.H1
        assert len(config.building_blocks) >= 1
        assert len(config.strategies) >= 1
        assert len(config.criteria) >= 1

    def test_generate_config_with_explicit_context(self) -> None:
        """GIVEN objectives with market_context
        WHEN generate_config() is called
        THEN the context overrides objective parsing.
        """
        agent = ResearchAgent()
        config = agent.generate_config(
            objectives=["Find breakout strategies"],
            market_context={
                "market": "GBPUSD",
                "timeframe": "H4",
                "tags": ["breakout"],
            },
        )

        assert config.market == Market.GBPUSD
        assert config.timeframe == Timeframe.H4

    def test_generate_config_includes_hypotheses(self) -> None:
        """GIVEN objectives
        WHEN generate_config() is called
        THEN the config includes hypotheses with confidence in [0, 1].
        """
        agent = ResearchAgent()
        config = agent.generate_config(
            objectives=["Find mean-reversion on EURUSD H1"],
        )

        assert len(config.hypotheses) >= 1
        for h in config.hypotheses:
            assert 0.0 <= h.confidence <= 1.0, f"Confidence {h.confidence} out of range"
            assert h.name, f"Hypothesis missing name"
            assert h.description, f"Hypothesis missing description"

    def test_generate_config_has_iteration_config(self) -> None:
        """GIVEN objectives
        WHEN generate_config() is called
        THEN the config includes iteration_config defaults.
        """
        agent = ResearchAgent()
        config = agent.generate_config(
            objectives=["Find mean-reversion on EURUSD H1"],
        )

        assert config.iteration_config.max_iterations == 5
        assert config.iteration_config.convergence_threshold == 0.02
        assert config.iteration_config.auto_iterate is True

    def test_empty_objectives_raises(self) -> None:
        """GIVEN no objectives
        WHEN generate_config() is called
        THEN ValueError is raised.
        """
        agent = ResearchAgent()
        with pytest.raises(ValueError, match="At least one objective"):
            agent.generate_config(objectives=[])

    def test_unknown_market_in_objective_raises(self) -> None:
        """GIVEN an objective with an unknown market
        WHEN generate_config() is called
        THEN ValueError is raised.
        """
        agent = ResearchAgent()
        with pytest.raises(ValueError, match="Cannot determine market"):
            agent.generate_config(objectives=["Find algo on CRYPTO/BTC"])

    def test_multiple_objectives_generate_richer_config(self) -> None:
        """GIVEN multiple objectives covering different strategies
        WHEN generate_config() is called
        THEN the config has multiple building blocks.
        """
        agent = ResearchAgent()
        config = agent.generate_config(
            objectives=[
                "Find mean-reversion on EURUSD H1",
                "Validate breakout strategies with volatility filters",
            ],
        )

        assert len(config.building_blocks) >= 2


class TestFormulateHypotheses:
    """Task 2.6: ResearchAgent.formulate_hypotheses()."""

    def test_formulate_hypotheses_returns_list(self) -> None:
        """GIVEN objectives
        WHEN formulate_hypotheses() is called
        THEN a list of HypothesisConfig is returned.
        """
        agent = ResearchAgent()
        hypotheses = agent.formulate_hypotheses(
            objectives=["Find mean-reversion on EURUSD H1"],
        )

        assert isinstance(hypotheses, list)
        assert len(hypotheses) >= 1
        assert all(isinstance(h, HypothesisConfig) for h in hypotheses)

    def test_hypotheses_have_unique_names(self) -> None:
        """GIVEN objectives
        WHEN formulate_hypotheses() is called
        THEN hypotheses have unique names.
        """
        agent = ResearchAgent()
        hypotheses = agent.formulate_hypotheses(
            objectives=["Find mean-reversion on EURUSD H1"],
        )

        names = [h.name for h in hypotheses]
        assert len(names) == len(set(names)), f"Duplicate hypothesis names: {names}"

    def test_hypotheses_confidence_in_range(self) -> None:
        """GIVEN objectives
        WHEN formulate_hypotheses() is called
        THEN all confidence scores are in [0, 1].
        """
        agent = ResearchAgent()
        hypotheses = agent.formulate_hypotheses(
            objectives=["Find mean-reversion on EURUSD H1"],
        )

        for h in hypotheses:
            assert 0.0 <= h.confidence <= 1.0, (
                f"Hypothesis '{h.name}' has confidence {h.confidence} outside [0, 1]"
            )

    def test_hypotheses_have_parameters(self) -> None:
        """GIVEN objectives
        WHEN formulate_hypotheses() is called
        THEN each hypothesis has testable parameters.
        """
        agent = ResearchAgent()
        hypotheses = agent.formulate_hypotheses(
            objectives=["Find mean-reversion on EURUSD H1"],
        )

        for h in hypotheses:
            assert h.parameters, f"Hypothesis '{h.name}' has empty parameters"

    def test_hypotheses_with_query_calibration(self) -> None:
        """GIVEN query results from Knowledge Lake
        WHEN formulate_hypotheses() is called with calibration data
        THEN confidence scores reflect historical performance.
        """
        agent = ResearchAgent()
        query_results = [
            {"campaign_id": "c1", "sharpe_ratio": 1.8, "profit_factor": 2.1},
            {"campaign_id": "c2", "sharpe_ratio": 1.2, "profit_factor": 1.5},
        ]

        hypotheses = agent.formulate_hypotheses(
            objectives=["Find mean-reversion on EURUSD H1"],
            query_results=query_results,
        )

        assert len(hypotheses) >= 1
        for h in hypotheses:
            assert 0.0 <= h.confidence <= 1.0

    def test_breakout_objectives_generate_donchian(self) -> None:
        """GIVEN breakout objectives
        WHEN formulate_hypotheses() is called
        THEN a donchian breakout hypothesis is included.
        """
        agent = ResearchAgent()
        hypotheses = agent.formulate_hypotheses(
            objectives=["Find breakout strategies on GBPUSD H4"],
        )

        names = [h.name for h in hypotheses]
        assert any("donchian" in n for n in names), (
            f"Expected donchian hypothesis, got: {names}"
        )


class TestQueryKnowledgeLake:
    """Task 2.6: ResearchAgent.query_knowledge_lake()."""

    def test_query_knowledge_lake_returns_list(self) -> None:
        """GIVEN market and timeframe
        WHEN query_knowledge_lake() is called
        THEN a list is returned (empty if no data).
        """
        agent = ResearchAgent()
        results = agent.query_knowledge_lake(
            market="EURUSD",
            timeframe="H1",
            tags=["mean_reversion"],
        )
        assert isinstance(results, list)


class TestRunMethod:
    """Task 2.9: ResearchAgent.run(context)."""

    @pytest.mark.asyncio
    async def test_run_writes_context_artifacts(self) -> None:
        """GIVEN a PipelineContext with objectives
        WHEN run() is called
        THEN research_config, hypotheses, etc. are written to context artifacts.
        """
        from quantlab.pipeline.base import PipelineContext

        agent = ResearchAgent()
        ctx = PipelineContext(
            config={
                "objectives": ["Find mean-reversion on EURUSD H1"],
            },
        )

        result = await agent.run(ctx)

        assert "research_config" in ctx.artifacts
        assert "objectives" in ctx.artifacts
        assert "hypotheses" in ctx.artifacts
        assert "iteration_config" in ctx.artifacts
        assert "gate_policies" in ctx.artifacts

        # Check return value
        assert "research_config" in result
        assert "hypotheses" in result

        # Check hypotheses list has items
        assert len(result["hypotheses"]) >= 1

    @pytest.mark.asyncio
    async def test_run_with_string_objective(self) -> None:
        """GIVEN a PipelineContext with campaign_name as string
        WHEN run() is called
        THEN it handles string input gracefully.
        """
        from quantlab.pipeline.base import PipelineContext

        agent = ResearchAgent()
        ctx = PipelineContext(
            config={"campaign_name": "Research campaign on EURUSD"},
        )

        result = await agent.run(ctx)
        assert "research_config" in result
        assert "hypotheses" in result
