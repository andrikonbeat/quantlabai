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

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Sequence
from uuid import uuid4

from quantlab.readers.models import EquityPoint


@dataclass(frozen=True)
class FeedbackSignals:
    """Live-evaluation signals captured for a campaign (REQ-34).

    Attributes:
        degradation: True when MetaGuardian reports the deployed strategy
            DEGRADING during the demo window.
        drawdown: Maximum live drawdown fraction (0.0–1.0).
        regime: Detected market regime label (e.g. ``"TREND"``).
        cost: Measured trading cost in basis points.
        parameter_matrix_delta: Parameter names flagged for review in the
            next research cycle (live confidence < 0.3, REQ-34 parameter
            matrix feedback). Empty when no parameter underperforms.
    """

    degradation: bool = False
    drawdown: float = 0.0
    regime: str = ""
    cost: float = 0.0
    parameter_matrix_delta: tuple[str, ...] = ()


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
            "parameter_matrix_delta": list(self.signals.parameter_matrix_delta),
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

def flag_matrix_deltas(
    confidence_map: dict[str, float],
    threshold: float = 0.3,
) -> tuple[str, ...]:
    """Flag parameters whose live confidence falls below *threshold* (REQ-34).

    Parameters with live performance confidence < 0.3 are flagged for review
    in the next research cycle. Pure and deterministic — no side effects.

    Args:
        confidence_map: Mapping of parameter name → live confidence (0.0-1.0).
        threshold: Confidence below which a parameter is flagged (default 0.3).

    Returns:
        Tuple of flagged parameter names in mapping order.
    """
    return tuple(
        name
        for name, confidence in confidence_map.items()
        if isinstance(confidence, (int, float)) and confidence < threshold
    )


# Bounded orchestrator→guardian directive kinds (REQ-643). Directives are
# limited to evaluation and advice — none can auto-approve, reorder, or
# gate the flow, and any other kind is rejected at construction.
DIRECTIVE_KINDS: tuple[str, ...] = (
    "evaluate",
    "live_ops_status",
    "escalation_ack",
)


@dataclass(frozen=True)
class GuardianDirective:
    """An orchestrator→guardian directive, bounded to evaluation + advice (REQ-643).

    The guardian agent accepts exactly three directive kinds — ``evaluate``
    (run a Guardian evaluation), ``live_ops_status`` (report current live-ops
    state), and ``escalation_ack`` (acknowledge an ops-surface escalation,
    REQ-36). Any other kind raises :class:`ValueError` BEFORE any execution
    begins, so a directive can never mutate the 14-phase flow (REQ-37) or
    bypass a human gate.

    Attributes:
        kind: The bounded directive kind.
        campaign_id: Campaign the directive applies to.
        alert_id: Escalation alert id to acknowledge (``escalation_ack``).
        points: Live equity points for the evaluation (``evaluate``); ``None``
            or empty means no live signal is available (feedback stays None).
        research_config: Research config handed to the evaluation stage.
    """

    kind: Literal["evaluate", "live_ops_status", "escalation_ack"]
    campaign_id: str
    alert_id: str | None = None
    points: Sequence[EquityPoint] | Iterable[EquityPoint] | None = None
    research_config: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in DIRECTIVE_KINDS:
            raise ValueError(
                f"unknown GuardianDirective kind {self.kind!r} — bounded to "
                f"{', '.join(DIRECTIVE_KINDS)} (REQ-643)"
            )


@dataclass(frozen=True)
class GuardianReport:
    """Guardian→orchestrator report envelope (REQ-644, REQ-34 envelope).

    The feedback channel from the guardian agent back to the orchestrator:
    it carries the evaluation ``guardian_state`` plus the :class:`FeedbackRecord`
    whose ``next_cycle_inputs()`` reshape is consumed by next-cycle generation
    (REQ-34). The report carries NO gate or flow fields (REQ-643) and claims
    only escalation alert ids that were actually acknowledged (REQ-36).

    Attributes:
        guardian_state: Evaluation state produced by the guardian stage
            (e.g. ``portfolio_state``), always carried even without signals.
        feedback: The FeedbackRecord payload, or ``None`` when the evaluation
            produced no live signals (REQ-644 scenario 2).
        live_ops_status: Current live-ops status, or ``None``.
        escalations_acked: Escalation alert ids acknowledged via the ops
            surface — never fabricated (REQ-36).
    """

    guardian_state: dict[str, Any] | None
    feedback: FeedbackRecord | None = None
    live_ops_status: dict[str, Any] | None = None
    escalations_acked: tuple[str, ...] = ()


