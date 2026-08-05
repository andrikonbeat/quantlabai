"""REQ-36: 24-7 Ops Surface — daemon-mode mobile escalation + ack.

Verifies the ops surface:
- escalates Guardian state transitions (NORMAL → VIGILANCE → DEFENSIVE →
  QUARANTINE) by pushing an alert carrying state and reason (overnight
  escalation scenario),
- fires a push when the demo window expires,
- records every alert so it can be acknowledged via the ops surface.

Push delivery failures never raise (REQ-35 failure tolerance applies through
the shared NotifierDispatcher).
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

import pytest

from quantlab.guardian.models import PortfolioState
from quantlab.phase4.demo_deploy import DemoWindow


def _make_mock_notifier(name: str = "mock") -> AsyncMock:
    """Build a mock notifier with ``send`` as an async method."""
    notifier = AsyncMock(spec=["send"])
    notifier.send = AsyncMock()
    return notifier


@pytest.fixture
def push_and_slack() -> dict:
    """A dispatcher notifier dict with push + slack mocks."""
    return {"push": _make_mock_notifier(), "slack": _make_mock_notifier()}


def _surface_with(dispatcher):
    from quantlab.agents.ops_surface import OpsSurface

    return OpsSurface(dispatcher)


class TestGuardianEscalation:
    """REQ-36 scenario: an overnight DEFENSIVE transition escalates."""

    async def test_transition_escalates_push_with_state_and_reason(
        self, push_and_slack
    ) -> None:
        """GIVEN the daemon running with an ops surface
        WHEN a Guardian DEFENSIVE transition fires (overnight)
        THEN a CRITICAL push alert is dispatched with state and reason
        AND the other channels still receive it.
        """
        from quantlab.agents.autonomous_monitor import NotifierDispatcher

        dispatcher = NotifierDispatcher(notifiers=push_and_slack)
        surface = _surface_with(dispatcher)

        surface.on_transition(
            PortfolioState.NORMAL,
            PortfolioState.DEFENSIVE,
            campaign_id="camp-1",
            reason="live drawdown 12% above threshold",
        )
        await surface.flush_pending()

        push = push_and_slack["push"]
        push.send.assert_awaited_once()
        kwargs = push.send.await_args.kwargs
        assert kwargs["severity"] == "CRITICAL"
        assert kwargs["type"] == "GUARDIAN_ESCALATION"
        assert kwargs["state"] == "DEFENSIVE"
        assert "12%" in kwargs["reason"]

    async def test_transition_records_alert_acknowledgeable_via_surface(
        self, push_and_slack
    ) -> None:
        """GIVEN an escalation alert was fired
        WHEN it is acknowledged via the ops surface
        THEN the alert records the ack and leaves the pending set.
        """
        from quantlab.agents.autonomous_monitor import NotifierDispatcher

        dispatcher = NotifierDispatcher(notifiers=push_and_slack)
        surface = _surface_with(dispatcher)

        surface.on_transition(
            PortfolioState.NORMAL,
            PortfolioState.QUARANTINE,
            campaign_id="camp-1",
            reason="quarantine hit",
        )
        await surface.flush_pending()

        alert = surface.pending_alerts()[0]
        assert alert.acked is False
        assert surface.pending_alerts()  # not yet acked

        acknowledged = surface.ack(alert.alert_id)
        assert acknowledged is not None
        assert acknowledged.acked is True
        assert acknowledged.acked_at is not None
        assert surface.pending_alerts() == []

    def test_escalation_only_on_worsening_transition(self, push_and_slack) -> None:
        """GIVEN a recovery (improvement) transition
        WHEN it fires
        THEN no escalation alert is recorded (escalation is one-directional).
        """
        surface = _surface_with(None)

        surface.on_transition(
            PortfolioState.DEFENSIVE,
            PortfolioState.NORMAL,
            campaign_id="camp-1",
            reason="recovered",
        )

        assert surface.pending_alerts() == []
        assert surface.list_alerts() == []

    def test_no_escalation_on_flat_transition(self) -> None:
        """GIVEN a NORMAL → NORMAL transition
        WHEN it fires
        THEN no alert is recorded.
        """
        surface = _surface_with(None)
        surface.on_transition(
            PortfolioState.NORMAL, PortfolioState.NORMAL, campaign_id="camp-1"
        )
        assert surface.list_alerts() == []

    async def test_vigilance_transition_escalates(self, push_and_slack) -> None:
        """GIVEN a worsening NORMAL → VIGILANCE transition
        WHEN it fires
        THEN an escalation alert is dispatched.
        """
        from quantlab.agents.autonomous_monitor import NotifierDispatcher

        surface = _surface_with(NotifierDispatcher(notifiers=push_and_slack))
        surface.on_transition(
            PortfolioState.NORMAL,
            PortfolioState.VIGILANCE,
            campaign_id="camp-1",
            reason="regime shift",
        )
        await surface.flush_pending()
        push_and_slack["push"].send.assert_awaited_once()

    async def test_escalation_push_failure_does_not_raise(self, caplog) -> None:
        """GIVEN the push provider unreachable during an escalation
        WHEN the transition fires
        THEN the alert is still recorded and the failure is tolerated.
        """
        import logging

        from quantlab.agents.autonomous_monitor import NotifierDispatcher

        push = _make_mock_notifier()
        push.send.side_effect = ConnectionError("push down")
        surface = _surface_with(NotifierDispatcher(notifiers={"push": push}))

        with caplog.at_level(logging.WARNING, logger="quantlab.agents.autonomous_monitor"):
            surface.on_transition(
                PortfolioState.NORMAL,
                PortfolioState.DEFENSIVE,
                campaign_id="camp-1",
                reason="overnight drawdown",
            )
            await surface.flush_pending()

        assert surface.list_alerts()  # alert survived the push failure
        assert caplog.text  # failure was logged


class TestDemoWindowExpiry:
    """REQ-36: demo window expiry fires a push alert."""

    def test_expired_window_fires_alert(self, push_and_slack) -> None:
        """GIVEN the demo window is expired
        WHEN the expiry check runs
        THEN a DEMO_WINDOW_EXPIRED alert is fired.
        """
        from quantlab.agents.autonomous_monitor import NotifierDispatcher

        window = DemoWindow(started_at=date(2026, 7, 1))
        surface = _surface_with(NotifierDispatcher(notifiers=push_and_slack))

        alert = surface.demo_window_expired("camp-1", window, window.expires_at)

        assert alert is not None
        assert alert.kind == "DEMO_WINDOW_EXPIRED"
        assert alert.campaign_id == "camp-1"
        assert alert.state is None

    def test_active_window_no_alert(self, push_and_slack) -> None:
        """GIVEN the demo window is still active
        WHEN the expiry check runs
        THEN no alert is fired.
        """
        from quantlab.agents.autonomous_monitor import NotifierDispatcher

        window = DemoWindow(started_at=date(2026, 7, 1))
        surface = _surface_with(NotifierDispatcher(notifiers=push_and_slack))

        alert = surface.demo_window_expired("camp-1", window, window.started_at)

        assert alert is None
        assert surface.list_alerts() == []


class TestOpsSurfaceRecords:
    """REQ-36: alerts are first-class records on the ops surface."""

    def test_alert_to_dict_is_json_safe(self, push_and_slack) -> None:
        """GIVEN an escalation alert
        WHEN it is serialised
        THEN every field round-trips through JSON.
        """
        import json

        surface = _surface_with(None)
        alert = surface.escalate_record(
            "camp-1",
            PortfolioState.QUARANTINE,
            reason="hard breach",
        )

        data = alert.to_dict()
        assert data["alert_id"] == alert.alert_id
        assert data["kind"] == "GUARDIAN_ESCALATION"
        assert data["state"] == "QUARANTINE"
        assert data["acked"] is False
        assert json.loads(json.dumps(data))["state"] == "QUARANTINE"

    def test_ack_unknown_alert_returns_none(self) -> None:
        """GIVEN an unknown alert id
        WHEN ack runs
        THEN it returns None.
        """
        surface = _surface_with(None)
        assert surface.ack("does-not-exist") is None

    def test_escalate_record_returns_alert_without_dispatch(self) -> None:
        """GIVEN a surface with no dispatcher
        WHEN an escalation record is created
        THEN the alert is recorded but nothing raises.
        """
        surface = _surface_with(None)
        alert = surface.escalate_record("camp-1", PortfolioState.DEFENSIVE)
        assert surface.get(alert.alert_id) is alert
        assert alert.severity == "CRITICAL"


class TestDaemonWiring:
    """REQ-36: the daemon wires transitions into the ops surface."""

    async def test_daemon_escalates_on_transitioned_evaluation(self) -> None:
        """GIVEN a live feed breaching the drawdown threshold
        WHEN the daemon streams it and the evaluation transitions
        THEN an escalation alert is recorded on the ops surface.
        """
        from quantlab.agents.autonomous_monitor import (
            AutonomousMonitorDaemon,
            MonitorConfig,
        )
        from quantlab.agents.ops_surface import OpsSurface
        from quantlab.guardian.live import evaluate_live
        from quantlab.readers.models import EquityPoint

        surface = OpsSurface(None)
        daemon = AutonomousMonitorDaemon(
            MonitorConfig(strategy_id="s1"),
            dispatcher=None,
            ops_surface=surface,
        )

        def _feed(prices):
            import asyncio
            from datetime import datetime, timezone

            async def gen(_campaign_id: str | None = None):
                for price in prices:
                    yield EquityPoint(
                        timestamp=datetime.now(timezone.utc),
                        equity=float(price),
                    )
                    await asyncio.sleep(0)

            return gen

        window: list[EquityPoint] = []

        def evaluator(point: EquityPoint) -> object:
            window.append(point)
            if len(window) >= 3:
                return evaluate_live(list(window), campaign_id="camp-1")
            return None

        daemon.set_live_evaluator(evaluator)
        daemon._get_stream = _feed([100.0, 100.0, 88.0])

        async for _ in daemon.stream_live("camp-1"):
            pass

        assert surface.pending_alerts(), "expected an escalation alert"
        alert = surface.pending_alerts()[0]
        assert alert.kind == "GUARDIAN_ESCALATION"
        assert alert.state == "DEFENSIVE"

    def test_daemon_accepts_ops_surface_injection(self) -> None:
        """GIVEN an ops surface
        WHEN the daemon is constructed with it
        THEN the daemon exposes it and can swap it later.
        """
        from quantlab.agents.autonomous_monitor import (
            AutonomousMonitorDaemon,
            MonitorConfig,
        )
        from quantlab.agents.ops_surface import OpsSurface

        surface = OpsSurface(None)
        daemon = AutonomousMonitorDaemon(
            MonitorConfig(strategy_id="s1"), ops_surface=surface
        )
        assert daemon.ops_surface is surface

        replacement = OpsSurface(None)
        daemon.set_ops_surface(replacement)
        assert daemon.ops_surface is replacement
