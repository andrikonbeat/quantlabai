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
    LiveDemoFeed,
    flag_matrix_deltas,
    record,
    record_demo_feedback,
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

class TestParameterMatrixDelta:
    """REQ-34: parameter matrix deltas feed the next research cycle."""

    def test_parameter_below_threshold_is_flagged(self) -> None:
        """GIVEN a parameter with live confidence 0.2 (< 0.3)
        WHEN flag_matrix_deltas() evaluates the matrix
        THEN the parameter is flagged for review.
        """
        flagged = flag_matrix_deltas({"sl_atr": 0.2, "tp_ratio": 0.8})
        assert "sl_atr" in flagged
        assert "tp_ratio" not in flagged

    def test_confidence_at_threshold_is_not_flagged(self) -> None:
        """GIVEN a parameter with live confidence exactly 0.3
        WHEN flag_matrix_deltas() evaluates the matrix
        THEN it is NOT flagged (strictly below the threshold).
        """
        assert flag_matrix_deltas({"sl_atr": 0.3}) == ()

    def test_next_cycle_inputs_carry_the_delta(self) -> None:
        """GIVEN a record with a parameter matrix delta
        WHEN next_cycle_inputs() is called
        THEN next-cycle research receives the flag list (REQ-34).
        """
        result = record(
            "camp-8",
            FeedbackSignals(
                degradation=True,
                parameter_matrix_delta=("sl_atr", "stop_loss_atr"),
            ),
        )
        inputs = result.next_cycle_inputs()
        assert inputs["parameter_matrix_delta"] == ["sl_atr", "stop_loss_atr"]

    def test_no_delta_defaults_to_empty_list(self) -> None:
        """GIVEN a record without matrix deltas
        THEN next_cycle_inputs() exposes an empty delta list.
        """
        inputs = record("camp-9", FeedbackSignals()).next_cycle_inputs()
        assert inputs["parameter_matrix_delta"] == []


class TestLiveDemoFeed:
    """REQ-34: the live demo-account feed is wired into the feedback record."""

    def test_live_demo_feed_produces_feedback_record(self) -> None:
        """GIVEN a live demo-account feed sample
        WHEN record_demo_feedback() runs
        THEN a FeedbackRecord is produced carrying the live signals.
        """
        feed = LiveDemoFeed(equity=100_000.0, positions=3, costs=1.4)
        result = record_demo_feedback(
            "camp-live-1",
            feed,
            degradation=True,
            drawdown=0.12,
            regime="TREND",
            cost=1.4,
            parameter_matrix_delta=("sl_atr",),
        )

        assert result.campaign_id == "camp-live-1"
        assert result.source == "live-demo"
        assert result.signals.degradation is True
        assert result.signals.drawdown == 0.12
        assert result.signals.parameter_matrix_delta == ("sl_atr",)
        assert result.next_cycle_inputs()["parameter_matrix_delta"] == ["sl_atr"]

    def test_backtest_feed_is_rejected(self) -> None:
        """GIVEN a feed sample sourced from backtest data
        WHEN record_demo_feedback() runs
        THEN ValueError is raised — backtest data must not spoof the live feed.
        """
        backtest = LiveDemoFeed(equity=99_000.0, positions=2, costs=0.0, source="backtest")
        with pytest.raises(ValueError):
            record_demo_feedback("camp-live-2", backtest)
