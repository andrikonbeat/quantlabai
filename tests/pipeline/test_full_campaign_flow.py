"""Task 4.8: full campaign flow — the 14 ordered phases (REQ-37).

Verifies that the orchestrated ``ResearchDirector.build_pipeline`` covers all
14 canonical lifecycle phases (research → hypothesis → config → review →
dispatch → monitor → retest → optimize → portfolio → compile → deploy → demo →
archive → live-ops), that the flow never stops at optimize, and that the
post-deploy boundary runs demo → archive before the post-archive live-ops
loop (monitor → guardian_evaluate → retester → optimizer, per design).

Strict TDD: written first — RED until Phase 4 wiring exists.
"""

from __future__ import annotations

from quantlab.agents.research_director import ResearchDirector
from quantlab.campaign.flow import (
    PHASES,
    STAGE_FOR_PHASE,
    assert_flow,
    missing_flow_stages,
)
from quantlab.dsl.models import (
    IterationConfig,
    OptimizeBlock,
    ResearchConfig,
    RetestBlock,
)


def _cfg(retest=None, optimize=None) -> ResearchConfig:
    return ResearchConfig(
        campaign="FullFlowPipe",
        market="EURUSD",
        timeframe="H1",
        iteration_config=IterationConfig(max_iterations=1),
        retest=retest,
        optimize=optimize,
    )


def _stage_names(pipeline) -> list[str]:
    return [s.name for s in pipeline.stages]


def _full_flow_pipeline():
    """Orchestrated pipeline with retest + optimize blocks enabled."""
    retest = RetestBlock(strategy_id="S1", databanks=["EURUSD_H1"])
    optimize = OptimizeBlock(strategy_id="S1", databanks=["EURUSD_H1"])
    return ResearchDirector().build_pipeline(
        _cfg(retest=retest, optimize=optimize), orchestrated=True
    )


class TestFullFlowCoversCanonicalPhases:
    """REQ-37: the orchestrated pipeline resolves to all 14 phases."""

    def test_all_14_canonical_phases_present(self) -> None:
        """GIVEN the full orchestrated pipeline
        THEN every canonical phase maps to a stage present in the pipeline
        (no phase dropped — the campaign may begin).
        """
        names = _stage_names(_full_flow_pipeline())
        assert missing_flow_stages(names) == []
        for phase in PHASES:
            assert STAGE_FOR_PHASE[phase] in names, (
                f"phase '{phase}' is not wired to a pipeline stage"
            )

    def test_canonical_phase_order_is_the_14_phase_lifecycle(self) -> None:
        """GIVEN the canonical constant
        THEN assert_flow passes — the 14-phase order is intact (REQ-37).
        """
        assert_flow(list(PHASES))  # must not raise

    def test_pipeline_does_not_stop_at_optimize(self) -> None:
        """GIVEN the full orchestrated pipeline
        THEN every phase after optimize (portfolio → … → live-ops) is wired —
        the flow must not stop at optimize (REQ-01 scenario).
        """
        names = _stage_names(_full_flow_pipeline())
        post_optimize = PHASES[PHASES.index("optimize") + 1 :]
        assert post_optimize, "optimize must not be the last canonical phase"
        for phase in post_optimize:
            assert STAGE_FOR_PHASE[phase] in names, (
                f"phase '{phase}' (after optimize) is missing"
            )

    def test_demo_archive_and_live_ops_wired_after_deploy(self) -> None:
        """GIVEN the full orchestrated pipeline
        THEN demo and archive run after deploy and live-ops (guardian_evaluate)
        runs after archive — the post-archive boundary is closed (REQ-34).
        """
        names = _stage_names(_full_flow_pipeline())
        assert names.index("deploy") < names.index("demo") < names.index("archive")
        assert names.index("archive") < names.index("guardian_evaluate")

    def test_live_ops_stage_wired_after_archive(self) -> None:
        """GIVEN the full orchestrated pipeline
        THEN the canonical live-ops stage runs after archive and before the
        post-archive loop (REQ-01 phase 14, REQ-6).
        """
        names = _stage_names(_full_flow_pipeline())
        assert "live_ops" in names
        assert names.index("archive") < names.index("live_ops")
        assert names.index("live_ops") < names.index("monitor")


class TestFullFlowOrderSegments:
    """REQ-37: phase segments keep their canonical relative order."""

    def test_research_through_dispatch_are_ordered(self) -> None:
        """GIVEN the full orchestrated pipeline
        THEN research → hypothesis → config → review → dispatch are ordered.
        """
        names = _stage_names(_full_flow_pipeline())
        assert (
            names.index("research")
            < names.index("hypothesis_builder")
            < names.index("builder")
            < names.index("config_review")
            < names.index("dispatch")
        )

    def test_portfolio_through_archive_are_ordered(self) -> None:
        """GIVEN the full orchestrated pipeline
        THEN portfolio → compile → deploy → demo → archive are ordered.
        """
        names = _stage_names(_full_flow_pipeline())
        assert (
            names.index("portfolio")
            < names.index("compile")
            < names.index("deploy")
            < names.index("demo")
            < names.index("archive")
        )

    def test_live_ops_loop_is_ordered(self) -> None:
        """GIVEN the full orchestrated pipeline
        THEN the post-archive live-ops loop runs monitor → guardian_evaluate →
        retester → optimizer in order (design boundary).
        """
        names = _stage_names(_full_flow_pipeline())
        assert (
            names.index("monitor")
            < names.index("guardian_evaluate")
            < names.index("retester")
            < names.index("optimizer")
        )


class TestFullFlowScoping:
    """The full flow belongs to the orchestrated branch only (REQ-11)."""

    def test_legacy_pipeline_has_no_demo_archive_or_live_ops(self) -> None:
        """GIVEN the default (non-orchestrated) pipeline
        THEN the post-deploy boundary stages are absent — legacy is unchanged.
        """
        names = _stage_names(ResearchDirector().build_pipeline(_cfg()))
        assert "demo" not in names
        assert "archive" not in names
        assert "guardian_evaluate" not in names

    def test_orchestrated_without_blocks_still_runs_full_flow(self) -> None:
        """GIVEN orchestrated=True without retest/optimize blocks
        THEN demo/archive/guardian_evaluate are still wired (retester and
        optimizer are the only conditional stages).
        """
        names = _stage_names(ResearchDirector().build_pipeline(_cfg(), orchestrated=True))
        assert "demo" in names
        assert "archive" in names
        assert "guardian_evaluate" in names
        assert "retester" not in names
        assert "optimizer" not in names
