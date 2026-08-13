"""MetaGuardian live evaluation — REQ-40.

``evaluate_live`` evaluates the streamed demo-account equity (delivered by the
autonomous monitor, REQ-41) in addition to backtest-derived signals. A live
drawdown strictly above ``drawdown_threshold`` (default 10%) drives the state
to DEFENSIVE and records the transition as a Guardian feedback record
(REQ-34). When no live data is available the evaluation holds with a
STREAM_LOST reason and performs no live-based state transition (fail-closed,
REQ-40 scenario 2).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Sequence

from quantlab.guardian.feedback import FeedbackRecord, FeedbackSignals, record
from quantlab.guardian.models import PortfolioState
from quantlab.readers.models import EquityPoint

# Live drawdown threshold above which the state transitions to DEFENSIVE
# (REQ-40 scenario 1: drawdown > 10%).
DEFAULT_LIVE_DRAWDOWN_THRESHOLD = 0.10


def max_drawdown(points: Sequence[EquityPoint]) -> float:
    """Return the maximum peak-to-trough drawdown fraction of the curve.

    For every point the drawdown relative to the running equity peak is
    ``(peak - equity) / peak``; the maximum across the curve is returned
    (0.0 when the curve never falls below its peak).

    Args:
        points: Equity points in timestamp order (the live account feed).

    Returns:
        Maximum drawdown as a fraction in ``[0.0, 1.0]``.
    """
    peak: float = 0.0
    worst: float = 0.0
    for point in points:
        peak = max(peak, point.equity)
        if peak > 0:
            worst = max(worst, (peak - point.equity) / peak)
    return worst


@dataclass(frozen=True)
class LiveEvaluation:
    """Outcome of a MetaGuardian live evaluation (REQ-40).

    Attributes:
        campaign_id: Campaign the live feed belongs to.
        drawdown: Computed maximum live drawdown fraction.
        state: Resulting live state, or ``None`` while held (no data).
        transitioned: True when a live-based state transition occurred.
        held: True when evaluation held (STREAM_LOST — no live transition).
        feedback: FeedbackRecord attached on transition (REQ-34), else None.
        reason: Human-readable explanation of the outcome.
    """

    campaign_id: str
    drawdown: float
    state: PortfolioState | None
    transitioned: bool
    held: bool
    feedback: FeedbackRecord | None
    reason: str


def evaluate_live(
    points: Sequence[EquityPoint] | Iterable[EquityPoint],
    *,
    campaign_id: str = "campaign",
    drawdown_threshold: float = DEFAULT_LIVE_DRAWDOWN_THRESHOLD,
    source: str = "metaguardian",
) -> LiveEvaluation:
    """Evaluate live demo-account equity for a campaign (REQ-40).

    Args:
        points: Live equity points streamed by the autonomous monitor
            (REQ-41), or any iterable of equity points (e.g. a
            :class:`quantlab.jforex.live_feed.JForexLiveFeed`). Empty when
            the stream is unavailable.
        campaign_id: Campaign identifier for feedback records.
        drawdown_threshold: Drawdown fraction above which the state
            transitions to DEFENSIVE (default 0.10 = 10%, REQ-40).
        source: Origin label for any feedback record.

    Returns:
        A :class:`LiveEvaluation`. When ``points`` is empty the evaluation
        holds with a STREAM_LOST reason — no live-based transition occurs.
    """
    points_list = list(points)
    if not points_list:
        return LiveEvaluation(
            campaign_id=campaign_id,
            drawdown=0.0,
            state=None,
            transitioned=False,
            held=True,
            feedback=None,
            reason="STREAM_LOST — no live account data to evaluate",
        )

    dd = max_drawdown(points_list)
    if dd > drawdown_threshold:
        feedback = record(
            campaign_id,
            FeedbackSignals(
                degradation=True,
                drawdown=dd,
                regime="",
                cost=0.0,
            ),
            source=source,
        )
        return LiveEvaluation(
            campaign_id=campaign_id,
            drawdown=dd,
            state=PortfolioState.DEFENSIVE,
            transitioned=True,
            held=False,
            feedback=feedback,
            reason=(
                f"live drawdown {dd:.1%} above {drawdown_threshold:.1%} "
                "threshold — DEFENSIVE"
            ),
        )

    return LiveEvaluation(
        campaign_id=campaign_id,
        drawdown=dd,
        state=PortfolioState.NORMAL,
        transitioned=False,
        held=False,
        feedback=None,
        reason=(
            f"live drawdown {dd:.1%} within {drawdown_threshold:.1%} "
            "threshold — no transition"
        ),
    )
