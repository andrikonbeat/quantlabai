"""Canonical pipeline counts integrity tests (G5).

Pins the canonical stage counts per design D8 (full-campaign-lifecycle delta):
code is authoritative — ``build_pipeline`` yields 16 non-orchestrated entries
(11 agent stages + 5 gates), 25 orchestrated (17 agent stages + 8 gates), and
27 with retest/optimize configured (19 agent stages + 8 gates). The research
stage must be first. Also pins the pipeline-core + custom-project-generator
deltas: ``StageRegistry.lookup`` rejects unregistered stages with
``RegistryError`` and resolves the registered ``custom_project`` stage (G2
dependency — registration only; wiring lands in U7).

Strict TDD: written first — RED until the registry lookup contract and
``custom_project`` registration exist.
"""

from __future__ import annotations

import pytest

from quantlab.agents.research_director import ResearchDirector
from quantlab.dsl.models import (
    IterationConfig,
    OptimizeBlock,
    ResearchConfig,
    RetestBlock,
)
from quantlab.pipeline.base import Stage
from quantlab.pipeline.registry import StageRegistry


def _cfg(retest=None, optimize=None) -> ResearchConfig:
    return ResearchConfig(
        campaign="CountsPipe",
        market="EURUSD",
        timeframe="H1",
        iteration_config=IterationConfig(max_iterations=1),
        retest=retest,
        optimize=optimize,
    )


def _stage_names(pipeline) -> list[str]:
    return [s.name for s in pipeline.stages]


class TestCanonicalCounts:
    """D8 / full-campaign-lifecycle: 16 / 25 / 27 entries per mode."""

    def test_non_orchestrated_counts_16(self) -> None:
        """GIVEN the default (non-orchestrated) build
        THEN the pipeline has 16 entries: 11 agent stages + 5 gates.
        """
        pipeline = ResearchDirector().build_pipeline(_cfg())
        names = _stage_names(pipeline)
        agents = [n for n in names if not n.startswith("gate_")]
        gates = [n for n in names if n.startswith("gate_")]
        assert len(names) == 16, f"Expected 16, got {len(names)}: {names}"
        assert len(agents) == 11, f"Expected 11 agent stages, got {len(agents)}: {agents}"
        assert len(gates) == 5, f"Expected 5 gates, got {len(gates)}: {gates}"

    def test_orchestrated_counts_25(self) -> None:
        """GIVEN the orchestrated build (no retest/optimize blocks)
        THEN the pipeline has 25 entries: 17 agent stages + 8 gates.
        """
        pipeline = ResearchDirector().build_pipeline(_cfg(), orchestrated=True)
        names = _stage_names(pipeline)
        agents = [n for n in names if not n.startswith("gate_")]
        gates = [n for n in names if n.startswith("gate_")]
        assert len(names) == 25, f"Expected 25, got {len(names)}: {names}"
        assert len(agents) == 17, f"Expected 17 agent stages, got {len(agents)}: {agents}"
        assert len(gates) == 8, f"Expected 8 gates, got {len(gates)}: {gates}"

    def test_orchestrated_with_retest_optimize_counts_27(self) -> None:
        """GIVEN the orchestrated build with retest and optimize blocks
        THEN the pipeline has 27 entries: 19 agent stages + 8 gates.
        """
        retest = RetestBlock(strategy_id="S1", databanks=["EURUSD_H1"])
        optimize = OptimizeBlock(strategy_id="S1", databanks=["EURUSD_H1"])
        pipeline = ResearchDirector().build_pipeline(
            _cfg(retest=retest, optimize=optimize), orchestrated=True
        )
        names = _stage_names(pipeline)
        agents = [n for n in names if not n.startswith("gate_")]
        gates = [n for n in names if n.startswith("gate_")]
        assert len(names) == 27, f"Expected 27, got {len(names)}: {names}"
        assert len(agents) == 19, f"Expected 19 agent stages, got {len(agents)}: {agents}"
        assert len(gates) == 8, f"Expected 8 gates, got {len(gates)}: {gates}"


class TestResearchFirst:
    """research-agent delta: research is the first agent stage."""

    def test_research_is_first_agent_stage_non_orchestrated(self) -> None:
        """GIVEN the non-orchestrated pipeline
        THEN the first stage is the research stage.
        """
        names = _stage_names(ResearchDirector().build_pipeline(_cfg()))
        assert names[0] in ("research", "research_llm"), f"First stage: {names[0]}"

    def test_research_is_first_agent_stage_orchestrated(self) -> None:
        """GIVEN the orchestrated pipeline
        THEN the first stage is the research stage.
        """
        names = _stage_names(
            ResearchDirector().build_pipeline(_cfg(), orchestrated=True)
        )
        assert names[0] in ("research", "research_llm"), f"First stage: {names[0]}"


class TestRegistryLookupContract:
    """pipeline-core delta: lookup() rejects unregistered stages; G2 dependency
    resolves custom_project after registration."""

    def test_unregistered_stage_lookup_raises_registry_error(self) -> None:
        """GIVEN a stage name absent from the registry
        WHEN StageRegistry.lookup() is called
        THEN RegistryError is raised (fail closed, no silent None).
        """
        from quantlab.pipeline.registry import RegistryError

        registry = StageRegistry()
        with pytest.raises(RegistryError):
            registry.lookup("definitely_not_a_registered_stage")

    def test_custom_project_lookup_resolves_after_registration(self) -> None:
        """GIVEN the updated registry (custom_project registered)
        WHEN StageRegistry.lookup("custom_project") is called
        THEN the custom project stage class is returned (G2 dependency — this
        slice only registers the stage; builder wiring lands in U7).
        """
        registry = StageRegistry()
        stage_class = registry.lookup("custom_project")
        assert issubclass(stage_class, Stage)

    def test_lookup_agrees_with_get_stage_class_for_registered_names(self) -> None:
        """GIVEN a stage name registered in the registry
        WHEN lookup() and get_stage_class() are both called
        THEN both APIs resolve to the same stage class (registry is the
        authoritative source of truth; no divergence between the two paths).
        """
        registry = StageRegistry()
        for name in ("research", "research_llm", "builder", "custom_project"):
            assert registry.lookup(name) is registry.get_stage_class(name), name

    def test_custom_project_in_agent_stage_enumeration(self) -> None:
        """GIVEN the updated registry
        WHEN agent stage names are enumerated
        THEN "custom_project" is included (matches what build_pipeline can
        instantiate — registry, not doc counts, is the source of truth).
        """
        registry = StageRegistry()
        agent_names = registry.list_stage_names_by_type("agent")
        assert "custom_project" in agent_names