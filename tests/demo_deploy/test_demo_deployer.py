"""Tests for DemoDeployer — REQ-31 deploy-window enforcement.

Covers: deploy proceeds inside the window; expiry blocks renewal pending
``HUMAN_APPROVE_DEMO`` (fail-closed, no deploy after expiry); the renewal
reminder is dispatched before expiry and on the expired path; and the
``QUANTLAB_DEMO_DRY_RUN`` rollback flag keeps dry-run on by default.
"""

from __future__ import annotations

from datetime import date

import pytest

from quantlab.phase4.demo_deploy import (
    DemoWindow,
    DemoWindowStatus,
    DemoDeployer,
    RenewalReminder,
    is_demo_dry_run,
)

_START = date(2026, 8, 3)
_EXPIRY = date(2026, 8, 21)
_REMINDER = date(2026, 8, 19)


class _RecordingDeployer:
    """Fake deployment backend — records calls, never touches the network."""

    def __init__(self, status: str = "DEPLOYED") -> None:
        self.status = status
        self.calls: list[tuple[object, object]] = []

    async def deploy(self, artifact: object, account: object) -> object:
        from quantlab.agents.deployment_agent import DeploymentResult

        self.calls.append((artifact, account))
        return DeploymentResult(status=self.status, jforex_package="demo.jar")


class _RecordingNotifier:
    """Fake reminder dispatcher — records reminders, returns them."""

    def __init__(self) -> None:
        self.reminders: list[RenewalReminder] = []

    def __call__(self, reminder: RenewalReminder) -> RenewalReminder:
        self.reminders.append(reminder)
        return reminder


class TestDemoDeployer:
    """REQ-31 deploy-window enforcement."""

    @pytest.mark.asyncio
    async def test_deploy_within_window_deploys_and_no_reminder(self) -> None:
        """GIVEN an approved deploy gate and an active demo window
        WHEN the demo phase runs
        THEN the strategy is deployed and NO renewal reminder fires yet.
        """
        backend = _RecordingDeployer()
        notifier = _RecordingNotifier()
        deployer = DemoDeployer(
            deploy_fn=backend.deploy,
            notifier_fn=notifier,
            window=DemoWindow(started_at=_START),
            campaign_id="camp-demo-1",
        )

        result = await deployer.deploy("demo.jfx", {"account": "acc-1"}, now=date(2026, 8, 5))

        assert result.status == "DEPLOYED"
        assert backend.calls == [("demo.jfx", {"account": "acc-1"})]
        assert notifier.reminders == [], "no reminder before the reminder date"

    @pytest.mark.asyncio
    async def test_deploy_when_reminder_due_deploys_and_reminds(self) -> None:
        """GIVEN the window in its final business days
        WHEN the demo phase runs
        THEN deployment proceeds AND a renewal reminder is scheduled before expiry.
        """
        backend = _RecordingDeployer()
        notifier = _RecordingNotifier()
        deployer = DemoDeployer(
            deploy_fn=backend.deploy,
            notifier_fn=notifier,
            window=DemoWindow(started_at=_START),
            campaign_id="camp-demo-1",
        )

        result = await deployer.deploy("demo.jfx", {"account": "acc-1"}, now=_REMINDER)

        assert result.status == "DEPLOYED"
        assert len(backend.calls) == 1
        assert len(notifier.reminders) == 1
        assert notifier.reminders[0].campaign_id == "camp-demo-1"
        assert "renewal" in notifier.reminders[0].message.lower()

    @pytest.mark.asyncio
    async def test_expired_window_blocks_pending_demo_gate(self) -> None:
        """GIVEN the demo window expired
        WHEN renewal is attempted
        THEN deployment blocks pending HUMAN_APPROVE_DEMO and never deploys.
        """
        backend = _RecordingDeployer()
        notifier = _RecordingNotifier()
        deployer = DemoDeployer(
            deploy_fn=backend.deploy,
            notifier_fn=notifier,
            window=DemoWindow(started_at=_START),
            campaign_id="camp-demo-1",
        )

        result = await deployer.deploy("demo.jfx", {"account": "acc-1"}, now=_EXPIRY)

        assert result.status == "BLOCKED_EXPIRED"
        assert result.pending_gate == "HUMAN_APPROVE_DEMO"
        assert backend.calls == [], "no deploy may run after the window expired"

    @pytest.mark.asyncio
    async def test_expired_window_dispatches_renewal_reminder(self) -> None:
        """GIVEN the demo window expired
        WHEN renewal is attempted
        THEN a renewal reminder is dispatched naming the required gate.
        """
        notifier = _RecordingNotifier()
        deployer = DemoDeployer(
            deploy_fn=_RecordingDeployer().deploy,
            notifier_fn=notifier,
            window=DemoWindow(started_at=_START),
            campaign_id="camp-demo-1",
        )

        await deployer.deploy("demo.jfx", {"account": "acc-1"}, now=_EXPIRY)

        assert len(notifier.reminders) == 1
        reminder = notifier.reminders[0]
        assert reminder.campaign_id == "camp-demo-1"
        assert reminder.due_on == _EXPIRY
        assert "HUMAN_APPROVE_DEMO" in reminder.message

    @pytest.mark.asyncio
    async def test_reminder_fires_exactly_once_on_expired_path(self) -> None:
        """GIVEN an expired window
        WHEN renewal is attempted
        THEN exactly one reminder is dispatched (no duplicate alerts).
        """
        notifier = _RecordingNotifier()
        deployer = DemoDeployer(
            deploy_fn=_RecordingDeployer().deploy,
            notifier_fn=notifier,
            window=DemoWindow(started_at=_START),
            campaign_id="camp-demo-1",
        )

        await deployer.deploy("demo.jfx", {"account": "acc-1"}, now=date(2026, 8, 25))

        assert len(notifier.reminders) == 1


class TestDemoDryRunRollback:
    """Rollback boundary: dry-run is the default; flag turns the live path on."""

    def test_dry_run_default_on_when_env_unset(self) -> None:
        """GIVEN no QUANTLAB_DEMO_DRY_RUN
        WHEN resolving the dry-run flag
        THEN it is True — the demo deploy path never goes live by default.
        """
        assert is_demo_dry_run({}) is True
        assert is_demo_dry_run(None) is True

    def test_dry_run_flag_opt_out(self) -> None:
        """GIVEN QUANTLAB_DEMO_DRY_RUN=0
        WHEN resolving the dry-run flag
        THEN it is False — the live path may run explicitly.
        """
        assert is_demo_dry_run({"QUANTLAB_DEMO_DRY_RUN": "0"}) is False
        assert is_demo_dry_run({"QUANTLAB_DEMO_DRY_RUN": "1"}) is True
