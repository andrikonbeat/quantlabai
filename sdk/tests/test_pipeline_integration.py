"""Integration and regression tests for PR 1 — tasks 1.16 and 1.17.

Task 1.16: Load minimal pipeline YAML, build pipeline, verify 17 stages in correct order.
Task 1.17: Regression test: basic 9-stage SQX pipeline executes without new stages.
"""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from quantlab.pipeline.base import Pipeline, PipelineContext, Stage
from quantlab.pipeline.config.models import (
    GateConfig,
    MultiAgentPipelineConfig,
    StageConfig,
)
from quantlab.pipeline.errors import ContractValidationError
from quantlab.pipeline.runner import PipelineRunner
from quantlab.pipeline.registry import StageRegistry
from quantlab.pipeline.stages.gate_interceptor import (
    FallbackPolicy,
    GateContext,
    GateDecision,
    GateAction,
    GateInterceptorStage,
)


# ─── Task 1.16: Integration test ───────────────────────────────────────────────


class TestBuildFromConfig:
    """Integration test: load minimal pipeline YAML, build, verify stages."""

    def _make_registry(self) -> StageRegistry:
        return StageRegistry()

    def test_build_pipeline_with_all_stages(self) -> None:
        """GIVEN a PipelineConfig with all stage types in order
        WHEN PipelineRunner.build_from_config() is called
        THEN all stages are created with expected names.
        """
        stages_config = [
            StageConfig(name="validate", type="builtin"),
            StageConfig(name="translate", type="builtin"),
            StageConfig(name="daemon_start", type="builtin"),
            StageConfig(name="load_config", type="builtin"),
            StageConfig(name="run_campaign", type="builtin"),
            StageConfig(name="poll_campaign", type="builtin"),
            StageConfig(name="export", type="builtin"),
            StageConfig(name="read", type="builtin"),
            StageConfig(name="compute_stats", type="builtin"),
            StageConfig(name="knowledge_store", type="builtin"),
            StageConfig(name="report", type="builtin"),
            StageConfig(name="research", type="agent"),
            StageConfig(name="builder", type="agent"),
            StageConfig(name="statistics", type="agent"),
            StageConfig(name="review", type="agent"),
            StageConfig(name="portfolio", type="agent"),
            StageConfig(name="gate", type="gate",
                       config={"gate_id": "HUMAN_APPROVE_PORTFOLIO"}),
            StageConfig(name="deploy", type="agent"),
            StageConfig(name="monitor", type="agent"),
        ]

        config = MultiAgentPipelineConfig(
            name="full-pipeline",
            stages=stages_config,
        )

        runner = PipelineRunner()
        runner.set_registry(self._make_registry())
        pipeline = runner.build_from_config(config)

        stage_names = [s.name for s in pipeline.stages]
        expected = [
            "validate", "translate", "daemon_start", "load_config",
            "run_campaign", "poll_campaign", "export", "read",
            "compute_stats", "knowledge_store", "report",
            "research", "builder", "statistics", "review",
            "portfolio", "gate", "deploy", "monitor",
        ]
        assert stage_names == expected

    def test_build_minimal_config(self) -> None:
        """GIVEN a minimal pipeline config with only agent stages
        WHEN build_from_config() is called
        THEN the pipeline is built with those stages only.
        """
        stages_config = [
            StageConfig(name="research", type="agent"),
            StageConfig(name="builder", type="agent"),
            StageConfig(name="statistics", type="agent"),
            StageConfig(name="review", type="agent"),
            StageConfig(name="portfolio", type="agent"),
            StageConfig(name="deploy", type="agent"),
            StageConfig(name="monitor", type="agent"),
        ]

        config = MultiAgentPipelineConfig(
            name="minimal-agent",
            stages=stages_config,
        )

        runner = PipelineRunner()
        runner.set_registry(self._make_registry())
        pipeline = runner.build_from_config(config)

        stage_names = [s.name for s in pipeline.stages]
        assert len(stage_names) == 7
        assert stage_names == [
            "research", "builder", "statistics", "review",
            "portfolio", "deploy", "monitor",
        ]

    def test_build_from_yaml(self) -> None:
        """GIVEN a YAML config with nested pipeline section
        WHEN MultiAgentPipelineConfig.load() is called
        THEN the config is parsed correctly.
        """
        config_data = {
            "pipeline": {
                "name": "yaml-pipeline",
                "description": "Test from YAML",
                "version": "1.0.0",
                "stages": [
                    {"name": "research", "type": "agent"},
                    {"name": "builder", "type": "agent"},
                    {"name": "statistics", "type": "agent"},
                ],
            },
            "memory": {"enabled": True, "topic_prefix": "quantlab/test"},
            "risk": {"max_portfolio_drawdown": 0.15},
        }

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            yaml.dump(config_data, f)
            tmp_path = f.name

        try:
            config = MultiAgentPipelineConfig.load(tmp_path)
            assert config.name == "yaml-pipeline"
            assert len(config.stages) == 3
            assert config.memory.topic_prefix == "quantlab/test"
            assert config.risk.max_portfolio_drawdown == 0.15
        finally:
            os.unlink(tmp_path)

    def test_build_with_gates_from_config(self) -> None:
        """GIVEN a config with gates defined
        WHEN build_from_config() is called
        THEN gate stages are injected after their 'after_stage' positions.
        """
        stages_config = [
            StageConfig(name="research", type="agent"),
            StageConfig(name="builder", type="agent"),
            StageConfig(name="statistics", type="agent"),
            StageConfig(name="review", type="agent"),
            StageConfig(name="portfolio", type="agent"),
        ]

        gates_config = [
            GateConfig(
                name="HUMAN_REVIEW_OBJECTIVES",
                gate_id="HUMAN_REVIEW_OBJECTIVES",
                after_stage="research",
                timeout_hours=24,
                fallback="CONTINUE",
            ),
            GateConfig(
                name="HUMAN_APPROVE_PORTFOLIO",
                gate_id="HUMAN_APPROVE_PORTFOLIO",
                after_stage="portfolio",
                timeout_hours=12,
                fallback="ABORT",
            ),
        ]

        config = MultiAgentPipelineConfig(
            name="gated-pipeline",
            stages=stages_config,
            gates=gates_config,
        )

        runner = PipelineRunner()
        runner.set_registry(self._make_registry())
        pipeline = runner.build_from_config(config)

        stage_names = [s.name for s in pipeline.stages]
        assert "gate_HUMAN_REVIEW_OBJECTIVES" in stage_names
        assert "gate_HUMAN_APPROVE_PORTFOLIO" in stage_names

        # Verify gate positions
        gate1_idx = stage_names.index("gate_HUMAN_REVIEW_OBJECTIVES")
        assert gate1_idx == 1  # After research (idx 0)

        gate2_idx = stage_names.index("gate_HUMAN_APPROVE_PORTFOLIO")
        assert gate2_idx == 6  # After portfolio (idx 5)

    def test_config_defaults_applied(self) -> None:
        """GIVEN an empty config
        WHEN MultiAgentPipelineConfig() is created
        THEN default values are applied.
        """
        config = MultiAgentPipelineConfig(name="defaults-test")
        assert config.version == "1.0.0"
        assert config.memory.enabled is True
        assert config.memory.topic_prefix == "quantlab/agent"
        assert config.risk.max_portfolio_drawdown == 0.15
        assert config.risk.kelly_fraction_cap == 0.25


