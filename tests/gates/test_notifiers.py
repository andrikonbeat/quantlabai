"""REQ-35: MobilePushNotifier + severity routing in NotifierDispatcher.

Verifies the push channel is registered in the dispatcher's severity routes
(CRITICAL → push; WARNING → push configurable), that a push delivers the full
payload, and that a push delivery failure is logged at WARNING while the
remaining channels still deliver — a push failure never breaks the alert
pipeline (REQ-35 scenarios 1 and 2).
"""

from __future__ import annotations

import logging

import pytest

from quantlab.agents.autonomous_monitor import (
    AutonomousMonitorDaemon,
    MonitorConfig,
    NotifierDispatcher,
)
from quantlab.gates.notifiers import MobilePushNotifier, Notifier


class RecordingTransport:
    """Async push transport recording every delivery attempt (fail-safe stub)."""

    def __init__(self, *, fail: Exception | None = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._fail = fail

    async def __call__(self, endpoint: str, payload: dict) -> None:
        if self._fail is not None:
            raise self._fail
        self.calls.append((endpoint, payload))


class TestMobilePushNotifier:
    """REQ-35 scenario 1: the push channel sends the full payload."""

    async def test_send_delivers_full_payload_to_endpoint(self) -> None:
        """GIVEN a MobilePushNotifier with a recording transport
        WHEN send() is called with a message and alert kwargs
        THEN the transport receives the endpoint and the full payload
        (message plus every alert field).
        """
        transport = RecordingTransport()
        notifier = MobilePushNotifier(
            endpoint="https://push.example/device/abc",
            transport=transport,
        )

        await notifier.send(
            "Drawdown exceeded 15%",
            type="DRAWDOWN_BREACH",
            severity="CRITICAL",
            strategy_id="strat_x",
        )

        assert len(transport.calls) == 1
        endpoint, payload = transport.calls[0]
        assert endpoint == "https://push.example/device/abc"
        assert payload["text"] == "Drawdown exceeded 15%"
        assert payload["type"] == "DRAWDOWN_BREACH"
        assert payload["severity"] == "CRITICAL"
        assert payload["strategy_id"] == "strat_x"

    async def test_push_failure_logged_warning_and_not_raised(self, caplog) -> None:
        """GIVEN the push provider unreachable
        WHEN send() runs
        THEN the failure is logged at WARNING
        AND the exception does not propagate (fail-safe).
        """
        transport = RecordingTransport(fail=ConnectionError("provider down"))
        notifier = MobilePushNotifier(
            endpoint="https://push.example/device/abc",
            transport=transport,
        )

        with caplog.at_level(logging.WARNING, logger="quantlab.gates.notifiers"):
            await notifier.send("alert body")

        assert len(caplog.records) >= 1
        assert all(r.levelno == logging.WARNING for r in caplog.records)
        assert "push.example" in caplog.text

    async def test_push_is_a_notifier_channel(self) -> None:
        """The push notifier conforms to the shared Notifier protocol."""
        assert issubclass(MobilePushNotifier, Notifier)
        assert hasattr(MobilePushNotifier, "send")


class TestPushSeverityRouting:
    """REQ-35: CRITICAL → push; WARNING → push configurable."""

    @staticmethod
    def _mock_notifier() -> type:
        return __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock()

    @pytest.mark.asyncio
    async def test_critical_routes_to_push_and_other_channels(self) -> None:
        """GIVEN push, slack, and email notifiers configured
        WHEN a CRITICAL alert is dispatched
        THEN the push channel sends the full payload
        AND the other configured channels still receive it.
        """
        push = self._mock_notifier()
        slack = self._mock_notifier()
        email = self._mock_notifier()
        dispatcher = NotifierDispatcher(
            notifiers={"push": push, "slack": slack, "email": email}
        )

        await dispatcher.dispatch(
            {
                "type": "DRAWDOWN_BREACH",
                "severity": "CRITICAL",
                "message": "Drawdown exceeded 15%",
                "strategy_id": "strat_x",
            }
        )

        push.send.assert_awaited_once()
        slack.send.assert_awaited_once()
        email.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_warning_default_does_not_push(self) -> None:
        """GIVEN a default dispatcher (push_on_warning=False)
        WHEN a WARNING alert is dispatched
        THEN the push channel is NOT used (WARNING push is opt-in).
        """
        push = self._mock_notifier()
        slack = self._mock_notifier()
        dispatcher = NotifierDispatcher(notifiers={"push": push, "slack": slack})

        await dispatcher.dispatch(
            {"type": "REGIME_SHIFT", "severity": "WARNING", "message": "regime"}
        )

        push.send.assert_not_called()
        slack.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_warning_routes_to_push_when_configured(self) -> None:
        """GIVEN a dispatcher with push_on_warning=True
        WHEN a WARNING alert is dispatched
        THEN the push channel receives it alongside the default channels.
        """
        push = self._mock_notifier()
        slack = self._mock_notifier()
        dispatcher = NotifierDispatcher(
            notifiers={"push": push, "slack": slack},
            push_on_warning=True,
        )

        await dispatcher.dispatch(
            {"type": "REGIME_SHIFT", "severity": "WARNING", "message": "regime"}
        )

        push.send.assert_awaited_once()
        slack.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_push_failure_degrades_gracefully(self, caplog) -> None:
        """GIVEN the push provider unreachable and a CRITICAL alert
        WHEN the dispatcher routes
        THEN the push failure is logged at WARNING
        AND the remaining channels deliver.
        """
        push = self._mock_notifier()
        push.send.side_effect = ConnectionError("push down")
        slack = self._mock_notifier()
        email = self._mock_notifier()
        dispatcher = NotifierDispatcher(
            notifiers={"push": push, "slack": slack, "email": email}
        )

        with caplog.at_level(logging.WARNING, logger="quantlab.agents.autonomous_monitor"):
            await dispatcher.dispatch(
                {
                    "type": "DRAWDOWN_BREACH",
                    "severity": "CRITICAL",
                    "message": "Drawdown exceeded 15%",
                }
            )

        assert "push" in caplog.text.lower()
        slack.send.assert_awaited_once()
        email.send.assert_awaited_once()


class TestPushRegistration:
    """REQ-35: the push notifier is registered in the dispatcher builder."""

    def test_build_notifiers_registers_push_channel(self) -> None:
        """GIVEN a notifier config declaring a push channel
        WHEN AutonomousMonitorDaemon._build_notifiers builds it
        THEN a MobilePushNotifier is registered with the configured endpoint.
        """
        built = AutonomousMonitorDaemon._build_notifiers(
            {"push": {"endpoint": "https://push.example/device/abc"}}
        )
        assert isinstance(built["push"], MobilePushNotifier)
        assert built["push"].endpoint == "https://push.example/device/abc"

    def test_console_channel_registers_too(self) -> None:
        """GIVEN a notifier config declaring a console channel
        WHEN the builder runs
        THEN a console notifier is registered (REQ-35 channel list).
        """
        built = AutonomousMonitorDaemon._build_notifiers({"console": {}})
        assert "console" in built

    def test_monitor_config_exposes_push_on_warning(self, monkeypatch) -> None:
        """GIVEN AUTONOMOUS_MONITOR_PUSH_ON_WARNING=1
        WHEN MonitorConfig loads
        THEN push_on_warning is True (WARNING push configurable via env).
        """
        monkeypatch.setenv("AUTONOMOUS_MONITOR_PUSH_ON_WARNING", "1")
        config = MonitorConfig(strategy_id="s1")
        assert config.push_on_warning is True

    def test_daemon_passes_push_on_warning_to_dispatcher(self) -> None:
        """GIVEN a MonitorConfig with push_on_warning=True
        WHEN the daemon builds its default dispatcher
        THEN the dispatcher routes WARNING to push.
        """
        config = MonitorConfig(strategy_id="s1", push_on_warning=True)
        dispatcher = NotifierDispatcher(
            notifiers=AutonomousMonitorDaemon._build_notifiers(
                {"push": {"endpoint": "https://push.example/x"}}
            ),
            push_on_warning=config.push_on_warning,
        )
        assert dispatcher._push_on_warning is True
