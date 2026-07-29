"""Integration tests for HypothesisBuilder stage, registry, and pipeline wiring."""

from __future__ import annotations

import pytest

from quantlab.pipeline.base import Stage
from quantlab.pipeline.registry import StageRegistry
from quantlab.pipeline.stages.agent_stages import HypothesisBuilderStage


class TestHypothesisBuilderStageContract:
    """Tests for the HypothesisBuilderStage ABC contract (S-7, S-9)."""

    def test_name(self) -> None:
        assert HypothesisBuilderStage.name == "hypothesis_builder"

    def test_requires(self) -> None:
        assert "research_config" in HypothesisBuilderStage.requires
        assert "hypotheses" in HypothesisBuilderStage.requires
        assert "objectives" in HypothesisBuilderStage.requires

    def test_provides(self) -> None:
        assert "building_blocks" in HypothesisBuilderStage.provides
        assert "strategies" in HypothesisBuilderStage.provides


class TestRegistryLookup:
    """Tests for hypothesis_builder registration in StageRegistry (S-7)."""

    def test_registry_returns_stage(self) -> None:
        registry = StageRegistry()
        cls = registry.get_stage_class("hypothesis_builder")
        assert cls is not None
        assert cls.name == "hypothesis_builder"

    def test_registry_in_list(self) -> None:
        registry = StageRegistry()
        names = registry.list_stage_names()
        assert "hypothesis_builder" in names

    def test_existing_stages_unaffected(self) -> None:
        registry = StageRegistry()
        for name in ["research", "research_llm", "builder", "statistics", "review"]:
            assert registry.get_stage_class(name) is not None

    def test_unknown_stage_returns_none(self) -> None:
        registry = StageRegistry()
        assert registry.get_stage_class("nonexistent") is None


class TestStageContractConformance:
    """Tests that the registered class conforms to Stage ABC."""

    def test_registered_class_is_stage_subclass(self) -> None:
        registry = StageRegistry()
        cls = registry.get_stage_class("hypothesis_builder")
        assert cls is not None
        assert issubclass(cls, Stage)

    def test_registered_class_has_execute(self) -> None:
        registry = StageRegistry()
        cls = registry.get_stage_class("hypothesis_builder")
        assert cls is not None
        assert hasattr(cls, "execute")
        import inspect
        assert not inspect.isabstract(cls)


class TestPipelineInsertion:
    """Tests that hypothesis_builder is inserted between research and builder."""

    def test_stage_order_in_docstring(self) -> None:
        """Verify the build_pipeline docstring reflects the new stage order."""
        from quantlab.agents.research_director import ResearchDirector
        doc = ResearchDirector.build_pipeline.__doc__ or ""
        assert "hypothesis_builder" in doc
        research_pos = doc.index("research")
        hyp_pos = doc.index("hypothesis_builder")
        builder_pos = doc.index("builder")
        assert research_pos < hyp_pos < builder_pos