class TestPipelineRunnerIntegration:
    """Integration tests for PipelineRunner with gate injection."""

    @pytest.mark.asyncio
    async def test_runner_with_gate_execution(self) -> None:
        """GIVEN a PipelineRunner with a registered gate
        WHEN run_with_gates() is called
        THEN the gate executes after its configured stage.
        """
        runner = PipelineRunner()

        gate = GateInterceptorStage()
        gate.name = "test_gate"
        gate.gate_id = "TEST_GATE"
        gate.timeout_hours = 24.0
        gate.fallback = FallbackPolicy.CONTINUE

        async def mock_callback(ctx: GateContext) -> GateDecision:
            return GateDecision(
                gate_id="TEST_GATE",
                action=GateAction.APPROVED,
                reason="All good",
                decided_by="test",
            )

        gate.set_callback(mock_callback)
        runner.register_gate("stage_a", gate)

        pipeline = Pipeline(name="gate-test")
        pipeline.stages = [
            _make_stage_simple("stage_a", [], ["output_a"]),
            _make_stage_simple("stage_b", ["output_a"], ["final"]),
        ]

        ctx = PipelineContext(config={})
        result = await runner.run_with_gates(pipeline, ctx)

        assert result.is_successful
        assert len(result.stages) == 3  # stage_a + gate + stage_b
        assert result.stages[0].stage_name == "stage_a"
        assert result.stages[0].status.value == "completed"
        assert result.stages[1].stage_name == "test_gate"
        assert result.stages[1].status.value == "completed"
        assert result.stages[2].stage_name == "stage_b"
        assert result.stages[2].status.value == "completed"

    @pytest.mark.asyncio
    async def test_runner_contract_validation(self) -> None:
        """GIVEN a pipeline with contract violations
        WHEN run() is called
        THEN ContractValidationError is raised before any stage executes.
        """
        runner = PipelineRunner()

        pipeline = Pipeline(name="bad-contract")
        pipeline.stages = [
            _make_stage_simple("alpha", [], ["x"]),
            _make_stage_simple("beta", ["nonexistent"], ["y"]),
        ]

        ctx = PipelineContext(config={})
        with pytest.raises(ContractValidationError):
            await runner.run(pipeline, ctx)


