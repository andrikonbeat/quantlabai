"""WU-6: orchestrated pipeline wiring (REQ-06, REQ-11, REQ-17 wiring).

Covers the orchestrated branch of ``ResearchDirector.build_pipeline``:
stage order research → builder → config_review → dispatch → … → retest →
optimize, the HUMAN_APPROVE_CONFIG gate between review and dispatch, and
fail-closed gate behavior in orchestrated mode (REQ-06 / REQ-11, D2/D3).

Strict TDD: written first — FAIL (RED) until the orchestrated wiring exists.
"""

import pytest

from quantlab.agents.research_director import ResearchDirector
from quantlab.dsl.models import (
    IterationConfig,
    OptimizeBlock,
    ResearchConfig,
    RetestBlock,
)
from quantlab.gates.callbacks import fail_closed_callback
from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.stages.config_review_stage import ConfigReviewStage
from quantlab.pipeline.stages.dispatch_stage import DispatchStage
from quantlab.pipeline.stages.gate_interceptor import (
    FallbackPolicy,
    GateAction,
    GateInterceptorStage,
)


def _cfg(retest=None, optimize=None) -> ResearchConfig:
    return ResearchConfig(
        campaign="OrchestratedPipe",
        market="EURUSD",
        timeframe="H1",
        iteration_config=IterationConfig(max_iterations=1),
        retest=retest,
        optimize=optimize,
    )


def _stage_names(pipeline) -> list[str]:
    return [s.name for s in pipeline.stages]


def _gates(pipeline) -> list[GateInterceptorStage]:
    return [s for s in pipeline.stages if isinstance(s, GateInterceptorStage)]


def _gate_ids(pipeline) -> list[str]:
    return [g.gate_id for g in _gates(pipeline)]


def _config_gate(pipeline) -> GateInterceptorStage:
    return next(g for g in _gates(pipeline) if g.gate_id == "HUMAN_APPROVE_CONFIG")


class _BlockingReviewer:
    """Reviews any BuildConfig as BLOCK (unsafe configuration)."""

    def review(self, build_config, costs=None):
        from quantlab.agents.config_reviewer import ConfigReviewVerdict

        return ConfigReviewVerdict(
            action="BLOCK",
            reason="SL stricter than PT (contradictory risk settings)",
            proposed_changes={},
            cost_note="preset cost profile",
        )


class _SpyBuilder:
    """Dispatch spy proving dispatch is never invoked on a BLOCK."""

    def __init__(self):
        self.dispatch_calls = []

    async def _dispatch_single(self, *args, **kwargs):
        self.dispatch_calls.append((args, kwargs))
        return None


# ── Stage wiring ──────────────────────────────────────────────────────────────

class TestOrchestratedStageWiring:
    """REQ-06/REQ-01: orchestrated stage order with config review + dispatch."""

    def test_orchestrated_adds_config_review_and_dispatch(self) -> None:
        """GIVEN orchestrated=True
        WHEN building the pipeline
        THEN config_review and dispatch are present, after builder, in order.
        """
        pipeline = ResearchDirector().build_pipeline(_cfg(), orchestrated=True)
        names = _stage_names(pipeline)

        assert "config_review" in names
        assert "dispatch" in names
        assert names.index("builder") < names.index("config_review") < names.index("dispatch")

    def test_orchestrated_research_leads_into_config_review(self) -> None:
        """GIVEN orchestrated=True
        THEN research runs before config_review (spec: after builder, before dispatch).
        """
        pipeline = ResearchDirector().build_pipeline(_cfg(), orchestrated=True)
        names = _stage_names(pipeline)
        assert names.index("research") < names.index("config_review")

    def test_orchestrated_dispatch_before_statistics(self) -> None:
        """GIVEN orchestrated=True
        THEN dispatch provides export_paths before statistics consumes them.
        """
        pipeline = ResearchDirector().build_pipeline(_cfg(), orchestrated=True)
        names = _stage_names(pipeline)
        assert names.index("dispatch") < names.index("statistics")

    def test_retester_optimizer_appended_after_monitor_when_configured(self) -> None:
        """GIVEN retest and optimize blocks in the ResearchConfig
        WHEN building the orchestrated pipeline
        THEN retester then optimizer run after monitor (REQ-01 loop tail).
        """
        retest = RetestBlock(strategy_id="S1", databanks=["EURUSD_H1"])
        optimize = OptimizeBlock(strategy_id="S1", databanks=["EURUSD_H1"])
        pipeline = ResearchDirector().build_pipeline(
            _cfg(retest=retest, optimize=optimize), orchestrated=True
        )
        names = _stage_names(pipeline)

        assert names.index("monitor") < names.index("retester") < names.index("optimizer")

    def test_retester_optimizer_absent_without_blocks(self) -> None:
        """GIVEN no retest/optimize blocks
        THEN the orchestrated pipeline has no retester/optimizer stages.
        """
        pipeline = ResearchDirector().build_pipeline(_cfg(), orchestrated=True)
        names = _stage_names(pipeline)
        assert "retester" not in names
        assert "optimizer" not in names

    def test_legacy_pipeline_unchanged(self) -> None:
        """REQ-11: default (non-orchestrated) pipeline is untouched."""
        pipeline = ResearchDirector().build_pipeline(_cfg())
        names = _stage_names(pipeline)

        assert "config_review" not in names
        assert "dispatch" not in names
        assert "retester" not in names
        assert "optimizer" not in names
        assert _gate_ids(pipeline) == [
            "HUMAN_REVIEW_OBJECTIVES",
            "HUMAN_APPROVE_ITERATION",
            "HUMAN_APPROVE_PORTFOLIO",
            "HUMAN_APPROVE_DEPLOY",
            "HUMAN_REVIEW_PERFORMANCE",
        ]


