"""REQ-37: segment-preserving flow-integrity invariant (PR1, WU-1).

The REQ-37 invariant is SEGMENT-PRESERVING, not just presence-checking: the
orchestrated pipeline MUST keep the canonical 14 phases present, the
post-deploy boundary ordered (deploy < demo < archive < live_ops < monitor),
and the loop tail ordered (monitor → guardian_evaluate → [retester] →
[optimizer]). ``assert_flow_segments`` fails closed with
``FlowIntegrityError`` on any drop, reorder, or wrong live-ops mapping, and
treats ``retester``/``optimizer`` as optional only when the caller marks them
optional (config-derived, ADR-1).

Strict TDD: RED — written before ``assert_flow_segments`` existed.
"""

from __future__ import annotations

import pytest

from quantlab.campaign.flow import (
    STAGE_FOR_PHASE,
    FlowIntegrityError,
    assert_flow_segments,
)


def _orchestrated_stages() -> list[str]:
    """Stage-name sequence of the orchestrated pipeline (retest+optimize set).

    Mirrors ``ResearchDirector.build_pipeline(orchestrated=True)``: the
    post-archive loop tail runs monitor → guardian_evaluate → retester →
    optimizer after the live_ops stage.
    """
    return [
        "research",
        "hypothesis_builder",
        "builder",
        "config_review",
        "dispatch",
        "portfolio",
        "compile",
        "deploy",
        "demo",
        "archive",
        "live_ops",
        "monitor",
        "guardian_evaluate",
        "retester",
        "optimizer",
    ]


class TestFlowSegmentsPresence:
    """REQ-37 scenario 1: a dropped phase aborts the invariant."""

    def test_full_segment_sequence_passes(self) -> None:
        """GIVEN every canonical phase mapped to an orchestrated stage
        THEN assert_flow_segments completes without error."""
        assert_flow_segments(_orchestrated_stages())  # must not raise

    def test_phase_drop_raises_flow_integrity_error(self) -> None:
        """GIVEN a pipeline missing the compile stage
        WHEN the segment invariant runs
        THEN it raises FlowIntegrityError naming the dropped phase."""
        dropped = [s for s in _orchestrated_stages() if s != "compile"]
        with pytest.raises(FlowIntegrityError) as exc:
            assert_flow_segments(dropped)
        assert "compile" in str(exc.value)

    def test_research_llm_satisfies_research(self) -> None:
        """GIVEN the pipeline routes research through the LLM stage
        THEN "research_llm" satisfies the "research" phase — no drop error."""
        llm = [
            "research_llm" if s == "research" else s
            for s in _orchestrated_stages()
        ]
        assert_flow_segments(llm)  # must not raise


class TestFlowSegmentsTailOrder:
    """REQ-37 scenario 3: a reordered segment fails validation."""

    def test_guardian_evaluate_before_monitor_raises(self) -> None:
        """GIVEN the loop tail reordered (guardian_evaluate before monitor)
        WHEN the segment invariant runs
        THEN it raises FlowIntegrityError naming the reorder."""
        stages = _orchestrated_stages()
        i, j = stages.index("monitor"), stages.index("guardian_evaluate")
        stages[i], stages[j] = stages[j], stages[i]
        with pytest.raises(FlowIntegrityError) as exc:
            assert_flow_segments(stages)
        assert "monitor" in str(exc.value) or "guardian_evaluate" in str(exc.value)

    def test_boundary_reorder_live_ops_before_archive_raises(self) -> None:
        """GIVEN the post-deploy boundary reordered (live_ops before archive)
        WHEN the segment invariant runs
        THEN it raises FlowIntegrityError (deploy<demo<archive<live_ops<monitor)."""
        stages = _orchestrated_stages()
        i, j = stages.index("archive"), stages.index("live_ops")
        stages[i], stages[j] = stages[j], stages[i]
        with pytest.raises(FlowIntegrityError):
            assert_flow_segments(stages)


