"""Tests for the demo-flow human gates — REQ-38.

Verifies ``HUMAN_APPROVE_DEMO`` and ``HUMAN_APPROVE_ARCHIVE`` are registered
in ``HUMAN_GATE_IDS`` / ``DEFAULT_GATE_POLICIES`` with a fail-closed
``FallbackPolicy.HOLD`` (never auto-approve), that the orchestrator applies
the HOLD fallback when no callback is registered, and that both gates are
resolvable via the OpenCode ``question``-tool decision-file callback with the
stdin fallback (mirroring ``HUMAN_APPROVE_CONFIG``).
"""

from __future__ import annotations

import asyncio
import json

import pytest

from quantlab.gates.callbacks import (
    QuestionToolGateCallback,
    decision_path,
    fail_closed_callback,
    pending_path,
)
from quantlab.gates.models import (
    DEFAULT_GATE_POLICIES,
    FallbackPolicy,
    GateDecisionAction,
    HUMAN_GATE_IDS,
)
from quantlab.gates.orchestrator import HumanGateOrchestrator

HUMAN_APPROVE_DEMO = "HUMAN_APPROVE_DEMO"
HUMAN_APPROVE_ARCHIVE = "HUMAN_APPROVE_ARCHIVE"

_PREEXISTING_GATES = (
    "HUMAN_REVIEW_OBJECTIVES",
    "HUMAN_APPROVE_ITERATION",
    "HUMAN_APPROVE_PORTFOLIO",
    "HUMAN_APPROVE_DEPLOY",
    "HUMAN_REVIEW_PERFORMANCE",
    "HUMAN_APPROVE_CONFIG",
)


def _ctx(gate_id: str) -> dict[str, object]:
    return {
        "gate_id": gate_id,
        "campaign_id": "camp-demo-1",
        "stage_name": "demo_phase",
    }


class TestDemoArchiveGateRegistration:
    """REQ-38: HUMAN_APPROVE_DEMO / HUMAN_APPROVE_ARCHIVE registered."""

    def test_demo_gate_in_gate_ids(self) -> None:
        """GIVEN the gate registry
        WHEN checking HUMAN_GATE_IDS
        THEN HUMAN_APPROVE_DEMO is present (appended, not replacing).
        """
        assert HUMAN_APPROVE_DEMO in HUMAN_GATE_IDS

    def test_archive_gate_in_gate_ids(self) -> None:
        """GIVEN the gate registry
        WHEN checking HUMAN_GATE_IDS
        THEN HUMAN_APPROVE_ARCHIVE is present (appended, not replacing).
        """
        assert HUMAN_APPROVE_ARCHIVE in HUMAN_GATE_IDS

    def test_demo_gate_policy_fallback_hold(self) -> None:
        """GIVEN the HUMAN_APPROVE_DEMO policy
        WHEN checking its fallback
        THEN it fails closed (HOLD) — never auto-approves on timeout.
        """
        policy = DEFAULT_GATE_POLICIES[HUMAN_APPROVE_DEMO]
        assert policy.fallback == FallbackPolicy.HOLD

    def test_archive_gate_policy_fallback_hold(self) -> None:
        """GIVEN the HUMAN_APPROVE_ARCHIVE policy
        WHEN checking its fallback
        THEN it fails closed (HOLD) — never auto-approves on timeout.
        """
        policy = DEFAULT_GATE_POLICIES[HUMAN_APPROVE_ARCHIVE]
        assert policy.fallback == FallbackPolicy.HOLD

    def test_demo_and_archive_gates_notify_ops_channels(self) -> None:
        """GIVEN the demo and archive gate policies
        WHEN checking their notifications
        THEN email and slack channels are registered for production ops.
        """
        for gate_id in (HUMAN_APPROVE_DEMO, HUMAN_APPROVE_ARCHIVE):
            notifications = DEFAULT_GATE_POLICIES[gate_id].notifications
            assert "email" in notifications
            assert "slack" in notifications

    def test_existing_gates_preserved(self) -> None:
        """GIVEN the existing human gates
        WHEN adding the demo and archive gates
        THEN all prior gate IDs remain registered (append, not overwrite).
        """
        for gate_id in _PREEXISTING_GATES:
            assert gate_id in HUMAN_GATE_IDS
            assert gate_id in DEFAULT_GATE_POLICIES