# ── Gate wiring ───────────────────────────────────────────────────────────────

class TestOrchestratedGateWiring:
    """REQ-06: HUMAN_APPROVE_CONFIG between review and dispatch."""

    def test_orchestrated_gates_gain_human_approve_config(self) -> None:
        """GIVEN orchestrated=True
        THEN the pipeline gains the HUMAN_APPROVE_CONFIG gate after
        config_review and before dispatch, plus the HUMAN_APPROVE_DEMO
        interceptor after the demo stage (REQ-38 s4)."""
        pipeline = ResearchDirector().build_pipeline(_cfg(), orchestrated=True)
        names = _stage_names(pipeline)
        gate_ids = _gate_ids(pipeline)

        assert "HUMAN_APPROVE_CONFIG" in gate_ids
        assert "HUMAN_APPROVE_DEMO" in gate_ids
        assert len(gate_ids) == 7
        idx_gate = names.index("gate_HUMAN_APPROVE_CONFIG")
        assert names.index("config_review") < idx_gate < names.index("dispatch")
        idx_demo = names.index("gate_HUMAN_APPROVE_DEMO")
        assert names.index("demo") < idx_demo < names.index("archive")

    @pytest.mark.asyncio
    async def test_orchestrated_gate_fails_closed_without_callback(self) -> None:
        """REQ-11/D2: no callback registered in orchestrated mode → HOLD,
        never auto-approve.
        """
        pipeline = ResearchDirector().build_pipeline(_cfg(), orchestrated=True)
        gate = _config_gate(pipeline)
        ctx = PipelineContext(config={})

        result = await gate.execute(ctx)

        assert result["decision"] == GateAction.HOLD.value
        decision_artifact = ctx.artifacts[f"gate_decision_{gate.gate_id}"]
        assert decision_artifact["action"] == GateAction.HOLD.value

    @pytest.mark.asyncio
    async def test_orchestrated_fail_closed_covers_all_gates(self) -> None:
        """REQ-11: every HUMAN_* gate fails closed in orchestrated mode when
        no callback is registered.
        """
        pipeline = ResearchDirector().build_pipeline(_cfg(), orchestrated=True)

        for gate in _gates(pipeline):
            ctx = PipelineContext(config={})
            result = await gate.execute(ctx)
            assert result["decision"] == GateAction.HOLD.value, (
                f"gate {gate.gate_id} must fail closed in orchestrated mode"
            )


# ── BLOCK → dispatch never invoked ────────────────────────────────────────────

class TestBlockStopsDispatch:
    """REQ-05/06: a BLOCK verdict on config review stops dispatch."""

    @pytest.mark.asyncio
    async def test_block_verdict_never_dispatches(self) -> None:
        """GIVEN a BLOCK verdict from config review
        WHEN the gate fires and DispatchStage runs
        THEN dispatch is never invoked and dispatch_blocked is published.
        """
        from quantlab.sqx.project_builder import BuildConfig

        spy = _SpyBuilder()
        review_stage = ConfigReviewStage(reviewer=_BlockingReviewer())
        gate = GateInterceptorStage()
        gate.gate_id = "HUMAN_APPROVE_CONFIG"
        gate.fallback = FallbackPolicy.HOLD

        async def _fail_closed_wrapper(gate_ctx) -> None:
            ctx_dict = (
                gate_ctx.__dict__
                if hasattr(gate_ctx, "__dict__")
                else dict(gate_ctx)
            )
            return await fail_closed_callback(ctx_dict)

        gate.set_callback(_fail_closed_wrapper)
        dispatch_stage = DispatchStage(builder=spy)

        ctx = PipelineContext(
            config={},
            artifacts={"build_config": BuildConfig()},
        )

        await review_stage.execute(ctx)
        assert ctx.artifacts["config_review_verdict"]["action"] == "BLOCK"

        await gate.execute(ctx)
        await dispatch_stage.execute(ctx)

        assert spy.dispatch_calls == []
        assert ctx.artifacts["dispatch_blocked"] is True
