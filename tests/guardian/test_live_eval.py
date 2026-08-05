"""Tests for MetaGuardian live evaluation — REQ-40.

Verifies ``guardian.live.evaluate_live`` computes live drawdown from the
streamed demo-account equity, transitions to DEFENSIVE when drawdown exceeds
10%, records the transition for feedback (REQ-34), and holds (no live-based
transition) when no stream data is available — fail-closed (REQ-40 scenario
2).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from quantlab.guardian.live import (
    LiveEvaluation,
    evaluate_live,
    max_drawdown,
)
from quantlab.guardian.models import PortfolioState
from quantlab.readers.models import EquityPoint


def _curve(values: list[float]) -> list[EquityPoint]:
    return [
        EquityPoint(timestamp=datetime.now(timezone.utc), equity=v)
        for v in values
    ]


class TestMaxDrawdown:
    """Pure drawdown math over the equity curve."""

    def test_peak_to_trough_drawdown(self) -> None:
        """GIVEN equity rising then falling
        WHEN max_drawdown runs
        THEN the peak-to-trough drawdown fraction is returned.
        """
        points = _curve([100.0, 120.0, 108.0, 96.0])
        assert max_drawdown(points) == pytest.approx(0.20)

    def test_monotonic_rise_has_zero_drawdown(self) -> None:
        """GIVEN an equity curve that never falls
        WHEN max_drawdown runs
        THEN the drawdown is 0.0.
        """
        assert max_drawdown(_curve([100.0, 101.0, 102.0])) == 0.0

    def test_single_point_has_zero_drawdown(self) -> None:
        """GIVEN a single equity point
        WHEN max_drawdown runs
        THEN the drawdown is 0.0 (no trough to measure).
        """
        assert max_drawdown(_curve([100.0])) == 0.0

    def test_drawdown_measures_from_latest_peak(self) -> None:
        """GIVEN a recovery that stays below a prior peak
        WHEN max_drawdown runs
        THEN the deepest trough below the running peak is measured.
        """
        points = _curve([100.0, 90.0, 95.0, 85.0, 92.0])
        assert max_drawdown(points) == pytest.approx(0.15)  # 85 vs peak 100


class TestEvaluateLive:
    """REQ-40: live drawdown drives the DEFENSIVE transition."""

    def test_drawdown_above_threshold_transitions_defensive(self) -> None:
        """GIVEN a live stream with drawdown > 10%
        WHEN evaluate_live runs
        THEN the state transitions to DEFENSIVE and the transition is
        recorded for feedback (REQ-40 scenario 1).
        """
        result = evaluate_live(
            _curve([100.0, 100.0, 88.0]),  # drawdown 0.12
            campaign_id="camp-live-dd",
        )

        assert isinstance(result, LiveEvaluation)
        assert result.state == PortfolioState.DEFENSIVE
        assert result.transitioned is True
        assert result.drawdown == pytest.approx(0.12)
        assert result.feedback is not None
        assert result.feedback.signals.drawdown == pytest.approx(0.12)
        assert result.feedback.signals.degradation is True

    def test_drawdown_at_threshold_does_not_transition(self) -> None:
        """GIVEN live drawdown exactly at 10% (not above)
        WHEN evaluate_live runs
        THEN no transition occurs (threshold is strictly ``>``).
        """
        result = evaluate_live(_curve([100.0, 90.0]), campaign_id="camp-x")

        assert result.drawdown == pytest.approx(0.10)
        assert result.transitioned is False
        assert result.state == PortfolioState.NORMAL
        assert result.feedback is None

    def test_drawdown_below_threshold_stays_normal(self) -> None:
        """GIVEN live drawdown under 10%
        WHEN evaluate_live runs
        THEN the state stays NORMAL and no feedback is recorded.
        """
        result = evaluate_live(_curve([100.0, 95.0]), campaign_id="camp-y")

        assert result.transitioned is False
        assert result.state == PortfolioState.NORMAL
        assert result.feedback is None

    def test_empty_stream_holds_no_transition(self) -> None:
        """GIVEN no live stream data
        WHEN evaluate_live would evaluate
        THEN evaluation holds with a STREAM_LOST reason and no live-based
        transition occurs (REQ-40 scenario 2, fail-closed).
        """
        result = evaluate_live([], campaign_id="camp-z")

        assert result.held is True
        assert result.transitioned is False
        assert result.state is None
        assert result.feedback is None
        assert "STREAM_LOST" in result.reason


class TestFeedbackLoop:
    """REQ-34 linkage: the DEFENSIVE transition feeds next-cycle inputs."""

    def test_transition_feedback_reaches_next_cycle_inputs(self) -> None:
        """GIVEN a DEFENSIVE live transition
        WHEN the feedback record is reshaped for next-cycle generation
        THEN the degradation and drawdown signals are present.
        """
        result = evaluate_live(
            _curve([100.0, 100.0, 88.0]),
            campaign_id="camp-next",
        )
        inputs = result.feedback.next_cycle_inputs()

        assert inputs["degradation"] is True
        assert inputs["drawdown"] == pytest.approx(0.12)
        assert inputs["campaign_id"] == "camp-next"