# ─── Task 1.17: Backward compatibility regression test ─────────────────────────


class TestBackwardCompatibility:
    """Regression test: basic SQX pipeline executes without new stages."""

    @pytest.mark.asyncio
    async def test_basic_pipeline_executes_without_new_stages(self) -> None:
        """GIVEN a pipeline with only the original SQX stages
        WHEN run() is called
        THEN all stages execute.
        """
        runner = PipelineRunner()

        pipeline = Pipeline(name="sqx-classic")
        pipeline.stages = [
            _make_stage_simple("validate", [], ["validated_config"]),
            _make_stage_simple("translate", ["validated_config"], ["cfx_bytes", "cfx_path"]),
            _make_stage_simple("export", ["cfx_path"], ["export_paths"]),
            _make_stage_simple("read", ["export_paths"], ["parsed_results"]),
            _make_stage_simple("compute_stats", ["parsed_results"], ["statistics"]),
            _make_stage_simple("knowledge_store", ["parsed_results", "statistics"], ["artifact_paths"]),
            _make_stage_simple("report", ["parsed_results", "statistics"], ["report_path"]),
        ]

        ctx = PipelineContext(config={"dry_run": True})
        result = await runner.run(pipeline, ctx)

        assert result.is_successful
        assert len(result.stages) == 7
        for stage_result in result.stages:
            assert stage_result.status.value == "completed"

    @pytest.mark.asyncio
    async def test_simple_pipeline_execution(self) -> None:
        """GIVEN a minimal pipeline
        WHEN run() is called
        THEN it executes successfully.
        """
        runner = PipelineRunner()

        pipeline = Pipeline(name="sqx-minimal")
        pipeline.stages = [
            _make_stage_simple("validate", [], ["validated_config"]),
            _make_stage_simple("translate", ["validated_config"], ["cfx_bytes"]),
            _make_stage_simple("read", ["cfx_bytes"], ["parsed_results"]),
        ]

        ctx = PipelineContext(config={"dry_run": True})
        result = await runner.run(pipeline, ctx)

        assert result.is_successful
        assert len(result.stages) == 3

    @pytest.mark.asyncio
    async def test_pipeline_error_skips_remaining_stages(self) -> None:
        """GIVEN a pipeline where one stage fails
        WHEN run() is called
        THEN remaining stages are SKIPPED.
        """
        runner = PipelineRunner()

        async def fail_stage(ctx: PipelineContext) -> dict:
            raise RuntimeError("Simulated failure")

        stage_a = _make_stage_simple("stage_a", [], ["x"])
        stage_b = _make_stage_simple("stage_b", ["x"], ["y"])
        stage_b.execute = fail_stage  # type: ignore[method-assign]
        stage_c = _make_stage_simple("stage_c", ["y"], ["z"])

        pipeline = Pipeline(name="error-test")
        pipeline.stages = [stage_a, stage_b, stage_c]

        ctx = PipelineContext(config={})
        result = await runner.run(pipeline, ctx)

        assert not result.is_successful
        assert result.stages[0].status.value == "completed"
        assert result.stages[1].status.value == "failed"
        assert result.stages[2].status.value == "skipped"

    def test_stage_registry_backward_compat(self) -> None:
        """GIVEN the StageRegistry
        WHEN querying for original SQX stage names
        THEN they still resolve correctly.
        """
        reg = StageRegistry()

        original_stages = [
            "validate", "translate", "daemon_start", "load_config",
            "run_campaign", "poll_campaign", "campaign", "export",
            "read", "compute_stats", "knowledge_store", "report",
        ]
        for name in original_stages:
            stage_class = reg.get_stage_class(name)
            assert stage_class is not None, f"Original stage '{name}' not found"

        agent_stages = [
            "research", "builder", "statistics", "review",
            "portfolio", "deploy", "monitor",
        ]
        for name in agent_stages:
            stage_class = reg.get_stage_class(name)
            assert stage_class is not None, f"Agent stage '{name}' not found"


def _make_stage_simple(
    stage_name: str,
    stage_requires: list[str],
    stage_provides: list[str],
) -> Stage:
    """Helper to create a concrete test stage.
    
    Uses a dynamically created subclass to avoid Python 3.14 ABC
    instantiation restrictions.
    """
    class _ConcreteStage(Stage):
        name = stage_name
        requires = stage_requires
        provides = stage_provides
        
        async def execute(self, ctx: PipelineContext) -> dict:
            return {"stage": self.name, "status": "ok"}
    
    return _ConcreteStage()