class TestDemoGateFailClosed:
    """REQ-38: autonomous mode never auto-approves the new gates."""

    @pytest.mark.asyncio
    async def test_orchestrator_applies_hold_fallback_for_demo_gate(self) -> None:
        """GIVEN autonomous mode with HUMAN_APPROVE_DEMO pending and no callback
        WHEN the gate fires before go-live
        THEN the orchestrator applies the HOLD fallback — never auto-approves.
        """
        orchestrator = HumanGateOrchestrator()
        decision = await orchestrator.on_gate(HUMAN_APPROVE_DEMO, _ctx(HUMAN_APPROVE_DEMO))

        assert decision.action != GateDecisionAction.APPROVE
        assert "HOLD" in decision.reason
        assert decision.decided_by == "system"

    @pytest.mark.asyncio
    async def test_orchestrator_applies_hold_fallback_for_archive_gate(self) -> None:
        """GIVEN autonomous mode with HUMAN_APPROVE_ARCHIVE pending and no callback
        WHEN the gate fires before close
        THEN the orchestrator applies the HOLD fallback — never auto-approves.
        """
        orchestrator = HumanGateOrchestrator()
        decision = await orchestrator.on_gate(
            HUMAN_APPROVE_ARCHIVE, _ctx(HUMAN_APPROVE_ARCHIVE)
        )

        assert decision.action != GateDecisionAction.APPROVE
        assert "HOLD" in decision.reason
        assert decision.decided_by == "system"

    @pytest.mark.asyncio
    async def test_fail_closed_callback_never_approves_new_gates(self) -> None:
        """GIVEN orchestrated mode with no callback registered
        WHEN fail_closed_callback fires for either new gate
        THEN the decision is HOLD and never approved.
        """
        for gate_id in (HUMAN_APPROVE_DEMO, HUMAN_APPROVE_ARCHIVE):
            decision = await fail_closed_callback(_ctx(gate_id))
            assert decision.action == GateDecisionAction.HOLD
            assert not decision.is_approved()
            assert decision.gate_id == gate_id


class TestDemoGateQuestionTool:
    """REQ-38 scenario 4: question-tool resolution for the new gates."""

    @pytest.mark.asyncio
    async def test_demo_gate_resolvable_via_question_tool(self, tmp_path) -> None:
        """GIVEN orchestrated mode with a pending demo gate
        WHEN the choice envelope is presented via the question tool
        THEN the human decision file resolves the gate to APPROVE.
        """
        callback = QuestionToolGateCallback(
            gate_event_dir=str(tmp_path),
            campaign_id="camp-demo-1",
            poll_interval=0.01,
            timeout=10,
        )
        task = asyncio.create_task(callback(_ctx(HUMAN_APPROVE_DEMO)))

        pending = pending_path(str(tmp_path), "camp-demo-1", HUMAN_APPROVE_DEMO)
        for _ in range(200):
            if pending.exists():
                break
            await asyncio.sleep(0.01)
        assert pending.exists(), "callback must write the pending file"
        assert json.loads(pending.read_text())["gate_id"] == HUMAN_APPROVE_DEMO

        decision_file = decision_path(str(tmp_path), "camp-demo-1", HUMAN_APPROVE_DEMO)
        decision_file.write_text(
            json.dumps({"action": "approve", "reason": "demo ok", "decided_by": "human"})
        )

        decision = await asyncio.wait_for(task, timeout=10)
        assert decision.gate_id == HUMAN_APPROVE_DEMO
        assert decision.action == GateDecisionAction.APPROVE
        assert decision.reason == "demo ok"

    @pytest.mark.asyncio
    async def test_archive_gate_denial_blocks_via_question_tool(self, tmp_path) -> None:
        """GIVEN orchestrated mode with a pending archive gate
        WHEN the human denies via the question tool
        THEN the decision is REJECT (denial blocks the phase).
        """
        callback = QuestionToolGateCallback(
            gate_event_dir=str(tmp_path),
            campaign_id="camp-demo-1",
            poll_interval=0.01,
            timeout=10,
        )
        task = asyncio.create_task(callback(_ctx(HUMAN_APPROVE_ARCHIVE)))

        pending = pending_path(str(tmp_path), "camp-demo-1", HUMAN_APPROVE_ARCHIVE)
        for _ in range(200):
            if pending.exists():
                break
            await asyncio.sleep(0.01)

        decision_file = decision_path(str(tmp_path), "camp-demo-1", HUMAN_APPROVE_ARCHIVE)
        decision_file.write_text(
            json.dumps({"action": "reject", "reason": "not yet", "decided_by": "human"})
        )

        decision = await asyncio.wait_for(task, timeout=10)
        assert decision.action == GateDecisionAction.REJECT
        assert decision.is_terminal()
