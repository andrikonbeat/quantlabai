"""Demo deploy window enforcement — REQ-31.

The Dukascopy demo account (100 USD) is valid for a **14-business-day window**
(hard campaign-validity deadline, semi-manual renewal — the JForex demo is a
platform constraint, this module enforces the software deadline). Renewal is
semi-manual: a reminder fires ``reminder_days`` business days before expiry,
and after expiry any renewal attempt **blocks pending the human gate
``HUMAN_APPROVE_DEMO``** (REQ-38) — fail-closed, never auto-approves.

Rollback boundary: dry-run is the default (``QUANTLAB_DEMO_DRY_RUN`` unset →
``True``); set ``QUANTLAB_DEMO_DRY_RUN=0`` to allow the live path.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from typing import Any, Awaitable, Callable, Mapping

logger = logging.getLogger(__name__)

WINDOW_DAYS = 14  # business days of the Dukascopy demo window (REQ-31)
REMINDER_DAYS = 2  # business days before expiry the renewal reminder fires
DEMO_DRY_RUN_ENV = "QUANTLAB_DEMO_DRY_RUN"


# ── Business-day arithmetic (pure) ───────────────────────────────────────────


def add_business_days(start: date, days: int) -> date:
    """Return the date ``days`` business days after (or before) ``start``.

    Only Monday–Friday count as business days; weekends are skipped. Negative
    ``days`` walks backwards over weekends too (used for the pre-expiry
    reminder date).
    """
    if days == 0:
        return start
    step = 1 if days > 0 else -1
    current = start
    remaining = abs(days)
    while remaining:
        current += timedelta(days=step)
        if current.weekday() < 5:  # Mon..Fri
            remaining -= 1
    return current


# ── Window model (pure) ──────────────────────────────────────────────────────


class DemoWindowStatus(str, Enum):
    """State of the demo window relative to ``today``."""

    ACTIVE = "ACTIVE"  # deploy may proceed, no reminder yet
    REMINDER_DUE = "REMINDER_DUE"  # deploy proceeds, renewal reminder fires
    EXPIRED = "EXPIRED"  # renewal blocked pending HUMAN_APPROVE_DEMO


@dataclass(frozen=True)
class DemoWindow:
    """The 14-business-day demo window (REQ-31).

    Attributes:
        started_at: Date the demo window opened.
        window_days: Length of the window in business days (default 14).
        reminder_days: Business days before expiry the renewal reminder fires.
    """

    started_at: date
    window_days: int = WINDOW_DAYS
    reminder_days: int = REMINDER_DAYS

    @property
    def expires_at(self) -> date:
        """The date the window expires (14 business days after start)."""
        return add_business_days(self.started_at, self.window_days)

    @property
    def reminder_at(self) -> date:
        """The date the renewal reminder fires (before expiry)."""
        return add_business_days(self.expires_at, -self.reminder_days)

    def status(self, today: date) -> DemoWindowStatus:
        """Resolve the window status on ``today``."""
        if today >= self.expires_at:
            return DemoWindowStatus.EXPIRED
        if today >= self.reminder_at:
            return DemoWindowStatus.REMINDER_DUE
        return DemoWindowStatus.ACTIVE

    def is_expired(self, today: date) -> bool:
        """True when ``today`` is at or past the expiry date."""
        return self.status(today) is DemoWindowStatus.EXPIRED

    def reminder_due(self, today: date) -> bool:
        """True when the renewal reminder should fire on ``today``."""
        return self.status(today) is DemoWindowStatus.REMINDER_DUE


@dataclass(frozen=True)
class RenewalReminder:
    """A renewal reminder scheduled for a campaign (REQ-31)."""

    campaign_id: str
    due_on: date
    message: str


# ── Dry-run rollback flag ────────────────────────────────────────────────────


def is_demo_dry_run(env: Mapping[str, str] | None = None) -> bool:
    """Resolve the demo dry-run flag from ``QUANTLAB_DEMO_DRY_RUN``.

    Unset → ``True`` (dry-run default on — the rollback boundary). Only an
    explicit ``"0"`` / ``"false"`` opts into the live path.
    """
    value = (os.environ if env is None else env).get(DEMO_DRY_RUN_ENV, "")
    return value.strip().lower() not in ("0", "false")


# ── DemoDeployer ─────────────────────────────────────────────────────────────


class DemoDeployer:
    """Enforce the 14-business-day demo window around deployment (REQ-31).

    Args:
        deploy_fn: Async backend that performs the actual packaging/deploy.
            Signature ``async fn(artifact, account) -> DeploymentResult``.
            Defaults to the real ``DeploymentAgent.package_jfx`` path (dry-run
            default, wired in the deployment-agent slice — REQ-32).
        notifier_fn: Sync callback receiving the :class:`RenewalReminder`
            when one is due. Defaults to logging.
        window: The :class:`DemoWindow` to enforce. Defaults to a window that
            starts on the deploy date (first deploy — full 14-day validity).
        campaign_id: Campaign identifier used in reminders and results.
    """

    def __init__(
        self,
        *,
        deploy_fn: Callable[[Any, Any], Awaitable[Any]] | None = None,
        notifier_fn: Callable[[RenewalReminder], Any] | None = None,
        window: DemoWindow | None = None,
        campaign_id: str = "demo",
    ) -> None:
        self._deploy_fn = deploy_fn
        self._notifier_fn = notifier_fn
        self._window = window
        self._campaign_id = campaign_id

    # ── Public protocol ────────────────────────────────────────────────────────

    async def deploy(
        self,
        artifact: Any,
        account: Any,
        *,
        now: date | None = None,
    ) -> Any:
        """Deploy *artifact* to *account* inside the demo window (REQ-31).

        Behavior by window status on ``now`` (default: today):

        - ``ACTIVE`` — deploy through the backend; no reminder.
        - ``REMINDER_DUE`` — dispatch the renewal reminder, then deploy.
        - ``EXPIRED`` — **block**: dispatch the renewal reminder and return a
          ``BLOCKED_EXPIRED`` result pending ``HUMAN_APPROVE_DEMO``; the
          backend is never invoked (fail-closed, REQ-31 scenario 2).

        Returns:
            The backend's ``DeploymentResult``, or a ``BLOCKED_EXPIRED``
            result carrying ``pending_gate="HUMAN_APPROVE_DEMO"``.
        """
        today = now or date.today()
        window = self._window or DemoWindow(started_at=today)

        if window.is_expired(today):
            self._dispatch_renewal_reminder(window, today)
            logger.warning(
                "Demo window for %s expired on %s — renewal blocked pending "
                "HUMAN_APPROVE_DEMO",
                self._campaign_id,
                window.expires_at,
            )
            return self._blocked_result()

        if window.reminder_due(today):
            self._dispatch_renewal_reminder(window, today)

        return await self._run_deploy(artifact, account)

    # ── Internals ──────────────────────────────────────────────────────────────

    async def _run_deploy(self, artifact: Any, account: Any) -> Any:
        """Run the backend deploy, defaulting to the DeploymentAgent path."""
        deploy_fn = self._deploy_fn or self._default_deploy
        return await deploy_fn(artifact, account)

    async def _default_deploy(self, artifact: Any, account: Any) -> Any:
        """Lazy DeploymentAgent packaging (REQ-32) — imported lazily to keep
        ``phase4`` free of a module-level dependency on ``agents``."""
        from quantlab.agents.deployment_agent import DeploymentAgent

        agent = DeploymentAgent(dry_run=is_demo_dry_run())
        return await agent.package_jfx(artifact, account, campaign_id=self._campaign_id)

    def _dispatch_renewal_reminder(self, window: DemoWindow, today: date) -> RenewalReminder:
        """Dispatch the semi-manual renewal reminder (REQ-31)."""
        reminder = RenewalReminder(
            campaign_id=self._campaign_id,
            due_on=window.expires_at,
            message=(
                f"Demo window for {self._campaign_id} expires on "
                f"{window.expires_at.isoformat()} — renewal requires "
                "HUMAN_APPROVE_DEMO (REQ-38)."
            ),
        )
        if self._notifier_fn is not None:
            self._notifier_fn(reminder)
        else:
            logger.info("Renewal reminder: %s", reminder.message)
        return reminder

    def _blocked_result(self) -> Any:
        """Fail-closed result for an expired window (REQ-31 scenario 2)."""
        from quantlab.agents.deployment_agent import DeploymentResult

        return DeploymentResult(
            status="BLOCKED_EXPIRED",
            pending_gate="HUMAN_APPROVE_DEMO",
            errors=[
                f"Demo window expired — renewal blocked pending "
                "HUMAN_APPROVE_DEMO"
            ],
        )
