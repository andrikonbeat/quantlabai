"""Campaign archive phase — REQ-33 (+ REQ-38 archive gate).

In the archive phase the system produces:

1. a **maintenance/replacement plan** for the deployed strategy based on live
   demo performance and Guardian degradation data (replacement candidates come
   from the campaign portfolio),
2. **account statistics** (equity, drawdown, P&L) over the demo window,
3. an **artifact bundle** stored for audit.

``HUMAN_APPROVE_ARCHIVE`` (REQ-38, registered in PR-4) holds the composed plan
for human confirmation: approval finalizes the archive; denial (or any
non-approval outcome, including the fail-closed HOLD fallback) returns the
campaign to maintenance. The gate is consumed on explicit ``action ==
APPROVE`` only — never on ``GateDecision.is_approved()`` (which returns True
for FALLBACK).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Sequence

from quantlab.gates.models import GateDecision, GateDecisionAction
from quantlab.guardian.feedback import FeedbackRecord
from quantlab.guardian.live import max_drawdown
from quantlab.guardian.models import StrategyState
from quantlab.readers.models import EquityPoint

logger = logging.getLogger(__name__)

ARCHIVE_GATE_ID = "HUMAN_APPROVE_ARCHIVE"

# Gate callback protocol: async ``fn(ctx: dict) -> GateDecision`` (matches
# ``quantlab.gates.orchestrator.GateCallback``).
GateCallback = Callable[[dict[str, Any]], Awaitable[GateDecision]]


# ── Account statistics (pure) ────────────────────────────────────────────────


@dataclass(frozen=True)
class AccountStats:
    """Account statistics over the demo window (REQ-33)."""

    start_equity: float
    end_equity: float
    max_drawdown: float
    pnl: float


def account_stats(
    points: Sequence[EquityPoint],
    *,
    start_equity: float | None = None,
) -> AccountStats:
    """Compute account statistics over the demo-window equity curve (REQ-33).

    Args:
        points: Equity points over the demo window (streamed by the
            autonomous monitor, REQ-41).
        start_equity: Window-starting balance; defaults to the first point.

    Returns:
        :class:`AccountStats` with end equity, P&L and max drawdown.
    """
    first = points[0].equity if points else 0.0
    start = start_equity if start_equity is not None else first
    end = points[-1].equity if points else start
    return AccountStats(
        start_equity=start,
        end_equity=end,
        max_drawdown=max_drawdown(points),
        pnl=end - start,
    )


# ── Maintenance / replacement plan (pure) ────────────────────────────────────


@dataclass(frozen=True)
class ReplacementCandidate:
    """A portfolio strategy proposed as a replacement (REQ-33)."""

    strategy_id: str
    reason: str


@dataclass(frozen=True)
class MaintenancePlan:
    """Maintenance/replacement plan for the deployed strategy (REQ-33)."""

    campaign_id: str
    deployed_strategy_id: str
    strategy_state: str
    recommendation: str  # "MAINTAIN" | "REPLACE"
    reason: str
    candidates: list[ReplacementCandidate] = field(default_factory=list)
    feedback: FeedbackRecord | None = None


def build_plan(
    *,
    campaign_id: str,
    deployed_strategy_id: str,
    strategy_state: StrategyState | str,
    portfolio_candidates: Sequence[str] = (),
    feedback: FeedbackRecord | None = None,
) -> MaintenancePlan:
    """Compose the archive maintenance/replacement plan (REQ-33 scenario 2).

    A DEGRADING strategy (Guardian report) or a feedback record that suggests
    replacement (REQ-34) yields a ``REPLACE`` recommendation whose candidates
    come from the campaign portfolio, excluding the deployed strategy itself.

    Args:
        campaign_id: Campaign identifier.
        deployed_strategy_id: Strategy currently deployed on the demo account.
        strategy_state: Guardian per-strategy state (e.g. DEGRADING).
        portfolio_candidates: Strategy IDs in the campaign portfolio.
        feedback: Optional feedback record attached at archive (REQ-34).
    """
    state = (
        strategy_state.value
        if isinstance(strategy_state, StrategyState)
        else str(strategy_state)
    )
    degrading = state == StrategyState.DEGRADING.value
    feedback_says_replace = feedback is not None and feedback.suggests_replacement()

    if degrading or feedback_says_replace:
        reasons = []
        if degrading:
            reasons.append(f"Guardian state {state}")
        if feedback_says_replace:
            reasons.append("live feedback reports degradation")
        candidates = [
            ReplacementCandidate(
                strategy_id=sid,
                reason="portfolio replacement candidate",
            )
            for sid in portfolio_candidates
            if sid != deployed_strategy_id
        ]
        return MaintenancePlan(
            campaign_id=campaign_id,
            deployed_strategy_id=deployed_strategy_id,
            strategy_state=state,
            recommendation="REPLACE",
            reason="; ".join(reasons) or "degraded performance",
            candidates=candidates,
            feedback=feedback,
        )

    return MaintenancePlan(
        campaign_id=campaign_id,
        deployed_strategy_id=deployed_strategy_id,
        strategy_state=state,
        recommendation="MAINTAIN",
        reason=f"Guardian state {state} — no replacement indicated",
        candidates=[],
        feedback=feedback,
    )


# ── Archive bundle ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ArchiveBundle:
    """Result of an archive phase run (REQ-33).

    Attributes:
        campaign_id: Campaign identifier.
        status: ``"ARCHIVED"`` when the human gate approved, ``"DENIED"``
            when the campaign returns to maintenance (REQ-38 scenario 3).
        plan: The composed maintenance/replacement plan.
        stats: Account statistics over the demo window.
        feedback: Feedback record attached at archive (REQ-34), if any.
        artifacts: Artifact bundle paths stored for audit.
        pending_gate: The gate that governed this archive.
        decision_action: Resolved gate action value (audit).
        archived_at: UTC timestamp when ARCHIVED, else ``None``.
    """

    campaign_id: str
    status: str
    plan: MaintenancePlan
    stats: AccountStats
    artifacts: list[str]
    feedback: FeedbackRecord | None = None
    pending_gate: str = ARCHIVE_GATE_ID
    decision_action: str = ""
    archived_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe audit record of the bundle."""
        return {
            "campaign_id": self.campaign_id,
            "status": self.status,
            "pending_gate": self.pending_gate,
            "decision_action": self.decision_action,
            "archived_at": (
                self.archived_at.isoformat() if self.archived_at else None
            ),
            "plan": {
                "deployed_strategy_id": self.plan.deployed_strategy_id,
                "strategy_state": self.plan.strategy_state,
                "recommendation": self.plan.recommendation,
                "reason": self.plan.reason,
                "candidates": [
                    {"strategy_id": c.strategy_id, "reason": c.reason}
                    for c in self.plan.candidates
                ],
            },
            "stats": {
                "start_equity": self.stats.start_equity,
                "end_equity": self.stats.end_equity,
                "max_drawdown": self.stats.max_drawdown,
                "pnl": self.stats.pnl,
            },
            "feedback": (
                self.feedback.next_cycle_inputs() if self.feedback else None
            ),
            "artifacts": list(self.artifacts),
        }


