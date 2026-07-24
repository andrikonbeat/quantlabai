"""GateDecision Pydantic models — approval decisions for human gates.

Defines the decision enum and data models used by HumanGateOrchestrator
and GateInterceptorStage for recording gate outcomes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class GateDecisionAction(str, Enum):
    """Possible outcomes of a gate decision."""

    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"
    ESCALATE = "escalate"
    TIMEOUT = "timeout"
    FALLBACK = "fallback"
    HOLD = "hold"


class FallbackPolicy(str, Enum):
    """Fallback behaviour when a gate times out without a response."""

    ABORT = "ABORT"          # Stop the pipeline
    CONTINUE = "CONTINUE"    # Proceed as if approved
    ESCALATE = "ESCALATE"    # Escalate to a human lead (external)
    HOLD = "HOLD"            # Hold the pipeline (for deploy gate)


class GateDecision(BaseModel):
    """Decision produced by a gate callback or fallback.

    Attributes:
        gate_id: Unique gate identifier (e.g. "HUMAN_REVIEW_OBJECTIVES").
        action: The decision action (approve, reject, modify, escalate, timeout, fallback).
        timestamp: UTC timestamp when the decision was made.
        reason: Human-readable reason for the decision.
        decided_by: Who made the decision ("human", "system", "escalation").
        metadata: Additional context (e.g., modified_context for MODIFY action).
    """

    gate_id: str = Field(..., description="Gate identifier")
    action: GateDecisionAction = Field(default=GateDecisionAction.APPROVE)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str = Field(default="")
    decided_by: str = Field(default="system")  # human, system, escalation
    metadata: dict[str, Any] = Field(default_factory=dict)

    def is_approved(self) -> bool:
        """Return True if the decision allows the pipeline to continue."""
        return self.action in (
            GateDecisionAction.APPROVE,
            GateDecisionAction.FALLBACK,
        )

    def is_terminal(self) -> bool:
        """Return True if the decision stops the pipeline."""
        return self.action in (
            GateDecisionAction.REJECT,
            GateDecisionAction.ABORT,
            GateDecisionAction.TIMEOUT,
        )


class GateContext(BaseModel):
    """Context provided to the gate callback for decision making.

    Attributes:
        gate_id: Unique gate identifier.
        pipeline_name: Name of the pipeline being executed.
        stage_name: Name of the stage that triggered this gate.
        context_artifacts: Dictionary of pipeline artifacts relevant to this gate.
        triggered_at: UTC timestamp when the gate was activated.
        timeout_hours: Configured timeout in hours.
        fallback: Configured fallback policy on timeout.
        escalate_to: Optional contact/channel for escalation fallback.
        campaign_id: Optional campaign identifier.
        iteration: Optional iteration number.
    """

    gate_id: str = Field(..., description="Gate identifier")
    pipeline_name: str = Field(default="unknown")
    stage_name: str = Field(default="")
    context_artifacts: dict[str, Any] = Field(default_factory=dict)
    triggered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    timeout_hours: float = Field(default=24.0, ge=0.1)
    fallback: FallbackPolicy = Field(default=FallbackPolicy.ESCALATE)
    escalate_to: str = Field(default="")
    campaign_id: str = Field(default="")
    iteration: int = Field(default=0)


class GatePolicyConfig(BaseModel):
    """Configuration for a single gate in the pipeline.

    Attributes:
        gate_id: Unique gate identifier (e.g. "HUMAN_REVIEW_OBJECTIVES").
        timeout_hours: Maximum wait time for human response (default 24h).
        fallback: Fallback policy on timeout (ABORT, CONTINUE, ESCALATE, HOLD).
        escalate_to: Contact/channel for ESCALATE fallback.
        notifications: List of notification channels (email, slack, webhook, console).
        required_approvers: Number of approvers required for approval.
    """

    gate_id: str = Field(..., description="Gate identifier")
    timeout_hours: float = Field(default=24.0, ge=0.1)
    fallback: FallbackPolicy = Field(default=FallbackPolicy.ESCALATE)
    escalate_to: str = Field(default="")
    notifications: list[str] = Field(default_factory=list)
    required_approvers: int = Field(default=1, ge=1)


# Predefined gate policies matching the specification
DEFAULT_GATE_POLICIES: dict[str, GatePolicyConfig] = {
    "HUMAN_REVIEW_OBJECTIVES": GatePolicyConfig(
        gate_id="HUMAN_REVIEW_OBJECTIVES",
        timeout_hours=24.0,
        fallback=FallbackPolicy.ESCALATE,
        escalate_to="research_lead@quantlab.ai",
        notifications=["email", "slack"],
    ),
    "HUMAN_APPROVE_ITERATION": GatePolicyConfig(
        gate_id="HUMAN_APPROVE_ITERATION",
        timeout_hours=24.0,
        fallback=FallbackPolicy.ABORT,
        notifications=["email"],
    ),
    "HUMAN_APPROVE_PORTFOLIO": GatePolicyConfig(
        gate_id="HUMAN_APPROVE_PORTFOLIO",
        timeout_hours=24.0,
        fallback=FallbackPolicy.ESCALATE,
        escalate_to="portfolio_mgr@quantlab.ai",
        notifications=["email", "slack"],
    ),
    "HUMAN_APPROVE_DEPLOY": GatePolicyConfig(
        gate_id="HUMAN_APPROVE_DEPLOY",
        timeout_hours=12.0,
        fallback=FallbackPolicy.HOLD,
        notifications=["email", "slack"],
    ),
    "HUMAN_REVIEW_PERFORMANCE": GatePolicyConfig(
        gate_id="HUMAN_REVIEW_PERFORMANCE",
        timeout_hours=48.0,
        fallback=FallbackPolicy.CONTINUE,
        notifications=["console"],
    ),
}


HUMAN_GATE_IDS: list[str] = list(DEFAULT_GATE_POLICIES.keys())