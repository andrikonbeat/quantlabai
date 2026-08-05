"""24-7 Ops Surface — mobile escalation for Guardian transitions and demo-window expiry (REQ-36).

The ops surface is the daemon-mode alerting + acknowledgement layer:

- **Guardian escalation**: on a worsening Guardian state transition
  (NORMAL → VIGILANCE → DEFENSIVE → QUARANTINE) a CRITICAL push alert
  carrying the new state and a reason is dispatched (overnight escalation
  scenario). The ``on_transition`` hook plugs directly into
  ``MetaGuardianOrchestrator.action_hooks``; ``escalate`` is the async path
  used by the daemon's live evaluation.
- **Demo window expiry**: when the 14-business-day demo window expires, a
  ``DEMO_WINDOW_EXPIRED`` alert is fired (renewal blocked pending the
  HUMAN_APPROVE_DEMO gate).
- **Ack**: every alert is recorded with an id and can be acknowledged via
  ``ack()`` — the acknowledgement is persisted on the alert record so a
  24-7 operator can confirm receipt from the ops surface.

Dispatch goes through the shared ``NotifierDispatcher`` (duck-typed): the
CRITICAL route reaches the mobile push channel (REQ-35) and push failures are
logged, never raised — escalation can never break the daemon loop.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from quantlab.guardian.models import PortfolioState
from quantlab.phase4.demo_deploy import DemoWindow

logger = logging.getLogger(__name__)

# Escalation ladder — rank is used to detect worsening transitions only
# (RECOVERY is deliberately absent: improving transitions never escalate).
_ESCALATION_RANK: dict[PortfolioState, int] = {
    PortfolioState.NORMAL: 0,
    PortfolioState.VIGILANCE: 1,
    PortfolioState.DEFENSIVE: 2,
    PortfolioState.QUARANTINE: 3,
}

# States whose *worsening* transitions fire a push (REQ-36 ladder).
DEFAULT_PUSH_LEVELS: frozenset[PortfolioState] = frozenset(
    {
        PortfolioState.VIGILANCE,
        PortfolioState.DEFENSIVE,
        PortfolioState.QUARANTINE,
    }
)


def escalation_rank(state: PortfolioState) -> int:
    """Rank *state* on the escalation ladder (NORMAL=0 … QUARANTINE=3).

    States outside the ladder (e.g. RECOVERY) rank ``-1`` and therefore can
    never be escalation targets.
    """
    return _ESCALATION_RANK.get(state, -1)


@dataclass(frozen=True)
class EscalationAlert:
    """An escalation alert recorded on the ops surface (REQ-36).

    Attributes:
        alert_id: Stable, short unique identifier (uuid hex).
        campaign_id: Campaign the alert belongs to.
        kind: ``GUARDIAN_ESCALATION`` or ``DEMO_WINDOW_EXPIRED``.
        state: Resulting PortfolioState value, or ``None`` (expiry alerts).
        reason: Human-readable escalation reason.
        severity: Alert severity (escalations are always ``CRITICAL``).
        created_at: UTC creation timestamp.
        acked: True once acknowledged via the ops surface.
        acked_at: UTC acknowledgement timestamp, else ``None``.
    """

    alert_id: str
    campaign_id: str
    kind: str
    state: str | None
    reason: str
    severity: str
    created_at: datetime
    acked: bool
    acked_at: datetime | None

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe dict serialisation (for MCP tools / audit)."""
        return {
            "alert_id": self.alert_id,
            "campaign_id": self.campaign_id,
            "kind": self.kind,
            "state": self.state,
            "reason": self.reason,
            "severity": self.severity,
            "created_at": self.created_at.isoformat(),
            "acked": self.acked,
            "acked_at": self.acked_at.isoformat() if self.acked_at else None,
        }