class TestFlowSegmentsOptionalTail:
    """REQ-37 scenario 4: conditional loop-tail segments (ADR-1)."""

    def test_configured_retester_dropped_raises(self) -> None:
        """GIVEN retest configured (retester NOT optional) and its stage dropped
        WHEN the segment invariant runs
        THEN it raises FlowIntegrityError — the configured tail must survive."""
        stages = [s for s in _orchestrated_stages() if s != "retester"]
        with pytest.raises(FlowIntegrityError) as exc:
            assert_flow_segments(stages)
        assert "retest" in str(exc.value)

    def test_optional_tail_without_blocks_passes(self) -> None:
        """GIVEN retest/optimize unconfigured (marked optional)
        WHEN the pipeline lacks retester and optimizer
        THEN the invariant passes — the tail is monitor → guardian_evaluate."""
        stages = [
            s for s in _orchestrated_stages()
            if s not in ("retester", "optimizer")
        ]
        assert_flow_segments(stages, optional_phases=("retester", "optimizer"))

    def test_optional_optimizer_alone_passes(self) -> None:
        """GIVEN only optimize unconfigured
        WHEN the pipeline lacks optimizer but keeps retester
        THEN the invariant passes with only optimizer optional."""
        stages = [s for s in _orchestrated_stages() if s != "optimizer"]
        assert_flow_segments(stages, optional_phases=("optimizer",))


class TestLiveOpsStageMapping:
    """REQ-37 scenario 5: live-ops maps to the real live_ops stage."""

    def test_stage_for_phase_live_ops_maps_to_live_ops(self) -> None:
        """WHEN STAGE_FOR_PHASE["live-ops"] is resolved
        THEN it maps to the real "live_ops" stage (not guardian_evaluate)."""
        assert STAGE_FOR_PHASE["live-ops"] == "live_ops"

    def test_live_ops_stage_is_required_by_segments(self) -> None:
        """GIVEN the pipeline drops the live_ops stage
        THEN the segment invariant fails — live-ops is a required segment."""
        stages = [s for s in _orchestrated_stages() if s != "live_ops"]
        with pytest.raises(FlowIntegrityError) as exc:
            assert_flow_segments(stages)
        assert "live-ops" in str(exc.value)


class TestRealOrchestratedPipeline:
    """The invariant holds against the real orchestrated pipeline."""

    def test_real_full_pipeline_passes_segments(self) -> None:
        """GIVEN the real orchestrated pipeline with retest+optimize blocks
        THEN assert_flow_segments passes with nothing optional."""
        from quantlab.agents.research_director import ResearchDirector
        from quantlab.dsl.models import (
            IterationConfig,
            OptimizeBlock,
            ResearchConfig,
            RetestBlock,
        )

        cfg = ResearchConfig(
            campaign="SegPipe",
            market="EURUSD",
            timeframe="H1",
            iteration_config=IterationConfig(max_iterations=1),
            retest=RetestBlock(strategy_id="S1", databanks=["EURUSD_H1"]),
            optimize=OptimizeBlock(strategy_id="S1", databanks=["EURUSD_H1"]),
        )
        pipeline = ResearchDirector().build_pipeline(cfg, orchestrated=True)
        assert_flow_segments([s.name for s in pipeline.stages])

    def test_real_pipeline_without_blocks_passes_optional_tail(self) -> None:
        """GIVEN the real orchestrated pipeline without retest/optimize blocks
        THEN assert_flow_segments passes when both tail stages are optional."""
        from quantlab.agents.research_director import ResearchDirector
        from quantlab.dsl.models import IterationConfig, ResearchConfig

        cfg = ResearchConfig(
            campaign="SegPipeOpt",
            market="EURUSD",
            timeframe="H1",
            iteration_config=IterationConfig(max_iterations=1),
        )
        pipeline = ResearchDirector().build_pipeline(cfg, orchestrated=True)
        assert_flow_segments(
            [s.name for s in pipeline.stages],
            optional_phases=("retester", "optimizer"),
        )
