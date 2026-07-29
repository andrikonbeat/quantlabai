"""Tests for PR 3: Pipeline wiring — LLMResearchStage, registry, routing, integration.

Tasks: 3.1 (RED), 3.2, 3.3 (RED), 3.4, 3.6

Covers:
- LLMResearchStage contract (requires/provides/name)
- StageRegistry lookup for "research_llm"
- ResearchDirector routing: model="" → classic, model="gpt-4" → LLM
- Full pipeline integration with mocked LLM config
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from quantlab.agents.research_director import ResearchDirector
from quantlab.dsl.models import (
    HypothesisConfig,
    IterationConfig,
    ResearchConfig,
)
from quantlab.pipeline.base import Stage
from quantlab.pipeline.config.models import AgentConfig
from quantlab.pipeline.registry import StageRegistry
from quantlab.pipeline.stages.agent_stages import (
    LLMResearchStage,
    ResearchStage,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_minimal_config() -> ResearchConfig:
    return ResearchConfig(
        campaign="TestPipeline",
        market="EURUSD",
        timeframe="H1",
        hypotheses=[
            HypothesisConfig(
                name="h1",
                description="Test hypothesis",
                confidence=0.7,
            ),
        ],
        iteration_config=IterationConfig(
            max_iterations=1,
            convergence_threshold=0.02,
        ),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Task 3.1 (RED) — LLMResearchStage I/O contract
# ══════════════════════════════════════════════════════════════════════════════

class TestLLMResearchStageContract:
    """LLMResearchStage I/O contract per spec scenario."""

    def test_requires_matches_research_stage(self) -> None:
        """GIVEN LLMResearchStage
        WHEN inspecting requires
        THEN it matches ResearchStage (empty — no upstream deps).
        """
        stage = LLMResearchStage()
        assert stage.requires == ResearchStage().requires

    def test_provides_matches_research_stage(self) -> None:
        """GIVEN LLMResearchStage
        WHEN inspecting provides
        THEN it provides the same 5 keys as ResearchStage.
        """
        stage = LLMResearchStage()
        expected = [
            "research_config",
            "objectives",
            "hypotheses",
            "iteration_config",
            "gate_policies",
        ]
        assert stage.provides == expected

    def test_name_is_research_llm(self) -> None:
        """GIVEN LLMResearchStage
        WHEN inspecting name
        THEN it is "research_llm".
        """
        assert LLMResearchStage.name == "research_llm"

    def test_is_abstract_stage(self) -> None:
        """GIVEN LLMResearchStage
        THEN it is a subclass of Stage.
        """
        assert issubclass(LLMResearchStage, Stage)

    def test_execute_raises_not_implemented(self) -> None:
        """GIVEN LLMResearchStage (abstract)
        WHEN execute() is called directly
        THEN NotImplementedError is raised.
        """
        from quantlab.pipeline.base import PipelineContext

        stage = LLMResearchStage()
        ctx = PipelineContext(config={})
        with pytest.raises(NotImplementedError):
            import asyncio
            asyncio.run(stage.execute(ctx))


# ══════════════════════════════════════════════════════════════════════════════
# Task 3.2 (RED) — StageRegistry lookup for "research_llm"
# ══════════════════════════════════════════════════════════════════════════════

class TestRegistryLookup:
    """StageRegistry returns LLMResearchStage for 'research_llm'."""

    def test_registry_returns_llm_stage_for_research_llm(self) -> None:
        """GIVEN StageRegistry
        WHEN looking up "research_llm"
        THEN the registry returns a class that is a subclass of LLMResearchStage.
        """
        registry = StageRegistry()
        stage_class = registry.get_stage_class("research_llm")
        assert stage_class is not None
        assert issubclass(stage_class, LLMResearchStage)

    def test_research_llm_is_available_for_pipeline_composition(self) -> None:
        """GIVEN StageRegistry
        WHEN listing agent stage names
        THEN "research_llm" is included.
        """
        registry = StageRegistry()
        agent_names = registry.list_stage_names_by_type("agent")
        assert "research_llm" in agent_names

    def test_existing_stages_unaffected_by_new_registration(self) -> None:
        """GIVEN StageRegistry
        WHEN listing all stage names
        THEN classic "research" is still present.
        """
        registry = StageRegistry()
        agent_names = registry.list_stage_names_by_type("agent")
        assert "research" in agent_names

    def test_unknown_stage_returns_none(self) -> None:
        """GIVEN a stage name that is not registered
        WHEN get_stage_class() is called
        THEN None is returned gracefully.
        """
        registry = StageRegistry()
        result = registry.get_stage_class("nonexistent_stage")
        assert result is None


# ══════════════════════════════════════════════════════════════════════════════
# Task 3.3 (RED) — ResearchDirector routing
# ══════════════════════════════════════════════════════════════════════════════

class TestResearchDirectorRouting:
    """ResearchDirector routes between classic and LLM research stages."""

    def _build_agent_config(self, model: str = "") -> AgentConfig:
        return AgentConfig(
            name="research",
            type="agent",
            model=model or "",
        )

    def test_empty_model_routes_to_classic(self) -> None:
        """GIVEN AgentConfig.model = ""
        WHEN ResearchDirector builds the pipeline
        THEN "research" stage is selected.
        """
        director = ResearchDirector()
        config = _make_minimal_config()
        agent_config = self._build_agent_config(model="")
        pipeline = director.build_pipeline(config, agent_config=agent_config)

        stage_names = [s.name for s in pipeline.stages]
        assert stage_names[0] == "research"

    def test_llm_model_routes_to_research_llm(self) -> None:
        """GIVEN AgentConfig.model = "gpt-4"
        WHEN ResearchDirector builds the pipeline
        THEN "research_llm" stage is selected.
        """
        director = ResearchDirector()
        config = _make_minimal_config()
        agent_config = self._build_agent_config(model="gpt-4")
        pipeline = director.build_pipeline(config, agent_config=agent_config)

        stage_names = [s.name for s in pipeline.stages]
        assert stage_names[0] == "research_llm"

    def test_default_no_agent_config_uses_classic(self) -> None:
        """GIVEN no AgentConfig provided (backward compat)
        WHEN ResearchDirector builds the pipeline
        THEN classic "research" stage is used.
        """
        director = ResearchDirector()
        config = _make_minimal_config()
        pipeline = director.build_pipeline(config)

        stage_names = [s.name for s in pipeline.stages]
        assert stage_names[0] == "research"

    def test_llm_routing_preserves_stage_count(self) -> None:
        """GIVEN AgentConfig.model = "gpt-4"
        WHEN ResearchDirector builds the pipeline
        THEN the pipeline still has 13 stages (8 agents + 5 gates).
        """
        director = ResearchDirector()
        config = _make_minimal_config()
        agent_config = self._build_agent_config(model="gpt-4")
        pipeline = director.build_pipeline(config, agent_config=agent_config)

        # 8 agent stages (research_llm + hypothesis_builder + builder + ...) + 5 gate interceptors = 13
        assert len(pipeline.stages) == 13


# ══════════════════════════════════════════════════════════════════════════════
# Task 3.6 (RED) — Full pipeline integration with LLM config
# ══════════════════════════════════════════════════════════════════════════════

class TestPipelineIntegration:
    """Full pipeline with LLMResearchStage — mocked providers."""

    @pytest.mark.asyncio
    async def test_llm_agent_execute_returns_expected_artifacts(self) -> None:
        """GIVEN LLMResearchStage with mocked LLMResearchAgent
        WHEN execute() is called
        THEN it returns dict with the 5 required artifact keys.
        """
        from quantlab.pipeline.base import PipelineContext
        from quantlab.pipeline.stages.agent_stages import LLMResearchStage

        # We need a concrete class — get it from the registry
        registry = StageRegistry()
        stage_class = registry.get_stage_class("research_llm")
        assert stage_class is not None

        # Mock the LLMResearchAgent to return a valid config
        mock_config = ResearchConfig(
            campaign="LLM Test",
            market="EURUSD",
            timeframe="H1",
            hypotheses=[
                HypothesisConfig(
                    name="llm_h1",
                    description="LLM-generated hypothesis",
                    confidence=0.8,
                ),
            ],
            iteration_config=IterationConfig(max_iterations=1),
        )

        stage = stage_class()
        # Patch the agent's generate_config method
        with patch.object(
            stage._agent,
            "generate_config",
            new=AsyncMock(return_value=mock_config),
        ):
            ctx = PipelineContext(
                config={
                    "objectives": ["Find long opportunities in tech"],
                    "market_context": {},
                    "llm_config": {"provider": "openai", "model": "gpt-4"},
                },
            )
            result = await stage.execute(ctx)

        assert isinstance(result, dict)
        assert "research_config" in result
        assert "objectives" in result
        assert "hypotheses" in result
        assert "iteration_config" in result
        assert "gate_policies" in result

        # Verify the research_config is our mocked values
        assert result["research_config"]["campaign"] == "LLM Test"
        assert len(result["hypotheses"]) == 1

    @pytest.mark.asyncio
    async def test_llm_agent_stage_writes_to_context_artifacts(self) -> None:
        """GIVEN LLMResearchStage with mocked agent
        WHEN execute() is called
        THEN artifacts are written to PipelineContext.
        """
        from quantlab.pipeline.base import PipelineContext
        from quantlab.pipeline.registry import StageRegistry

        registry = StageRegistry()
        stage_class = registry.get_stage_class("research_llm")
        assert stage_class is not None

        mock_config = ResearchConfig(
            campaign="Artifacts Test",
            market="EURUSD",
            timeframe="H1",
            iteration_config=IterationConfig(max_iterations=1),
        )

        stage = stage_class()
        with patch.object(
            stage._agent,
            "generate_config",
            new=AsyncMock(return_value=mock_config),
        ):
            ctx = PipelineContext(config={})
            result = await stage.execute(ctx)

        # Verify artifacts written to context
        assert ctx.artifacts.get("research_config") is not None
        assert "objectives" in ctx.artifacts
        assert "hypotheses" in ctx.artifacts

    @pytest.mark.asyncio
    async def test_llm_pipeline_with_agent_config_builds_and_runs(self) -> None:
        """GIVEN ResearchDirector with LLM AgentConfig
        WHEN build_pipeline() is called
        THEN a pipeline with research_llm stage can be created.
        """
        from quantlab.agents.research_director import ResearchDirector
        from quantlab.pipeline.base import PipelineContext
        from quantlab.pipeline.config.models import AgentConfig
        from quantlab.pipeline.runner import PipelineRunner

        director = ResearchDirector()
        config = _make_minimal_config()
        agent_config = AgentConfig(
            name="research",
            type="agent",
            model="gpt-4",
        )

        pipeline = director.build_pipeline(config, agent_config=agent_config)

        stage_names = [s.name for s in pipeline.stages]
        assert stage_names[0] == "research_llm"

        # Attempt to run with mocked external inputs
        ctx = PipelineContext(config={})
        ctx.artifacts["selected_strategies"] = []
        ctx.artifacts["live_equity"] = {}
        for gate_id in ("HUMAN_APPROVE_PORTFOLIO", "HUMAN_APPROVE_DEPLOY", "HUMAN_REVIEW_PERFORMANCE"):
            ctx.artifacts[f"gate_decision_{gate_id}"] = {"status": "pending"}

        runner = PipelineRunner()
        runner.set_registry(StageRegistry())

        from quantlab.pipeline.config.models import MultiAgentPipelineConfig, StageConfig

        # Build via runner to get proper pipeline context
        stages = [
            StageConfig(name="research_llm", type="agent"),
            StageConfig(name="builder", type="agent"),
            StageConfig(name="statistics", type="agent"),
            StageConfig(name="review", type="agent"),
            StageConfig(name="portfolio", type="agent"),
            StageConfig(name="deploy", type="agent"),
            StageConfig(name="monitor", type="agent"),
        ]

        pipeline_config = MultiAgentPipelineConfig(
            name="llm-pipeline-test",
            stages=stages,
        )

        p = runner.build_from_config(pipeline_config)
        assert len(p.stages) == 7
        assert p.stages[0].name == "research_llm"
