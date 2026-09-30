"""Tests for the HUMAN_APPROVE_REPLACEMENT gate registration.

The Guardian's live-replacement gate is a prompt-level contract today: the
guardian-orchestrator agent presents it, but no code path invokes it yet.
Registering it gives the gate an explicit, deliberately chosen failure mode
instead of relying on the incidental ``GatePolicyConfig`` default.

The important property is that an unanswered replacement fails closed. This
gate is the only path that changes a live position, so it must never fall back
to ``CONTINUE`` — the one fallback that resolves to
``GateDecisionAction.APPROVE`` and therefore auto-approves.
"""

from __future__ import annotations

from quantlab.gates.models import (
    DEFAULT_GATE_POLICIES,
    FallbackPolicy,
    GateDecisionAction,
    HUMAN_GATE_IDS,
    GatePolicyConfig,
)
from quantlab.gates.orchestrator import HumanGateOrchestrator

import pytest

HUMAN_APPROVE_REPLACEMENT = "HUMAN_APPROVE_REPLACEMENT"


class TestReplacementGateRegistration:
    """The gate is registered with an explicit fail-closed policy."""

    def test_replacement_gate_in_gate_ids(self) -> None:
        """GIVEN the gate registry
        WHEN checking HUMAN_GATE_IDS
        THEN HUMAN_APPROVE_REPLACEMENT is present (appended, not replacing).
        """
        assert HUMAN_APPROVE_REPLACEMENT in HUMAN_GATE_IDS

    def test_replacement_gate_in_default_gate_policies(self) -> None:
        """GIVEN DEFAULT_GATE_POLICIES
        WHEN checking the registry
        THEN HUMAN_APPROVE_REPLACEMENT has an explicit policy entry.
        """
        assert HUMAN_APPROVE_REPLACEMENT in DEFAULT_GATE_POLICIES

    def test_replacement_gate_policy_key_matches_gate_id(self) -> None:
        """GIVEN the registry is keyed by gate id
        WHEN looking up HUMAN_APPROVE_REPLACEMENT
        THEN the policy's own gate_id matches its dict key, so a lookup by
        either one resolves to the same policy.
        """
        policy = DEFAULT_GATE_POLICIES[HUMAN_APPROVE_REPLACEMENT]
        assert policy.gate_id == HUMAN_APPROVE_REPLACEMENT

    def test_replacement_gate_never_auto_approves(self) -> None:
        """GIVEN the HUMAN_APPROVE_REPLACEMENT policy
        WHEN checking its fallback
        THEN it is not CONTINUE — CONTINUE is the auto-approve path.
        """
        policy = DEFAULT_GATE_POLICIES[HUMAN_APPROVE_REPLACEMENT]
        assert policy.fallback is not FallbackPolicy.CONTINUE

    def test_replacement_gate_escalate_target_is_set_only_for_escalate(self) -> None:
        """GIVEN the registry's escalate_to convention
        WHEN checking HUMAN_APPROVE_REPLACEMENT
        THEN escalate_to is populated only when the fallback is ESCALATE, so no
        gate carries a target it would never use.
        """
        for policy in DEFAULT_GATE_POLICIES.values():
            if policy.fallback is FallbackPolicy.ESCALATE:
                assert policy.escalate_to, (
                    f"{policy.gate_id} escalates but names no target"
                )
            else:
                assert policy.escalate_to == "", (
                    f"{policy.gate_id} names an escalate_to but does not escalate"
                )


class TestReplacementGateFailClosed:
    """An unanswered replacement resolves to a non-approving action.

    Assertions are on the resolved ``GateDecisionAction``, never on
    ``GateDecision.is_approved()``: that helper also returns True for
    ``FALLBACK`` (PR-4), so it cannot distinguish an approved replacement from
    an aborted one. The live callers gate on the explicit action for the same
    reason — see ``_GATE_APPROVED_ACTIONS`` in ``cli/campaign_commands.py``.
    """

    @pytest.mark.asyncio
    async def test_unanswered_replacement_does_not_approve(self) -> None:
        """GIVEN the replacement gate with no callback registered
        WHEN the gate fires
        THEN the resolved action is not APPROVE.
        """
        orchestrator = HumanGateOrchestrator()
        decision = await orchestrator.on_gate(
            HUMAN_APPROVE_REPLACEMENT, {"campaign_id": "camp-live-1"}
        )

        assert decision.action is not GateDecisionAction.APPROVE
        assert decision.gate_id == HUMAN_APPROVE_REPLACEMENT
        assert decision.decided_by == "system"

    def test_replacement_policy_is_distinct_from_the_default(self) -> None:
        """GIVEN the registered policy
        WHEN compared with a default-constructed policy
        THEN they differ, proving the entry is an explicit choice and not the
        incidental ``GatePolicyConfig`` default.
        """
        registered = DEFAULT_GATE_POLICIES[HUMAN_APPROVE_REPLACEMENT]
        default = GatePolicyConfig(gate_id=HUMAN_APPROVE_REPLACEMENT)
        assert registered.fallback != default.fallback


class TestPreExistingGatesPreserved:
    """Registering the ninth gate appends; it does not replace anything."""

    def test_all_prior_gate_ids_remain_registered(self) -> None:
        """GIVEN the eight gates registered before this change
        WHEN HUMAN_APPROVE_REPLACEMENT is added
        THEN every prior gate ID is still present in both the ID list and the
        policy registry.
        """
        for gate_id in (
            "HUMAN_REVIEW_OBJECTIVES",
            "HUMAN_APPROVE_ITERATION",
            "HUMAN_APPROVE_PORTFOLIO",
            "HUMAN_APPROVE_DEPLOY",
            "HUMAN_APPROVE_DEMO",
            "HUMAN_APPROVE_ARCHIVE",
            "HUMAN_REVIEW_PERFORMANCE",
            "HUMAN_APPROVE_CONFIG",
        ):
            assert gate_id in HUMAN_GATE_IDS
            assert gate_id in DEFAULT_GATE_POLICIES
