"""Tests for pipeline gate stages."""

import pytest
from quantlab.pipeline.stages import (
    GateDecision,
    GateFallback,
    GateContext,
    GateInterceptorStage,
    GateApprovalStage,
    HumanReviewObjectivesStage,
    HumanApproveIterationStage,
    HumanApprovePortfolioStage,
    HumanApproveDeployStage,
    HumanReviewPerformanceStage,
)
from quantlab.pipeline.base import PipelineContext


class TestGateDecision:
    """Tests for GateDecision enum."""

    def test_decision_values(self):
        assert GateDecision.APPROVE.value == "approve"
        assert GateDecision.REJECT.value == "reject"
        assert GateDecision.ESCALATE.value == "escalate"
        assert GateDecision.MODIFY.value == "modify"


class TestGateFallback:
    """Tests for GateFallback enum."""

    def test_fallback_values(self):
        assert GateFallback.ABORT.value == "abort"
        assert GateFallback.CONTINUE.value == "continue"
        assert GateFallback.ESCALATE.value == "escalate"
        assert GateFallback.HOLD.value == "hold"


class TestGateContext:
    """Tests for GateContext dataclass."""

    def test_context_creation(self):
        ctx = GateContext(
            gate_id="TEST_GATE",
            campaign_id="camp-123",
            stage_name="gate_test",
            artifacts={"key": "value"},
            config={"timeout_hours": 24},
            metadata={"pipeline": "test"},
        )
        assert ctx.gate_id == "TEST_GATE"
        assert ctx.campaign_id == "camp-123"
        assert ctx.artifacts["key"] == "value"


class MockGateStage(GateInterceptorStage):
    """Mock gate stage for testing."""
    gate_id = "TEST_GATE"
    requires = ["input_artifact"]
    provides = ["gate_decision_test_gate"]


class TestGateInterceptorStage:
    """Tests for GateInterceptorStage."""

    @pytest.mark.asyncio
    async def test_auto_approve_when_no_callback(self):
        """Stage should auto-approve when no callback provided."""
        stage = MockGateStage()
        ctx = PipelineContext(
            config={},
            artifacts={"input_artifact": "test_value"},
            metadata={"campaign_id": "test-campaign"},
        )

        decision = await stage.execute(ctx)

        assert decision == GateDecision.APPROVE
        assert "gate_decision_test_gate" in ctx.artifacts
        assert ctx.artifacts["gate_decision_test_gate"]["decision"] == "approve"

    @pytest.mark.asyncio
    async def test_custom_callback_returns_reject(self):
        """Stage should use custom callback decision."""
        async def reject_callback(context: GateContext) -> GateDecision:
            return GateDecision.REJECT

        stage = MockGateStage(callback=reject_callback)
        ctx = PipelineContext(
            config={},
            artifacts={"input_artifact": "test_value"},
            metadata={"campaign_id": "test-campaign"},
        )

        decision = await stage.execute(ctx)

        assert decision == GateDecision.REJECT
        assert ctx.artifacts["gate_decision_test_gate"]["decision"] == "reject"

    @pytest.mark.asyncio
    async def test_timeout_triggers_fallback(self):
        """Stage should execute fallback on timeout."""
        async def slow_callback(context: GateContext) -> GateDecision:
            import asyncio
            await asyncio.sleep(10)  # Longer than timeout
            return GateDecision.APPROVE

        stage = MockGateStage(
            callback=slow_callback,
            timeout_hours=0.00001,  # ~0.036 seconds
            fallback=GateFallback.ABORT,
        )
        ctx = PipelineContext(
            config={},
            artifacts={"input_artifact": "test_value"},
            metadata={"campaign_id": "test-campaign"},
        )

        decision = await stage.execute(ctx)

        assert decision == GateDecision.REJECT  # ABORT fallback -> REJECT

    @pytest.mark.asyncio
    async def test_fallback_continue_approves(self):
        """CONTINUE fallback should approve on timeout."""
        async def slow_callback(context: GateContext) -> GateDecision:
            import asyncio
            await asyncio.sleep(10)
            return GateDecision.APPROVE

        stage = MockGateStage(
            callback=slow_callback,
            timeout_hours=0.00001,
            fallback=GateFallback.CONTINUE,
        )
        ctx = PipelineContext(
            config={},
            artifacts={"input_artifact": "test_value"},
            metadata={"campaign_id": "test-campaign"},
        )

        decision = await stage.execute(ctx)

        assert decision == GateDecision.APPROVE

    @pytest.mark.asyncio
    async def test_fallback_escalate(self):
        """ESCALATE fallback should return escalate decision."""
        async def slow_callback(context: GateContext) -> GateDecision:
            import asyncio
            await asyncio.sleep(10)
            return GateDecision.APPROVE

        stage = MockGateStage(
            callback=slow_callback,
            timeout_hours=0.00001,
            fallback=GateFallback.ESCALATE,
        )
        ctx = PipelineContext(
            config={},
            artifacts={"input_artifact": "test_value"},
            metadata={"campaign_id": "test-campaign"},
        )

        decision = await stage.execute(ctx)

        assert decision == GateDecision.ESCALATE

    @pytest.mark.asyncio
    async def test_decision_recorded_to_context(self):
        """Decision should be recorded to context artifacts."""
        stage = MockGateStage()
        ctx = PipelineContext(
            config={},
            artifacts={"input_artifact": "test_value"},
            metadata={"campaign_id": "test-campaign"},
        )

        await stage.execute(ctx)

        decision_key = "gate_decision_test_gate"
        assert decision_key in ctx.artifacts
        decision_data = ctx.artifacts[decision_key]
        assert "decision" in decision_data
        assert "gate_id" in decision_data
        assert "timestamp" in decision_data
        assert "fallback_used" in decision_data


class TestPredefinedGateStages:
    """Tests for the 5 predefined gate stages."""

    def test_human_review_objectives_contract(self):
        stage = HumanReviewObjectivesStage()
        assert stage.gate_id == "HUMAN_REVIEW_OBJECTIVES"
        assert stage.requires == ["research_config", "objectives", "hypotheses"]
        assert stage.provides == ["gate_decision_human_review_objectives"]

    def test_human_approve_iteration_contract(self):
        stage = HumanApproveIterationStage()
        assert stage.gate_id == "HUMAN_APPROVE_ITERATION"
        assert stage.requires == ["review_decision", "iteration_proposal"]
        assert stage.provides == ["gate_decision_human_approve_iteration"]

    def test_human_approve_portfolio_contract(self):
        stage = HumanApprovePortfolioStage()
        assert stage.gate_id == "HUMAN_APPROVE_PORTFOLIO"
        assert stage.requires == [
            "portfolio_cfx",
            "portfolio_result",
            "correlation_matrix",
            "risk_allocation",
        ]
        assert stage.provides == ["gate_decision_human_approve_portfolio"]

    def test_human_approve_deploy_contract(self):
        stage = HumanApproveDeployStage()
        assert stage.gate_id == "HUMAN_APPROVE_DEPLOY"
        assert stage.requires == ["jforex_package", "jcloud_config", "deployment_result"]
        assert stage.provides == ["gate_decision_human_approve_deploy"]

    def test_human_review_performance_contract(self):
        stage = HumanReviewPerformanceStage()
        assert stage.gate_id == "HUMAN_REVIEW_PERFORMANCE"
        assert stage.requires == ["rolling_metrics", "regime_alerts", "performance_alerts"]
        assert stage.provides == ["gate_decision_human_review_performance"]