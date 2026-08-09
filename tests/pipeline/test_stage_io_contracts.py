"""Task 4.8: stage I/O contracts for the full-campaign flow (REQ-26/REQ-34).

Verifies the requires/provides contracts of the Phase 4 stage adapters and
that the registry resolves them by name:

- ``execution_monitor`` → ExecutionMonitorStage (requires [], provides
  monitor_result) — the live-ops monitoring adapter.
- ``archiver`` → ArchiverStage (requires guardian_state, provides
  archive_result) — the maintenance/replacement runbook adapter (REQ-33).
- The post-deploy chain demo → archive → guardian_evaluate keeps the stage
  contract chain satisfied (deployment_result → demo_result → archive_bundle).

Strict TDD: written first — RED until Phase 4 wiring exists.
"""

from __future__ import annotations

from quantlab.pipeline.base import Stage
from quantlab.pipeline.registry import StageRegistry
from quantlab.pipeline.stages.agent_stages import GuardianEvaluationAgentStage
from quantlab.pipeline.stages.archiver_stage import ArchiverStage
from quantlab.pipeline.stages.archive_stage import ArchiveStage
from quantlab.pipeline.stages.demo_stage import DemoStage
from quantlab.pipeline.stages.execution_monitor_stage import ExecutionMonitorStage


class TestExecutionMonitorStageContract:
    """REQ-26: execution_monitor I/O contract."""

    def test_name_is_execution_monitor(self) -> None:
        assert ExecutionMonitorStage.name == "execution_monitor"

    def test_requires_is_empty(self) -> None:
        assert ExecutionMonitorStage.requires == []

    def test_provides_monitor_result(self) -> None:
        assert ExecutionMonitorStage.provides == ["monitor_result"]

    def test_is_a_stage(self) -> None:
        assert issubclass(ExecutionMonitorStage, Stage)


class TestArchiverStageContract:
    """REQ-33: archiver I/O contract."""

    def test_name_is_archiver(self) -> None:
        assert ArchiverStage.name == "archiver"

    def test_requires_guardian_state(self) -> None:
        assert ArchiverStage.requires == ["guardian_state"]

    def test_provides_archive_result(self) -> None:
        assert ArchiverStage.provides == ["archive_result"]

    def test_is_a_stage(self) -> None:
        assert issubclass(ArchiverStage, Stage)


class TestPostDeployChainContract:
    """REQ-34/REQ-37: demo → archive → guardian_evaluate I/O chain."""

    def test_demo_requires_deployment_result_provides_demo_result(self) -> None:
        assert DemoStage.requires == ["deployment_result"]
        assert DemoStage.provides == ["demo_result"]

    def test_archive_requires_demo_result_provides_archive_bundle(self) -> None:
        assert ArchiveStage.requires == ["demo_result"]
        assert ArchiveStage.provides == ["archive_bundle"]

    def test_guardian_evaluate_requires_research_config(self) -> None:
        assert GuardianEvaluationAgentStage.requires == ["research_config"]
        assert "guardian_state" in GuardianEvaluationAgentStage.provides

    def test_chain_keys_flow(self) -> None:
        """GIVEN the stage contracts in pipeline order
        THEN each stage's requires are provided upstream: deployment_result →
        demo_result → archive_bundle (full stage chain contract scenario).
        """
        provided = {"research_config", "deployment_result"}
        assert DemoStage.requires == ["deployment_result"] and set(DemoStage.requires) <= provided
        provided |= set(DemoStage.provides)
        assert set(ArchiveStage.requires) <= provided
        provided |= set(ArchiveStage.provides)
        assert set(GuardianEvaluationAgentStage.requires) <= provided


class TestRegistryRegistersLiveOpsStages:
    """Task 4.2: execution_monitor and archiver are registered by name."""

    def test_registry_resolves_execution_monitor(self) -> None:
        registry = StageRegistry()
        stage_class = registry.get_stage_class("execution_monitor")
        assert stage_class is not None
        assert issubclass(stage_class, ExecutionMonitorStage)

    def test_registry_resolves_archiver(self) -> None:
        registry = StageRegistry()
        stage_class = registry.get_stage_class("archiver")
        assert stage_class is not None
        assert issubclass(stage_class, ArchiverStage)

    def test_registry_still_resolves_existing_live_ops_stages(self) -> None:
        """GIVEN the registry after the new registrations
        THEN demo/archive/guardian_evaluate remain resolvable.
        """
        registry = StageRegistry()
        assert registry.get_stage_class("demo") is not None
        assert registry.get_stage_class("archive") is not None
        assert registry.get_stage_class("guardian_evaluate") is not None