# ── ArchivePhase ─────────────────────────────────────────────────────────────


class ArchivePhase:
    """Run the archive phase with a HUMAN_APPROVE_ARCHIVE human gate (REQ-33).

    Args:
        gate_fn: Async gate callback returning a :class:`GateDecision`.
            Defaults to ``HumanGateOrchestrator.on_gate`` — with no callback
            registered the fail-closed HOLD fallback applies, so the archive
            never auto-finalizes.
    """

    def __init__(self, *, gate_fn: GateCallback | None = None, skip_gate: bool = False) -> None:
        self._gate_fn = gate_fn
        self._skip_gate = skip_gate

    async def run(
        self,
        campaign_id: str,
        *,
        strategy_state: StrategyState | str = StrategyState.ACTIVE,
        portfolio_candidates: Sequence[str] = (),
        feedback: FeedbackRecord | None = None,
        equity_points: Sequence[EquityPoint] = (),
        start_equity: float | None = None,
        artifacts: Sequence[str] = (),
        deployed_strategy_id: str = "",
        now: datetime | None = None,
    ) -> ArchiveBundle:
        """Run the archive phase for *campaign_id* (REQ-33).

        Composes the plan and statistics, then holds the plan for the
        ``HUMAN_APPROVE_ARCHIVE`` gate. Only an explicit ``APPROVE`` action
        finalizes the archive; every other outcome (REJECT, HOLD fallback,
        FALLBACK) returns the campaign to maintenance (status ``DENIED``).

        Returns:
            The :class:`ArchiveBundle` with the plan, stats and artifact
            bundle — or a ``DENIED`` bundle when the gate did not approve.
        """
        stats = account_stats(equity_points, start_equity=start_equity)
        plan = build_plan(
            campaign_id=campaign_id,
            deployed_strategy_id=deployed_strategy_id,
            strategy_state=strategy_state,
            portfolio_candidates=portfolio_candidates,
            feedback=feedback,
        )

        decision = None
        if not self._skip_gate:
            decision = await self._resolve_gate(campaign_id, plan)

        # Gate on the EXPLICIT action — never is_approved() (returns True for
        # FALLBACK; see PR-4 finding). When skip_gate=True the pipeline gate
        # owns the decision, so the bundle stays PENDING_GATE for the interceptor.
        if decision is None:
            return ArchiveBundle(
                campaign_id=campaign_id,
                status="PENDING_GATE",
                plan=plan,
                stats=stats,
                artifacts=list(artifacts),
                feedback=feedback,
                decision_action="",
                archived_at=None,
            )

        if decision.action != GateDecisionAction.APPROVE:
            logger.warning(
                "Archive gate for %s resolved %s — campaign returns to "
                "maintenance (denial blocks the phase, REQ-38 s3)",
                campaign_id,
                decision.action.value,
            )
            return ArchiveBundle(
                campaign_id=campaign_id,
                status="DENIED",
                plan=plan,
                stats=stats,
                artifacts=[],
                feedback=feedback,
                decision_action=decision.action.value,
                archived_at=None,
            )

        return ArchiveBundle(
            campaign_id=campaign_id,
            status="ARCHIVED",
            plan=plan,
            stats=stats,
            artifacts=list(artifacts),
            feedback=feedback,
            decision_action=decision.action.value,
            archived_at=now or datetime.now(timezone.utc),
        )

    # ── Gate resolution ───────────────────────────────────────────────────────

    async def _resolve_gate(
        self,
        campaign_id: str,
        plan: MaintenancePlan,
    ) -> GateDecision:
        """Resolve the HUMAN_APPROVE_ARCHIVE gate (REQ-38).

        Uses the injected ``gate_fn`` when provided; otherwise the standard
        ``HumanGateOrchestrator`` (no callback → fail-closed HOLD fallback).
        """
        ctx: dict[str, Any] = {
            "gate_id": ARCHIVE_GATE_ID,
            "campaign_id": campaign_id,
            "stage_name": "archive_phase",
            "context_artifacts": {
                "recommendation": plan.recommendation,
                "candidates": [c.strategy_id for c in plan.candidates],
                "strategy_state": plan.strategy_state,
            },
        }
        if self._gate_fn is not None:
            return await self._gate_fn(ctx)

        from quantlab.gates.orchestrator import HumanGateOrchestrator

        orchestrator = HumanGateOrchestrator()
        return await orchestrator.on_gate(ARCHIVE_GATE_ID, ctx)
