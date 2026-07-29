"""Tests for RefutationStage registration and pipeline wiring."""

from __future__ import annotations

from quantlab.pipeline.base import Stage
from quantlab.pipeline.registry import StageRegistry
from quantlab.pipeline.stages.agent_stages import RefutationStage


class TestRefutationStageContract:
    def test_name(self) -> None:
        assert RefutationStage.name == "refutation"

    def test_requires(self) -> None:
        assert "hypotheses" in RefutationStage.requires
        assert "building_blocks" in RefutationStage.requires
        assert "strategies" in RefutationStage.requires

    def test_provides(self) -> None:
        assert "falsation_results" in RefutationStage.provides


class TestRegistryLookup:
    def test_registry_returns_stage(self) -> None:
        registry = StageRegistry()
        cls = registry.get_stage_class("refutation")
        assert cls is not None
        assert cls.name == "refutation"

    def test_registry_in_list(self) -> None:
        registry = StageRegistry()
        names = registry.list_stage_names()
        assert "refutation" in names

    def test_registered_class_is_stage_subclass(self) -> None:
        registry = StageRegistry()
        cls = registry.get_stage_class("refutation")
        assert cls is not None
        assert issubclass(cls, Stage)

    def test_unknown_stage_returns_none(self) -> None:
        registry = StageRegistry()
        assert registry.get_stage_class("nonexistent") is None


class TestPipelineInsertion:
    def test_stage_order_in_docstring(self) -> None:
        import re
        from quantlab.agents.research_director import ResearchDirector
        doc = ResearchDirector.build_pipeline.__doc__ or ""
        assert "refutation" in doc
        names = re.findall(r"\bhypothesis_builder\b|\brefutation\b|\bbuilder\b", doc)
        hyp_pos = next(i for i, n in enumerate(names) if n == "hypothesis_builder")
        ref_pos = next(i for i, n in enumerate(names) if n == "refutation")
        builder_pos = next(i for i, n in enumerate(names) if n == "builder")
        assert hyp_pos < ref_pos < builder_pos
