"""Unit tests for PipelineRunner.validate_contracts() — task 1.15.

Verifies:
    - Valid pipeline contract passes validation
    - Mismatched requires/provides raises ContractValidationError
    - Error includes missing keys and stage names
"""

import pytest

from quantlab.pipeline.base import Pipeline, PipelineContext, Stage
from quantlab.pipeline.errors import ContractValidationError
from quantlab.pipeline.runner import PipelineRunner


class TestValidateContracts:
    """Tests for PipelineRunner.validate_contracts()."""

    def test_valid_pipeline_passes(self) -> None:
        """GIVEN a correctly wired pipeline
        WHEN validate_contracts() is called
        THEN it passes without error.
        """
        pipeline = Pipeline(name="test-valid")
        pipeline.stages = [
            _make_stage("stage_a", [], ["output_a", "output_b"]),
            _make_stage("stage_b", ["output_a"], ["output_c"]),
            _make_stage("stage_c", ["output_b", "output_c"], ["final"]),
        ]

        runner = PipelineRunner()
        runner.validate_contracts(pipeline)

    def test_valid_with_empty_requires(self) -> None:
        """GIVEN a pipeline where first stage has empty requires
        WHEN validate_contracts() is called
        THEN it passes.
        """
        pipeline = Pipeline(name="test-empty-req")
        pipeline.stages = [
            _make_stage("first", [], ["x"]),
            _make_stage("second", ["x"], ["y"]),
        ]

        runner = PipelineRunner()
        runner.validate_contracts(pipeline)

    def test_missing_key_raises_error(self) -> None:
        """GIVEN a pipeline where a stage requires a key not provided
        WHEN validate_contracts() is called
        THEN ContractValidationError is raised with missing key details.
        """
        pipeline = Pipeline(name="test-missing")
        pipeline.stages = [
            _make_stage("builder", [], ["cfx_bytes"]),
            _make_stage("statistics", ["export_paths"], ["statistics"]),
        ]

        runner = PipelineRunner()
        with pytest.raises(ContractValidationError) as excinfo:
            runner.validate_contracts(pipeline)

        error = excinfo.value
        assert "statistics" in str(error) or "export_paths" in str(error)
        missing = error.missing_keys
        assert "statistics" in missing
        assert "export_paths" in missing["statistics"]

    def test_multiple_missing_keys(self) -> None:
        """GIVEN a pipeline where a stage depends on multiple missing keys
        WHEN validate_contracts() is called
        THEN error lists all missing keys.
        """
        pipeline = Pipeline(name="test-multi-missing")
        pipeline.stages = [
            _make_stage("start", [], []),
            _make_stage("needy", ["alpha", "beta", "gamma"], ["result"]),
        ]

        runner = PipelineRunner()
        with pytest.raises(ContractValidationError) as excinfo:
            runner.validate_contracts(pipeline)

        error = excinfo.value
        needy_missing = error.missing_keys.get("needy", [])
        assert "alpha" in needy_missing
        assert "beta" in needy_missing
        assert "gamma" in needy_missing

    def test_chain_dependency_satisfied(self) -> None:
        """GIVEN a 3-stage chain where each stage reads from prior provides
        WHEN validate_contracts() is called
        THEN it passes.
        """
        pipeline = Pipeline(name="test-chain")
        pipeline.stages = [
            _make_stage("a", [], ["x"]),
            _make_stage("b", ["x"], ["y"]),
            _make_stage("c", ["y"], ["z"]),
        ]

        runner = PipelineRunner()
        runner.validate_contracts(pipeline)

    def test_accumulates_provides_across_stages(self) -> None:
        """GIVEN a pipeline where a later stage depends on a key provided
        by an early stage (not the immediate predecessor)
        WHEN validate_contracts() is called
        THEN it passes because provides accumulate.
        """
        pipeline = Pipeline(name="test-accumulate")
        pipeline.stages = [
            _make_stage("first", [], ["initial_data"]),
            _make_stage("second", ["initial_data"], ["intermediate"]),
            _make_stage("third", ["initial_data", "intermediate"], ["final"]),
        ]

        runner = PipelineRunner()
        runner.validate_contracts(pipeline)

    def test_agent_stage_chain_satisfied(self) -> None:
        """GIVEN a pipeline with stages matching the multi-agent chain
        WHEN validate_contracts() is called
        THEN it passes.
        """
        pipeline = Pipeline(name="test-agent-chain")
        pipeline.stages = [
            _make_stage("research", [], ["research_config", "objectives", "hypotheses"]),
            _make_stage("builder", ["research_config"], ["cfx_bytes", "campaign_id", "export_paths"]),
            _make_stage("statistics", ["export_paths"], ["statistics", "aggregate_stats", "monte_carlo_bands"]),
            _make_stage("review", ["statistics", "aggregate_stats", "monte_carlo_bands"],
                       ["review_decision", "iteration_proposal"]),
            _make_stage("gate",
                       [],
                       ["gate_decision_HUMAN_APPROVE_PORTFOLIO"]),
            _make_stage("portfolio", ["review_decision", "gate_decision_HUMAN_APPROVE_PORTFOLIO"],
                       ["portfolio_cfx", "portfolio_result"]),
        ]

        runner = PipelineRunner()
        runner.validate_contracts(pipeline)

    def test_error_has_stage_names(self) -> None:
        """GIVEN a mismatched pipeline
        WHEN validate_contracts() is called
        THEN the error includes stage_names.
        """
        pipeline = Pipeline(name="test-stage-names")
        pipeline.stages = [
            _make_stage("alpha", [], ["x"]),
            _make_stage("beta", ["missing_key"], ["y"]),
        ]

        runner = PipelineRunner()
        with pytest.raises(ContractValidationError) as excinfo:
            runner.validate_contracts(pipeline)

        assert "beta" in excinfo.value.stage_names


def _make_stage(
    stage_name: str,
    stage_requires: list[str],
    stage_provides: list[str],
) -> Stage:
    """Helper to create a concrete stage for contract testing.
    
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
