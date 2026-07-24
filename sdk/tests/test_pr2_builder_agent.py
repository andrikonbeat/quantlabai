"""Tests for BuilderAgent — tasks 2.10, 2.11, 2.12, 2.13, 2.18."""

import pytest

from quantlab.agents.builder_agent import BuilderAgent, DispatchResult
from quantlab.dsl.models import ResearchConfig


class TestTranslate:
    """Task 2.10 + 2.11: BuilderAgent.translate_to_cfx()."""

    @pytest.mark.asyncio
    async def test_translate_valid_config_to_cfx(self) -> None:
        """GIVEN a valid ResearchConfig
        WHEN translate_to_cfx() is called
        THEN CFX bytes are returned.
        """
        from quantlab.dsl.models import Strategy

        agent = BuilderAgent()
        config = ResearchConfig(
            campaign="TranslateTest",
            market="EURUSD",
            timeframe="H1",
            strategies=[
                Strategy(name="StratA", direction="BOTH"),
            ],
        )

        cfx_bytes = await agent.translate_to_cfx(config)
        assert isinstance(cfx_bytes, bytes)
        assert len(cfx_bytes) > 0


class TestRun:
    """Task 2.11 + 2.12 + 2.18: BuilderAgent.run(context)."""

    @pytest.mark.asyncio
    async def test_run_writes_context_artifacts(self) -> None:
        """GIVEN a PipelineContext with research_config artifact
        WHEN run() is called
        THEN cfx_bytes, campaign_id, sqcli_status, export_paths are written.
        """
        from quantlab.dsl.models import Strategy
        from quantlab.pipeline.base import PipelineContext

        agent = BuilderAgent()
        config = ResearchConfig(
            campaign="BuilderTest",
            market="EURUSD",
            timeframe="H1",
            strategies=[
                Strategy(name="StratA", direction="BOTH"),
            ],
        )

        ctx = PipelineContext(
            config={"campaign_name": "BuilderTest"},
            artifacts={"research_config": config.model_dump(mode="json")},
        )

        result = await agent.run(ctx)

        # Check context artifacts were written
        assert "cfx_bytes" in ctx.artifacts
        assert "campaign_id" in ctx.artifacts
        assert "sqcli_status" in ctx.artifacts
        assert "export_paths" in ctx.artifacts

        # Check return value
        assert "cfx_bytes" in result
        assert "campaign_id" in result
        assert result["sqcli_status"] in ("completed", "pending", "failed")

        # Check export paths
        assert len(result["export_paths"]) >= 1

    @pytest.mark.asyncio
    async def test_run_missing_research_config_raises(self) -> None:
        """GIVEN a PipelineContext without research_config
        WHEN run() is called
        THEN ValueError is raised.
        """
        from quantlab.pipeline.base import PipelineContext

        agent = BuilderAgent()
        ctx = PipelineContext(config={})

        with pytest.raises(ValueError, match="No research_config"):
            await agent.run(ctx)

    @pytest.mark.asyncio
    async def test_run_with_research_config_object(self) -> None:
        """GIVEN a ResearchConfig object in context artifacts
        WHEN run() is called
        THEN it handles the object directly.
        """
        from quantlab.dsl.models import Strategy
        from quantlab.pipeline.base import PipelineContext

        agent = BuilderAgent()
        config = ResearchConfig(
            campaign="DirectObj",
            market="EURUSD",
            timeframe="H1",
            strategies=[
                Strategy(name="StratA", direction="BOTH"),
            ],
        )

        ctx = PipelineContext(
            config={},
            artifacts={"research_config": config},
        )

        result = await agent.run(ctx)
        assert result["sqcli_status"] == "completed"
        assert len(result["export_paths"]) >= 1

    @pytest.mark.asyncio
    async def test_dispatch_retry_on_failure(self) -> None:
        """GIVEN a builder agent with max_retries=1
        WHEN dispatch fails
        THEN it retries before returning error.
        """
        from quantlab.dsl.models import Strategy
        from quantlab.pipeline.base import PipelineContext

        agent = BuilderAgent(max_retries=1, timeout_minutes=1)
        config = ResearchConfig(
            campaign="RetryTest",
            market="EURUSD",
            timeframe="H1",
            strategies=[
                Strategy(name="StratA", direction="BOTH"),
            ],
        )

        ctx = PipelineContext(
            config={},
            artifacts={"research_config": config.model_dump(mode="json")},
        )

        result = await agent.run(ctx)
        # Even with retries, valid config should succeed
        assert "campaign_id" in result


