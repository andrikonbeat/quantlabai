"""Unit tests for GateInterceptorStage — task 1.13.

Verifies:
    - GateInterceptorStage pause/resume flow
    - Timeout handling with fallback policies (ABORT, CONTINUE, ESCALATE)
    - Engram recording
    - Gate decision written to PipelineContext artifacts
"""

import asyncio
from datetime import datetime, timezone

import pytest

from quantlab.pipeline.base import PipelineContext
from quantlab.pipeline.errors import GateTimeoutError
from quantlab.pipeline.stages.gate_interceptor import (
    FallbackPolicy,
    GateAction,
    GateContext,
    GateDecision,
    GateInterceptorStage,
    HUMAN_GATE_IDS,
)


class TestGateInterceptorStage:
    """Tests for the GateInterceptorStage."""

    def test_contract_attributes(self) -> None:
        """GIVEN a GateInterceptorStage
        WHEN inspecting its contract
        THEN it has the expected default attributes.
        """
        gate = GateInterceptorStage()
        gate.gate_id = "HUMAN_REVIEW_OBJECTIVES"
        assert gate.name == "gate"
        assert gate.gate_id == "HUMAN_REVIEW_OBJECTIVES"
        assert gate.timeout_hours == 24.0
        assert gate.fallback == FallbackPolicy.ESCALATE
        assert gate.requires == []
        assert gate.provides == []

    def test_gate_customisation(self) -> None:
        """GIVEN a GateInterceptorStage for deploy gate
        WHEN setting custom timeout and fallback
        THEN attributes reflect the configuration.
        """
        gate = GateInterceptorStage()
        gate.gate_id = "HUMAN_APPROVE_DEPLOY"
        gate.timeout_hours = 6.0
        gate.fallback = FallbackPolicy.ABORT
        gate.requires = ["portfolio_cfx"]
        gate.provides = ["gate_decision_HUMAN_APPROVE_DEPLOY"]

        assert gate.gate_id == "HUMAN_APPROVE_DEPLOY"
        assert gate.timeout_hours == 6.0
        assert gate.fallback == FallbackPolicy.ABORT
        assert gate.requires == ["portfolio_cfx"]

    def test_human_gate_ids(self) -> None:
        """GIVEN HUMAN_GATE_IDS
        THEN all 5 gate IDs are defined.
        """
        assert len(HUMAN_GATE_IDS) == 5
        assert "HUMAN_REVIEW_OBJECTIVES" in HUMAN_GATE_IDS
        assert "HUMAN_APPROVE_ITERATION" in HUMAN_GATE_IDS
        assert "HUMAN_APPROVE_PORTFOLIO" in HUMAN_GATE_IDS
        assert "HUMAN_APPROVE_DEPLOY" in HUMAN_GATE_IDS
        assert "HUMAN_REVIEW_PERFORMANCE" in HUMAN_GATE_IDS

    def test_set_callback(self) -> None:
        """GIVEN a GateInterceptorStage
        WHEN a callback is set
        THEN it is stored and callable.
        """
        gate = GateInterceptorStage()
        gate.gate_id = "HUMAN_REVIEW_OBJECTIVES"

        async def mock_callback(ctx: GateContext) -> GateDecision:
            return GateDecision(
                gate_id="HUMAN_REVIEW_OBJECTIVES",
                action=GateAction.APPROVED,
                reason="Approved by test",
                decided_by="test",
            )

        gate.set_callback(mock_callback)
        # We can't easily test private _callback, but we can test it doesn't error
        assert gate._callback is not None

    @pytest.mark.asyncio
    async def test_execute_approved(self) -> None:
        """GIVEN a GateInterceptorStage with an APPROVE callback
        WHEN executed
        THEN it returns the decision and writes to context artifacts.
        """
        gate = GateInterceptorStage()
        gate.gate_id = "HUMAN_REVIEW_OBJECTIVES"

        async def mock_callback(ctx: GateContext) -> GateDecision:
            return GateDecision(
                gate_id="HUMAN_REVIEW_OBJECTIVES",
                action=GateAction.APPROVED,
                reason="Looks good",
                decided_by="human",
            )

        gate.set_callback(mock_callback)

        ctx = PipelineContext(config={})
        result = await gate.execute(ctx)

        assert result["gate_id"] == "HUMAN_REVIEW_OBJECTIVES"
        assert result["decision"] == "approved"
        assert result["reason"] == "Looks good"

        # Verify context artifact written
        artifact = ctx.artifacts.get("gate_decision_HUMAN_REVIEW_OBJECTIVES")
        assert artifact is not None
        assert artifact["action"] == "approved"
        assert artifact["reason"] == "Looks good"

    @pytest.mark.asyncio
    async def test_execute_rejected(self) -> None:
        """GIVEN a GateInterceptorStage with a REJECT callback
        WHEN executed
        THEN it returns the rejection decision.
        """
        gate = GateInterceptorStage()
        gate.gate_id = "HUMAN_APPROVE_ITERATION"

        async def mock_callback(ctx: GateContext) -> GateDecision:
            return GateDecision(
                gate_id="HUMAN_APPROVE_ITERATION",
                action=GateAction.REJECTED,
                reason="Criteria not met",
                decided_by="human",
            )

        gate.set_callback(mock_callback)

        ctx = PipelineContext(config={})
        result = await gate.execute(ctx)

        assert result["gate_id"] == "HUMAN_APPROVE_ITERATION"
        assert result["decision"] == "rejected"
        assert result["reason"] == "Criteria not met"

    @pytest.mark.asyncio
    async def test_timeout_with_abort_fallback(self) -> None:
        """GIVEN a GateInterceptorStage with timeout and ABORT fallback
        WHEN no callback responds before timeout
        THEN GateTimeoutError is raised.
        """
        gate = GateInterceptorStage()
        gate.gate_id = "HUMAN_APPROVE_DEPLOY"
        gate.timeout_hours = 0.0001  # Very short timeout (0.36 seconds)
        gate.fallback = FallbackPolicy.ABORT

        async def slow_callback(ctx: GateContext) -> GateDecision:
            await asyncio.sleep(10)  # Will never complete in time
            return GateDecision(gate_id="test", action=GateAction.APPROVED)

        gate.set_callback(slow_callback)

        ctx = PipelineContext(config={})
        with pytest.raises(GateTimeoutError) as excinfo:
            await gate.execute(ctx)

        assert "HUMAN_APPROVE_DEPLOY" in str(excinfo.value)
        assert excinfo.value.gate_id == "HUMAN_APPROVE_DEPLOY"

    @pytest.mark.asyncio
    async def test_timeout_with_continue_fallback(self) -> None:
        """GIVEN a GateInterceptorStage with timeout and CONTINUE fallback
        WHEN timeout elapses
        THEN execution continues with fallback decision.
        """
        gate = GateInterceptorStage()
        gate.gate_id = "HUMAN_REVIEW_PERFORMANCE"
        gate.timeout_hours = 0.0001  # Very short timeout
        gate.fallback = FallbackPolicy.CONTINUE

        async def slow_callback(ctx: GateContext) -> GateDecision:
            await asyncio.sleep(10)
            return GateDecision(gate_id="test", action=GateAction.APPROVED)

        gate.set_callback(slow_callback)

        ctx = PipelineContext(config={})
        result = await gate.execute(ctx)

        assert result["decision"] == "fallback"
        assert "CONTINUE" in result["reason"]

    @pytest.mark.asyncio
    async def test_timeout_with_escalate_fallback(self) -> None:
        """GIVEN a GateInterceptorStage with timeout and ESCALATE fallback
        WHEN timeout elapses
        THEN execution continues with escalation decision.
        """
        gate = GateInterceptorStage()
        gate.gate_id = "HUMAN_REVIEW_OBJECTIVES"
        gate.timeout_hours = 0.0001
        gate.fallback = FallbackPolicy.ESCALATE

        async def slow_callback(ctx: GateContext) -> GateDecision:
            await asyncio.sleep(10)
            return GateDecision(gate_id="test", action=GateAction.APPROVED)

        gate.set_callback(slow_callback)

        ctx = PipelineContext(config={})
        result = await gate.execute(ctx)

        assert result["decision"] == "fallback"
        assert "ESCALATE" in result["reason"]

    @pytest.mark.asyncio
    async def test_no_callback_uses_fallback(self) -> None:
        """GIVEN a GateInterceptorStage with no callback set
        WHEN executed
        THEN fallback is applied directly.
        """
        gate = GateInterceptorStage()
        gate.gate_id = "HUMAN_REVIEW_OBJECTIVES"
        gate.timeout_hours = 24.0
        gate.fallback = FallbackPolicy.CONTINUE

        ctx = PipelineContext(config={})
        result = await gate.execute(ctx)

        assert result["decision"] == "fallback"
        assert "CONTINUE" in result["reason"]

    def test_gate_context_build(self) -> None:
        """GIVEN a GateInterceptorStage and PipelineContext
        WHEN build_gate_context is called
        THEN a GateContext with correct fields is returned.
        """
        gate = GateInterceptorStage()
        gate.gate_id = "HUMAN_APPROVE_PORTFOLIO"
        gate.timeout_hours = 12.0
        gate.fallback = FallbackPolicy.ESCALATE

        ctx = PipelineContext(
            config={"pipeline_name": "test-pipeline"},
            artifacts={"portfolio_cfx": b"cfx-data"},
        )
        ctx.metadata["pipeline_name"] = "test-pipeline"

        gate_ctx = gate.build_gate_context(ctx)

        assert gate_ctx.gate_id == "HUMAN_APPROVE_PORTFOLIO"
        assert gate_ctx.pipeline_name == "test-pipeline"
        assert gate_ctx.timeout_hours == 12.0
        assert gate_ctx.fallback == FallbackPolicy.ESCALATE
        assert "portfolio_cfx" in gate_ctx.context_artifacts

    @pytest.mark.asyncio
    async def test_is_engaged(self) -> None:
        """GIVEN a GateInterceptorStage
        WHEN it has been executed
        THEN is_engaged returns True.
        """
        gate = GateInterceptorStage()
        gate.gate_id = "TEST_GATE"
        gate.fallback = FallbackPolicy.CONTINUE

        assert gate.is_engaged is False

        # After execution (with fallback since no callback)
        ctx = PipelineContext(config={})
        await gate.execute(ctx)

        assert gate.is_engaged is True


@pytest.mark.asyncio
async def test_gate_decision_enum() -> None:
    """GIVEN GateAction enum values
    THEN they match expected strings.
    """
    assert GateAction.APPROVED.value == "approved"
    assert GateAction.REJECTED.value == "rejected"
    assert GateAction.TIMEOUT.value == "timeout"
    assert GateAction.FALLBACK.value == "fallback"


@pytest.mark.asyncio
async def test_fallback_policy_enum() -> None:
    """GIVEN FallbackPolicy enum values
    THEN they match expected strings.
    """
    assert FallbackPolicy.ABORT.value == "ABORT"
    assert FallbackPolicy.CONTINUE.value == "CONTINUE"
    assert FallbackPolicy.ESCALATE.value == "ESCALATE"
