"""Tests for the guardian orchestration agent glue — REQ-641/REQ-643/REQ-644.

``execute_guardian_directive`` is the SDK entry the ``quantlab-guardian``
subagent dispatches to. It wraps the EXISTING guardian stages — it MUST NOT
introduce a new pipeline phase (REQ-37) — reuses the ops surface for
escalation acks (REQ-36), and returns the bidirectional report envelope
carrying ``guardian_state`` plus the ``FeedbackRecord`` payload
(REQ-644 / REQ-34 envelope).

Threat-matrix RED-first: escalation ack integrity (unknown id is surfaced as
``None`` and NEVER fabricated, REQ-36), directive boundedness (report carries
no gate/flow fields, REQ-643), and flow integrity after a run (REQ-37).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from quantlab.campaign.flow import PHASES, STAGE_FOR_PHASE, assert_flow
from quantlab.guardian.agent import execute_guardian_directive
from quantlab.guardian.feedback import FeedbackRecord, GuardianDirective
from quantlab.guardian.models import PortfolioState
from quantlab.readers.models import EquityPoint

import quantlab.pipeline.stages as stages_pkg


class OpsSurface:
    """Minimal in-file double for the REQ-36 escalation-ack surface.

    The original ``quantlab.agents.ops_surface`` module was removed as dead
    code (repo-organization PR 1); the guardian agent only needs the
    duck-typed ``escalate_record``/``ack``/``get`` contract, so this stub
    preserves the ack round-trip tests without the deleted module.
    """

    def __init__(self, dispatcher=None) -> None:
        self._alerts: dict[str, _AlertRecord] = {}

    def escalate_record(self, campaign_id, state, reason=""):
        record = _AlertRecord(campaign_id)
        self._alerts[record.alert_id] = record
        return record

    def ack(self, alert_id):
        record = self._alerts.get(alert_id)
        if record is not None:
            record.acked = True
        return record

    def get(self, alert_id):
        return self._alerts.get(alert_id)


class _AlertRecord:
    _seq = 0

    def __init__(self, campaign_id: str) -> None:
        _AlertRecord._seq += 1
        self.alert_id = f"alert-{campaign_id}-{_AlertRecord._seq}"
        self.acked = False


def _point(equity: float) -> EquityPoint:
    """A single live-demo equity point (REQ-34 live feed shape)."""
    return EquityPoint(
        timestamp=datetime(2026, 8, 12, 10, 0, tzinfo=timezone.utc),
        equity=equity,
    )


class TestEscalationAck:
    """REQ-36: escalation ack round-trips the ops surface; ids never fabricated."""

    @pytest.mark.asyncio
    async def test_ack_round_trips_through_ops_surface(self) -> None:
        """GIVEN a recorded escalation alert on the ops surface
        WHEN an escalation_ack directive acknowledges it
        THEN the alert is acked AND the report claims exactly that id."""
        surface = OpsSurface()
        alert = surface.escalate_record(
            "camp-ack",
            PortfolioState.DEFENSIVE,
            reason="live drawdown above threshold",
        )

        report = await execute_guardian_directive(
            GuardianDirective(
                kind="escalation_ack",
                campaign_id="camp-ack",
                alert_id=alert.alert_id,
            ),
            ops_surface=surface,
        )

        acked = surface.get(alert.alert_id)
        assert acked is not None
        assert acked.acked is True
        assert report.escalations_acked == (alert.alert_id,)

    @pytest.mark.asyncio
    async def test_unknown_alert_id_is_surfaced_never_fabricated(self) -> None:
        """GIVEN an ack for an id the ops surface does not know
        WHEN the directive runs
        THEN ack() returns None surfaced as an empty claim — the report never
        fabricates a successful acknowledgement (REQ-36 threat row)."""
        surface = OpsSurface()

        report = await execute_guardian_directive(
            GuardianDirective(
                kind="escalation_ack",
                campaign_id="camp-ack",
                alert_id="alert-does-not-exist",
            ),
            ops_surface=surface,
        )

        assert report.escalations_acked == ()
        assert surface.get("alert-does-not-exist") is None

    @pytest.mark.asyncio
    async def test_ack_without_ops_surface_is_graceful_noop(self) -> None:
        """GIVEN no ops surface wired (default None)
        WHEN an escalation_ack directive runs
        THEN the report claims no acked ids — graceful no-op (design OQ)."""
        report = await execute_guardian_directive(
            GuardianDirective(
                kind="escalation_ack",
                campaign_id="camp-ack",
                alert_id="alert-1",
            )
        )
        assert report.escalations_acked == ()


class TestEvaluateDirective:
    """REQ-644: evaluate returns guardian_state plus the FeedbackRecord payload."""

    @pytest.mark.asyncio
    async def test_evaluate_report_carries_state_and_feedback(self) -> None:
        """GIVEN live points with drawdown above the 10% threshold
        WHEN the evaluate directive runs
        THEN the envelope carries guardian_state AND a FeedbackRecord whose
        next_cycle_inputs() expose the degradation signal (REQ-34)."""
        points = [_point(100_000.0), _point(85_000.0)]  # drawdown 0.15

        report = await execute_guardian_directive(
            GuardianDirective(
                kind="evaluate",
                campaign_id="camp-eval",
                points=points,
            )
        )

        assert report.guardian_state is not None
        assert "portfolio_state" in report.guardian_state
        assert isinstance(report.feedback, FeedbackRecord)
        inputs = report.feedback.next_cycle_inputs()
        assert inputs["degradation"] is True
        assert inputs["drawdown"] == 0.15
        assert inputs["campaign_id"] == "camp-eval"

    @pytest.mark.asyncio
    async def test_empty_points_feedback_none_state_still_carried(self) -> None:
        """GIVEN an evaluation with no live points (empty stream)
        WHEN the evaluate directive runs
        THEN feedback is None while guardian_state is still carried
        (REQ-644 scenario 2)."""
        report = await execute_guardian_directive(
            GuardianDirective(kind="evaluate", campaign_id="camp-eval", points=[])
        )

        assert report.feedback is None
        assert report.guardian_state is not None
        assert "portfolio_state" in report.guardian_state

    @pytest.mark.asyncio
    async def test_no_live_transition_feedback_none_state_carried(self) -> None:
        """GIVEN live points producing no state transition (no signals)
        WHEN the evaluate directive runs
        THEN the FeedbackRecord reflects no degradation (feedback is None,
        REQ-644 scenario 2) and the envelope still carries guardian_state."""
        points = [_point(100_000.0), _point(100_500.0)]  # no drawdown

        report = await execute_guardian_directive(
            GuardianDirective(
                kind="evaluate",
                campaign_id="camp-eval",
                points=points,
            )
        )

        assert report.feedback is None
        assert report.guardian_state is not None

    @pytest.mark.asyncio
    async def test_live_ops_status_without_archive_bundle_holds(self) -> None:
        """GIVEN a live_ops_status directive without an archive bundle
        WHEN the directive runs
        THEN the stage fails closed — status "hold", flow untouched
        (REQ-643 scenario: reports status without altering flow order)."""
        report = await execute_guardian_directive(
            GuardianDirective(kind="live_ops_status", campaign_id="camp-live")
        )

        assert report.live_ops_status is not None
        assert report.live_ops_status["status"] == "hold"
        assert report.guardian_state is None


class TestFlowIntegrityAfterRun:
    """REQ-37: the agent run must never add a phase or touch the flow/registry."""

    @pytest.mark.asyncio
    async def test_run_leaves_phases_at_14_and_registry_unchanged(self) -> None:
        """GIVEN the canonical flow and stage registry before a full agent run
        WHEN an evaluate directive executes
        THEN len(PHASES) is still 14, STAGE_FOR_PHASE is unchanged, the stage
        registry is unchanged, and assert_flow(PHASES) still passes."""
        phases_before = list(PHASES)
        stage_for_phase_before = dict(STAGE_FOR_PHASE)
        registry_before = sorted(
            name for name in dir(stages_pkg) if not name.startswith("_")
        )

        await execute_guardian_directive(
            GuardianDirective(
                kind="evaluate",
                campaign_id="camp-flow",
                points=[_point(100_000.0)],
            )
        )

        assert len(PHASES) == 14
        assert list(PHASES) == phases_before
        assert dict(STAGE_FOR_PHASE) == stage_for_phase_before
        assert (
            sorted(name for name in dir(stages_pkg) if not name.startswith("_"))
            == registry_before
        )
        assert_flow(PHASES)  # must not raise (REQ-37)

    def test_guardian_agent_module_imports_no_gate_machinery(self) -> None:
        """GIVEN the guardian agent module
        WHEN it is imported
        THEN it exposes no gate machinery — a directive cannot approve or
        gate the flow by construction (REQ-643)."""
        import quantlab.guardian.agent as agent

        assert not hasattr(agent, "HumanGateOrchestrator")
        assert not hasattr(agent, "GateDecision")
        assert not hasattr(agent, "on_gate")