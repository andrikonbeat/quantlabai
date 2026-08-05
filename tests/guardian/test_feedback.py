"""Tests for Guardian live feedback records — REQ-34.

Verifies ``guardian.feedback.record(campaign_id, signals)`` produces a
``FeedbackRecord`` carrying degradation/drawdown/regime/cost signals that is
attached at campaign archive and feeds next-cycle generation inputs, and that
the feedback path NEVER alters human gates or the flow order (REQ-34 scenario
2: "Feedback never bypasses gates").
"""

from __future__ import annotations

import asyncio

import pytest

from quantlab.gates.models import GateDecisionAction, HUMAN_GATE_IDS
from quantlab.gates.orchestrator import HumanGateOrchestrator
from quantlab.guardian import feedback
from quantlab.guardian.feedback import (
    FeedbackRecord,
    FeedbackSignals,
    record,
)


class TestRecord:
    """REQ-34: record() produces a persisted-able feedback record."""

    def test_record_creates_feedback_record_with_signals(self) -> None:
        """GIVEN degradation/drawdown/regime/cost signals
        WHEN record(campaign_id, signals) runs
        THEN a FeedbackRecord is produced carrying every signal.
        """
        result = record(
            "camp-archive-1",
            FeedbackSignals(
                degradation=True,
                drawdown=0.12,
                regime="TREND",
                cost=2.0,
            ),
        )

        assert isinstance(result, FeedbackRecord)
        assert result.campaign_id == "camp-archive-1"
        assert result.signals.degradation is True
        assert result.signals.drawdown == 0.12
        assert result.signals.regime == "TREND"
        assert result.signals.cost == 2.0
        assert result.recorded_at is not None
        assert result.record_id != ""

    def test_record_preserves_all_signal_fields(self) -> None:
        """GIVEN a different signal set
        WHEN record() runs
        THEN every field round-trips exactly (no default swallowing).
        """
        result = record(
            "camp-2",
            FeedbackSignals(degradation=False, drawdown=0.03, regime="RANGE", cost=0.5),
        )

        assert result.campaign_id == "camp-2"
        assert result.signals.degradation is False
        assert result.signals.drawdown == 0.03
        assert result.signals.regime == "RANGE"
        assert result.signals.cost == 0.5

    def test_record_detects_degradation(self) -> None:
        """GIVEN a record reporting degradation
        WHEN suggests_replacement() is asked
        THEN it signals a replacement candidate (REQ-34/REQ-33 linkage).
        """
        result = record("camp-3", FeedbackSignals(degradation=True))
        assert result.suggests_replacement() is True

    def test_record_healthy_does_not_suggest_replacement(self) -> None:
        """GIVEN a record with no degradation
        WHEN suggests_replacement() is asked
        THEN it does NOT suggest replacement.
        """
        result = record("camp-4", FeedbackSignals(degradation=False))
        assert result.suggests_replacement() is False


class TestNextCycleInputs:
    """REQ-34 scenario 1: next-cycle generation receives the degradation signal."""

    def test_next_cycle_inputs_carry_degradation_signal(self) -> None:
        """GIVEN a degrading strategy feedback record
        WHEN next_cycle_inputs() is called
        THEN the degradation signal is present for the generation flow.
        """
        result = record(
            "camp-5",
            FeedbackSignals(degradation=True, drawdown=0.15, regime="TREND", cost=1.2),
        )
        inputs = result.next_cycle_inputs()

        assert inputs["degradation"] is True
        assert inputs["drawdown"] == 0.15
        assert inputs["regime"] == "TREND"
        assert inputs["cost"] == 1.2
        assert inputs["campaign_id"] == "camp-5"


class TestGatesNeverBypassed:
    """REQ-34 scenario 2: feedback never bypasses human gates."""

    def test_feedback_module_does_not_import_gate_machinery(self) -> None:
        """GIVEN the feedback module
        WHEN it is imported
        THEN it exposes no gate machinery — the feedback path cannot
        approve or resolve a human gate by construction.
        """
        assert not hasattr(feedback, "HumanGateOrchestrator")
        assert not hasattr(feedback, "GateDecision")
        assert not hasattr(feedback, "on_gate")

    @pytest.mark.asyncio
    async def test_record_leaves_human_gates_in_force(self) -> None:
        """GIVEN live drawdown data recorded as feedback
        WHEN the archive gate fires afterwards
        THEN the gate still holds (no auto-approve) — gates remain in force.
        """
        record("camp-6", FeedbackSignals(degradation=True, drawdown=0.11))

        orchestrator = HumanGateOrchestrator()
        decision = await orchestrator.on_gate(
            "HUMAN_APPROVE_ARCHIVE",
            {"gate_id": "HUMAN_APPROVE_ARCHIVE", "campaign_id": "camp-6"},
        )

        assert decision.action != GateDecisionAction.APPROVE
        assert decision.decided_by == "system"

    def test_record_does_not_alter_gate_registry(self) -> None:
        """GIVEN the gate registry before recording feedback
        WHEN record() runs
        THEN HUMAN_GATE_IDS is unchanged — feedback is additive only.
        """
        before = list(HUMAN_GATE_IDS)
        record("camp-7", FeedbackSignals(drawdown=0.04))
        assert HUMAN_GATE_IDS == before
