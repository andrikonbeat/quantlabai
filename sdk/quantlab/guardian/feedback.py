"""Guardian live feedback records — REQ-34.

``record(campaign_id, signals)`` captures MetaGuardian live evaluations
(degradation, drawdown, regime, cost) into a :class:`FeedbackRecord` that is
attached at campaign archive and feeds next-cycle generation inputs.

This module is intentionally **pure** — it imports no gate machinery and
resolves no human gate. Feedback MUST NOT alter the 14-phase flow order
(REQ-37) or bypass human gates (REQ-34 scenario 2); by construction it cannot,
because it never touches ``quantlab.gates``. Persistence is the caller's job
(e.g. the archive bundle embeds the returned record).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class FeedbackSignals:
    """Live-evaluation signals captured for a campaign (REQ-34).

    Attributes:
        degradation: True when MetaGuardian reports the deployed strategy
            DEGRADING during the demo window.
        drawdown: Maximum live drawdown fraction (0.0–1.0).
        regime: Detected market regime label (e.g. ``"TREND"``).
        cost: Measured trading cost in basis points.
    """

    degradation: bool = False
    drawdown: float = 0.0
    regime: str = ""
    cost: float = 0.0


@dataclass(frozen=True)
class FeedbackRecord:
    """A persisted feedback record for one campaign (REQ-34).

    Attached at campaign archive and consumed by next-cycle generation as
    inputs. Additive only — creating a record never modifies flow order or
    human-gate state.
    """

    campaign_id: str
    signals: FeedbackSignals
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    record_id: str = field(default_factory=lambda: uuid4().hex)
    source: str = "metaguardian"

    def suggests_replacement(self) -> bool:
        """True when the recorded signals indicate a degrading strategy."""
        return self.signals.degradation

    def next_cycle_inputs(self) -> dict[str, Any]:
        """Reshape the signals for the next generation cycle (REQ-34).

        The returned mapping is the input handed to reconfiguration /
        next-cycle research — it must expose every captured signal.
        """
        return {
            "campaign_id": self.campaign_id,
            "degradation": self.signals.degradation,
            "drawdown": self.signals.drawdown,
            "regime": self.signals.regime,
            "cost": self.signals.cost,
            "recorded_at": self.recorded_at.isoformat(),
            "source": self.source,
        }


def record(
    campaign_id: str,
    signals: FeedbackSignals,
    *,
    source: str = "metaguardian",
    recorded_at: datetime | None = None,
) -> FeedbackRecord:
    """Create a feedback record for *campaign_id* from live signals (REQ-34).

    Args:
        campaign_id: Campaign identifier the record belongs to.
        signals: Live-evaluation signals (degradation/drawdown/regime/cost).
        source: Origin label for the record (default ``"metaguardian"``).
        recorded_at: Record timestamp override (default: now, UTC).

    Returns:
        A new :class:`FeedbackRecord`. The caller persists it (e.g. by
        attaching it to the campaign archive bundle).
    """
    return FeedbackRecord(
        campaign_id=campaign_id,
        signals=signals,
        recorded_at=recorded_at or datetime.now(timezone.utc),
        source=source,
    )