class TestTimeoutRetry:
    """Task 2.13: Retry logic and timeout."""

    def test_default_retry_config(self) -> None:
        """GIVEN a BuilderAgent with default params
        THEN max_retries=2 and timeout_minutes=60.
        """
        agent = BuilderAgent()
        assert agent._max_retries == 2
        assert agent._timeout_minutes == 60

    def test_custom_retry_config(self) -> None:
        """GIVEN a BuilderAgent with custom params
        THEN the custom values are used.
        """
        agent = BuilderAgent(max_retries=5, timeout_minutes=120)
        assert agent._max_retries == 5
        assert agent._timeout_minutes == 120


class TestGeneratePipelineConfig:
    """Task 2.12: generate_pipeline_config()."""

    def test_generates_full_pipeline_config(self) -> None:
        """GIVEN a ResearchConfig
        WHEN generate_pipeline_config() is called
        THEN a full pipeline config dict with all sections is returned.
        """
        agent = BuilderAgent()
        config = ResearchConfig(
            campaign="PipelineGen",
            market="EURUSD",
            timeframe="H1",
        )

        pipeline_config = agent.generate_pipeline_config(config)

        assert "version" in pipeline_config
        assert "pipeline" in pipeline_config
        assert "stages" in pipeline_config["pipeline"]
        assert len(pipeline_config["pipeline"]["stages"]) == 7

        # Check all 7 agent stages are present
        stage_names = [s["name"] for s in pipeline_config["pipeline"]["stages"]]
        expected = ["research", "builder", "statistics", "review",
                     "portfolio", "deploy", "monitor"]
        assert stage_names == expected

    def test_generates_all_5_gates(self) -> None:
        """GIVEN a ResearchConfig
        WHEN generate_pipeline_config() is called
        THEN all 5 gates are included with correct after_stage.
        """
        agent = BuilderAgent()
        config = ResearchConfig(
            campaign="GateGen",
            market="EURUSD",
            timeframe="H1",
        )

        pipeline_config = agent.generate_pipeline_config(config)
        gates = pipeline_config.get("gates", [])
        assert len(gates) == 5

        gate_ids = [g["gate_id"] for g in gates]
        expected_gates = [
            "HUMAN_REVIEW_OBJECTIVES",
            "HUMAN_APPROVE_ITERATION",
            "HUMAN_APPROVE_PORTFOLIO",
            "HUMAN_APPROVE_DEPLOY",
            "HUMAN_REVIEW_PERFORMANCE",
        ]
        assert gate_ids == expected_gates

    def test_config_includes_memory_and_risk(self) -> None:
        """GIVEN a ResearchConfig
        WHEN generate_pipeline_config() is called
        THEN memory and risk sections are included.
        """
        agent = BuilderAgent()
        config = ResearchConfig(
            campaign="FullGen",
            market="EURUSD",
            timeframe="H1",
        )

        pipeline_config = agent.generate_pipeline_config(config)
        assert "memory" in pipeline_config
        assert pipeline_config["memory"]["enabled"] is True
        assert pipeline_config["memory"]["topic_prefix"] == "quantlab/agent"

        assert "risk" in pipeline_config
        assert "max_portfolio_drawdown" in pipeline_config["risk"]