def build_report(
    *,
    guardian_state: dict[str, Any] | None,
    feedback: FeedbackRecord | None = None,
    live_ops_status: dict[str, Any] | None = None,
    escalations_acked: tuple[str, ...] = (),
) -> GuardianReport:
    """Build the guardian→orchestrator report envelope (REQ-644).

    Pure constructor. The envelope REUSES the :class:`FeedbackRecord` — the
    next-cycle generation flow consumes ``report.feedback.next_cycle_inputs()``
    (REQ-34), so the reshape stays canonical. ``escalations_acked`` records
    only ids the ops surface actually returned as acknowledged (REQ-36).

    Args:
        guardian_state: Evaluation state (``None`` when no evaluation ran).
        feedback: FeedbackRecord payload, or ``None`` when no live signals.
        live_ops_status: Live-ops status dict, or ``None``.
        escalations_acked: Acknowledged alert ids — never fabricated.

    Returns:
        A new :class:`GuardianReport`.
    """
    return GuardianReport(
        guardian_state=guardian_state,
        feedback=feedback,
        live_ops_status=live_ops_status,
        escalations_acked=tuple(escalations_acked),
    )


@dataclass(frozen=True)
class LiveDemoFeed:
    """A live demo-account feed sample (REQ-34 live demo account feed).

    Carries the live stream of demo-account equity, positions, and costs that
    MetaGuardian consumes for real-time state transitions. ``source`` MUST be
    ``"live-demo"``; backtest samples are rejected by
    :func:`record_demo_feedback` so the live feed can never be spoofed by
    backtest data (REQ-34 scenario 2).
    """

    equity: float = 0.0
    positions: int = 0
    costs: float = 0.0
    source: str = "live-demo"


def record_demo_feedback(
    campaign_id: str,
    feed: LiveDemoFeed,
    *,
    degradation: bool = False,
    drawdown: float = 0.0,
    regime: str = "",
    cost: float = 0.0,
    parameter_matrix_delta: tuple[str, ...] = (),
) -> FeedbackRecord:
    """Record live demo-account feedback (REQ-34 live demo account feed).

    Wires a :class:`LiveDemoFeed` sample into a :class:`FeedbackRecord` that
    is attached at campaign archive and consumed by next-cycle generation.
    Purely additive — the 14-phase flow order and human gates are never
    touched (REQ-37).

    Args:
        campaign_id: Campaign identifier the record belongs to.
        feed: Live demo-account feed sample (equity/positions/costs).
        degradation: True when MetaGuardian reports the deployed strategy
            DEGRADING during the demo window.
        drawdown: Maximum live drawdown fraction (0.0-1.0).
        regime: Detected market regime label.
        cost: Measured trading cost in basis points.
        parameter_matrix_delta: Parameter names flagged for review in the
            next research cycle (live confidence < 0.3).

    Raises:
        ValueError: When *feed* does not originate from the live demo account
            (``source != "live-demo"``) — backtest data must not masquerade
            as the live feed.
    """
    if feed.source != "live-demo":
        raise ValueError(
            "live demo feedback requires a live-demo feed, got "
            f"source={feed.source!r} (backtest data must not spoof the live "
            "demo account)"
        )
    signals = FeedbackSignals(
        degradation=degradation,
        drawdown=drawdown,
        regime=regime,
        cost=cost,
        parameter_matrix_delta=tuple(parameter_matrix_delta),
    )
    return FeedbackRecord(
        campaign_id=campaign_id,
        signals=signals,
        source="live-demo",
    )
