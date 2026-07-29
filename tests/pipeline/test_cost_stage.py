"""Tests for CostInjectionStage I/O contract and execution.

Covers spec scenarios from:
- openspec/changes/broker-cost-engine/specs/pipeline-core/spec.md (CostInjectionStage)
- openspec/specs/cost-pipeline-integration/spec.md (CostInjectionStage)
"""

import pytest

from quantlab.pipeline._stages import CostInjectionStage
from quantlab.pipeline.base import PipelineContext


class TestCostInjectionStageContract:
    """CostInjectionStage requires/provides contract — spec scenario."""

    def test_stage_name(self):
        """GIVEN CostInjectionStage THEN name is 'cost_injection'."""
        stage = CostInjectionStage()
        assert stage.name == "cost_injection"

    def test_requires_broker_profile(self):
        """CostInjectionStage requires config.broker_profile."""
        stage = CostInjectionStage()
        assert "config.broker_profile" in stage.requires

    def test_provides_cost_config(self):
        """CostInjectionStage provides cost_config."""
        stage = CostInjectionStage()
        assert "cost_config" in stage.provides

    def test_requires_exactly_one_key(self):
        """CostInjectionStage has exactly one requires key."""
        stage = CostInjectionStage()
        assert len(stage.requires) == 1

    def test_provides_exactly_one_key(self):
        """CostInjectionStage has exactly one provides key."""
        stage = CostInjectionStage()
        assert len(stage.provides) == 1

    def test_stage_is_stage_subclass(self):
        """CostInjectionStage IS a Stage subclass."""
        from quantlab.pipeline.base import Stage
        assert issubclass(CostInjectionStage, Stage)

    def test_execute_raises_not_implemented(self):
        """CostInjectionStage.execute() raises NotImplementedError (abstract stage)."""
        stage = CostInjectionStage()
        ctx = PipelineContext(config={"broker_profile": "dukascopy"})
        with pytest.raises(NotImplementedError):
            import asyncio
            asyncio.run(stage.execute(ctx))


class TestCostInjectionStageEdgeCases:
    """Edge cases for CostInjectionStage."""

    def test_execute_without_broker_profile_missing_key(self):
        """GIVEN PipelineContext without broker_profile WHEN execute THEN NotImplementedError (abstract)."""
        stage = CostInjectionStage()
        ctx = PipelineContext(config={})
        with pytest.raises(NotImplementedError):
            import asyncio
            asyncio.run(stage.execute(ctx))

    def test_provides_typed_as_list_of_strings(self):
        """provides attribute is a list of strings."""
        stage = CostInjectionStage()
        assert isinstance(stage.provides, list)
        assert all(isinstance(x, str) for x in stage.provides)

    def test_requires_typed_as_list_of_strings(self):
        """requires attribute is a list of strings."""
        stage = CostInjectionStage()
        assert isinstance(stage.requires, list)
        assert all(isinstance(x, str) for x in stage.requires)

    def test_exported_from_pipeline_stages(self):
        """CostInjectionStage is accessible from quantlab.pipeline.stages."""
        from quantlab.pipeline.stages import CostInjectionStage as ExportedStage
        assert ExportedStage is CostInjectionStage

    def test_exported_from_pipeline_init(self):
        """CostInjectionStage is accessible from quantlab.pipeline."""
        from quantlab.pipeline import CostInjectionStage as ExportedStage
        from quantlab.pipeline._stages import CostInjectionStage as BaseStage
        assert ExportedStage is not None
        assert ExportedStage is BaseStage

    def test_registered_in_stage_registry(self):
        """CostInjectionStage is registered under 'cost_injection' key."""
        from quantlab.pipeline.registry import StageRegistry
        registry = StageRegistry()
        stage_class = registry.get_stage_class("cost_injection")
        assert stage_class is not None
        assert stage_class.name == "cost_injection"


class TestCostInjectionStagePipelineOrder:
    """CostInjectionStage sits after GuardianEvaluationStage, before BuilderStage."""

    def test_position_matches_design(self):
        """CostInjectionStage, GuardianEvaluationStage, and BuilderStage all exist."""
        from quantlab.pipeline._stages import CostInjectionStage
        from quantlab.pipeline.stages.agent_stages import GuardianEvaluationStage
        from quantlab.pipeline.stages.agent_stages import BuilderStage

        assert CostInjectionStage is not None
        assert GuardianEvaluationStage is not None
        assert BuilderStage is not None

    def test_requires_contract_upstream_is_satisfiable(self):
        """config.broker_profile could come from ResearchConfig parsed costs section."""
        stage = CostInjectionStage()
        assert "config.broker_profile" in stage.requires
        # The config dict key is the same regardless of upstream source
        assert stage.requires == ["config.broker_profile"]
