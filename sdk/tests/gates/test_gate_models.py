"""Tests for gate models — REQ-06 (HUMAN_APPROVE_CONFIG gate).

Verifies HUMAN_APPROVE_CONFIG is appended to HUMAN_GATE_IDS with a
fail-closed policy (fallback HOLD) and webhook+console notifications.
"""

from quantlab.gates.models import (
    DEFAULT_GATE_POLICIES,
    FallbackPolicy,
    GateDecision,
    GateDecisionAction,
    HUMAN_GATE_IDS,
)

HUMAN_APPROVE_CONFIG = "HUMAN_APPROVE_CONFIG"


class TestHumanApproveConfigGateModel:
    """REQ-06: HUMAN_APPROVE_CONFIG gate between review and dispatch."""

    def test_human_approve_config_in_gate_ids(self) -> None:
        """GIVEN the gate registry
        WHEN checking HUMAN_GATE_IDS
        THEN HUMAN_APPROVE_CONFIG is present (appended, not replacing).
        """
        assert HUMAN_APPROVE_CONFIG in HUMAN_GATE_IDS

    def test_human_approve_config_policy_fallback_hold(self) -> None:
        """GIVEN the HUMAN_APPROVE_CONFIG policy
        WHEN checking its fallback
        THEN it fails closed (HOLD) — never auto-approves on timeout.
        """
        policy = DEFAULT_GATE_POLICIES[HUMAN_APPROVE_CONFIG]
        assert policy.fallback == FallbackPolicy.HOLD

    def test_human_approve_config_notifications_webhook_and_console(self) -> None:
        """GIVEN the HUMAN_APPROVE_CONFIG policy
        WHEN checking notifications
        THEN webhook and console channels are registered for production.
        """
        notifications = DEFAULT_GATE_POLICIES[HUMAN_APPROVE_CONFIG].notifications
        assert "webhook" in notifications
        assert "console" in notifications

    def test_existing_gates_preserved(self) -> None:
        """GIVEN the existing five human gates
        WHEN appending HUMAN_APPROVE_CONFIG
        THEN all prior gate IDs remain registered (append, not overwrite).
        """
        for gate_id in (
            "HUMAN_REVIEW_OBJECTIVES",
            "HUMAN_APPROVE_ITERATION",
            "HUMAN_APPROVE_PORTFOLIO",
            "HUMAN_APPROVE_DEPLOY",
            "HUMAN_REVIEW_PERFORMANCE",
        ):
            assert gate_id in HUMAN_GATE_IDS
            assert gate_id in DEFAULT_GATE_POLICIES


class TestGateDecisionSemantics:
    """Sanity for the decision model used by the gate protocol."""

    def test_hold_is_not_approval(self) -> None:
        """GIVEN a HOLD decision
        WHEN checking is_approved
        THEN it is not approved — fail-closed semantics hold.
        """
        decision = GateDecision(gate_id=HUMAN_APPROVE_CONFIG, action=GateDecisionAction.HOLD)
        assert not decision.is_approved()

    def test_approve_is_approved(self) -> None:
        """GIVEN an APPROVE decision
        WHEN checking is_approved
        THEN it allows the pipeline to continue.
        """
        decision = GateDecision(gate_id=HUMAN_APPROVE_CONFIG, action=GateDecisionAction.APPROVE)
        assert decision.is_approved()