class OpsSurface:
    """Records, dispatches and acknowledges escalation alerts (REQ-36).

    The surface is dispatcher-agnostic: it needs any object with an async
    ``dispatch(alert_dict)`` method (``NotifierDispatcher`` satisfies this),
    so no import cycle is created with the daemon.
    """

    def __init__(
        self,
        dispatcher: Any | None = None,
        *,
        push_levels: frozenset[PortfolioState] = DEFAULT_PUSH_LEVELS,
    ) -> None:
        """Initialise the surface.

        Args:
            dispatcher: Optional object exposing ``async dispatch(dict)``
                (e.g. ``NotifierDispatcher``). When ``None`` alerts are
                recorded but never dispatched (pure-ack mode).
            push_levels: States whose worsening transitions escalate.
        """
        self._dispatcher = dispatcher
        self._push_levels = frozenset(push_levels)
        self._alerts: dict[str, EscalationAlert] = {}
        self._pending: list[EscalationAlert] = []
        self._dispatch_tasks: set[asyncio.Task[None]] = set()

    # ── Public record API ──────────────────────────────────────────────────

    def escalate_record(
        self,
        campaign_id: str,
        state: PortfolioState,
        *,
        reason: str = "",
    ) -> EscalationAlert:
        """Record a GUARDIAN_ESCALATION alert without dispatching it."""
        return self._record(
            campaign_id=campaign_id,
            kind="GUARDIAN_ESCALATION",
            state=state.value,
            reason=reason or f"Guardian escalated to {state.value}",
        )

    async def escalate(
        self,
        campaign_id: str,
        state: PortfolioState,
        *,
        reason: str = "",
    ) -> EscalationAlert:
        """Record AND dispatch a GUARDIAN_ESCALATION alert (async path)."""
        alert = self.escalate_record(campaign_id, state, reason=reason)
        await self._dispatch_alert(alert)
        return alert

    def on_transition(
        self,
        old_state: PortfolioState,
        new_state: PortfolioState,
        *,
        campaign_id: str = "portfolio",
        reason: str = "",
    ) -> EscalationAlert | None:
        """Guardian action-hook: escalate worsening transitions (REQ-36).

        Plugs into ``MetaGuardianOrchestrator``'s ``action_hooks``
        (``Callable[[old_state, new_state], None]``). Escalation is
        one-directional — only a strictly worsening transition into a push
        level fires an alert, so recovery never re-alerts the operator.
        """
        if not self._should_escalate(old_state, new_state):
            return None
        alert = self.escalate_record(campaign_id, new_state, reason=reason)
        self._schedule_dispatch(alert)
        return alert

    def demo_window_expired(
        self,
        campaign_id: str,
        window: DemoWindow,
        today: date,
    ) -> EscalationAlert | None:
        """Fire a DEMO_WINDOW_EXPIRED alert when the window has expired.

        Returns ``None`` while the window is still active/reminder-due.
        """
        if not window.is_expired(today):
            return None
        alert = self._record(
            campaign_id=campaign_id,
            kind="DEMO_WINDOW_EXPIRED",
            state=None,
            reason=(
                f"demo window expired {window.expires_at.isoformat()} — "
                "renewal blocked pending HUMAN_APPROVE_DEMO"
            ),
        )
        self._schedule_dispatch(alert)
        return alert

    # ── Ack / inspection API ───────────────────────────────────────────────

    def ack(self, alert_id: str) -> EscalationAlert | None:
        """Acknowledge an alert via the ops surface.

        Returns the acknowledged alert, or ``None`` when the id is unknown.
        """
        alert = self._alerts.get(alert_id)
        if alert is None:
            return None
        acknowledged = replace(
            alert,
            acked=True,
            acked_at=datetime.now(timezone.utc),
        )
        self._alerts[alert_id] = acknowledged
        return acknowledged

    def get(self, alert_id: str) -> EscalationAlert | None:
        """Return the alert with *alert_id*, else ``None``."""
        return self._alerts.get(alert_id)

    def list_alerts(self) -> list[EscalationAlert]:
        """All recorded alerts (most recent first)."""
        return list(self._alerts.values())

    def pending_alerts(self) -> list[EscalationAlert]:
        """Alerts not yet acknowledged."""
        return [a for a in self._alerts.values() if not a.acked]

    async def flush_pending(self) -> None:
        """Dispatch queued alerts and await in-flight dispatch tasks.

        Deterministic test/daemon drain point: after calling the sync hooks
        (``on_transition`` / ``demo_window_expired``) from a context without
        a running loop, the queued alerts are dispatched here.
        """
        while self._pending:
            await self._dispatch_alert(self._pending.pop(0))
        if self._dispatch_tasks:
            await asyncio.gather(*list(self._dispatch_tasks))
            self._dispatch_tasks.clear()

    # ── Internals ──────────────────────────────────────────────────────────

    def _record(
        self,
        *,
        campaign_id: str,
        kind: str,
        state: str | None,
        reason: str,
    ) -> EscalationAlert:
        alert = EscalationAlert(
            alert_id=uuid4().hex[:12],
            campaign_id=campaign_id,
            kind=kind,
            state=state,
            reason=reason,
            severity="CRITICAL",
            created_at=datetime.now(timezone.utc),
            acked=False,
            acked_at=None,
        )
        self._alerts[alert.alert_id] = alert
        logger.info("OpsSurface: %s alert %s for %s", kind, alert.alert_id, campaign_id)
        return alert

    def _should_escalate(
        self, old_state: PortfolioState, new_state: PortfolioState
    ) -> bool:
        return (
            escalation_rank(new_state) > escalation_rank(old_state)
            and new_state in self._push_levels
        )

    def _schedule_dispatch(self, alert: EscalationAlert) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop (sync caller) — queue for flush_pending().
            self._pending.append(alert)
            return
        task = loop.create_task(self._dispatch_alert(alert))
        self._dispatch_tasks.add(task)
        task.add_done_callback(self._dispatch_tasks.discard)

    async def _dispatch_alert(self, alert: EscalationAlert) -> None:
        if self._dispatcher is None:
            return
        await self._dispatcher.dispatch(
            {
                "type": alert.kind,
                "severity": alert.severity,
                "message": f"{alert.kind}: {alert.reason}",
                "state": alert.state,
                "reason": alert.reason,
                "campaign_id": alert.campaign_id,
                "alert_id": alert.alert_id,
                "strategy_id": alert.campaign_id,
            }
        )
