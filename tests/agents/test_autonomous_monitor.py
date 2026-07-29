"""Tests for autonomous monitor — MonitorConfig, NotifierDispatcher, AutoActionExecutor, and daemon.

RED phase: tests reference code that does not exist yet.
Covers tasks 1.2, 1.4, 4.1, 4.2, 4.3.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call

import pytest
import yaml

from quantlab.agents.autonomous_monitor import (
    AutoActionExecutor,
    AutonomousMonitorDaemon,
    MonitorConfig,
    NotifierDispatcher,
)
from quantlab.agents.monitoring_agent import MonitoringAgent
from quantlab.knowledge.store import TimeSeriesStore
from quantlab.readers.models import EquityPoint


class TestMonitorConfig:
    """MonitorConfig creation, YAML loading, and env-var override."""

    # ── Default values ─────────────────────────────────────────────────────────

    def test_default_values(self) -> None:
        """A config with only strategy_id uses spec defaults."""
        cfg = MonitorConfig(strategy_id="test_strat")
        assert cfg.strategy_id == "test_strat"
        assert cfg.drawdown_threshold == 0.15
        assert cfg.sharpe_degradation_pct == 0.4
        assert cfg.compute_interval == 60
        assert cfg.stream_timeout == 60
        assert cfg.heartbeat_interval == 30
        assert cfg.max_retries == 5
        assert cfg.knowledge_root == "knowledge"
        assert cfg.notifiers == {}

    def test_explicit_values(self) -> None:
        """Override every field explicitly."""
        cfg = MonitorConfig(
            strategy_id="explicit",
            drawdown_threshold=0.20,
            sharpe_degradation_pct=0.5,
            compute_interval=120,
            stream_timeout=90,
            heartbeat_interval=15,
            max_retries=3,
            knowledge_root="/tmp/knowledge",
            notifiers={"slack": {"webhook": "https://hooks.example.com"}},
        )
        assert cfg.drawdown_threshold == 0.20
        assert cfg.sharpe_degradation_pct == 0.5
        assert cfg.compute_interval == 120
        assert cfg.stream_timeout == 90
        assert cfg.heartbeat_interval == 15
        assert cfg.max_retries == 3
        assert cfg.knowledge_root == "/tmp/knowledge"
        assert cfg.notifiers["slack"]["webhook"] == "https://hooks.example.com"

    # ── YAML loading ──────────────────────────────────────────────────────────

    def test_from_yaml_full(self) -> None:
        """Load a fully-specified YAML config."""
        yaml_content = """
        strategy_id: yaml_strat
        drawdown_threshold: 0.25
        sharpe_degradation_pct: 0.6
        compute_interval: 300
        stream_timeout: 120
        heartbeat_interval: 60
        max_retries: 10
        knowledge_root: /custom/knowledge
        notifiers:
          slack:
            webhook: https://hooks.example.com/slack
        """
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            tmp_path = f.name

        try:
            cfg = MonitorConfig.from_yaml(tmp_path)
            assert cfg.strategy_id == "yaml_strat"
            assert cfg.drawdown_threshold == 0.25
            assert cfg.compute_interval == 300
            assert cfg.notifiers["slack"]["webhook"] == "https://hooks.example.com/slack"
        finally:
            os.unlink(tmp_path)

    def test_from_yaml_partial(self) -> None:
        """Partial YAML fills missing fields with defaults."""
        yaml_content = """
        strategy_id: partial_strat
        drawdown_threshold: 0.30
        """
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            tmp_path = f.name

        try:
            cfg = MonitorConfig.from_yaml(tmp_path)
            assert cfg.strategy_id == "partial_strat"
            assert cfg.drawdown_threshold == 0.30
            # Defaults for unset fields
            assert cfg.sharpe_degradation_pct == 0.4
            assert cfg.compute_interval == 60
            assert cfg.notifiers == {}
        finally:
            os.unlink(tmp_path)

    def test_from_yaml_minimal(self) -> None:
        """Minimal YAML with only strategy_id uses defaults everywhere else."""
        yaml_content = "strategy_id: minimal_strat\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            tmp_path = f.name

        try:
            cfg = MonitorConfig.from_yaml(tmp_path)
            assert cfg.strategy_id == "minimal_strat"
            assert cfg.drawdown_threshold == 0.15
            assert cfg.compute_interval == 60
        finally:
            os.unlink(tmp_path)

    # ── Environment variable overrides ─────────────────────────────────────────

    def test_env_override_float(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AUTONOMOUS_MONITOR_DRAWDOWN_THRESHOLD overrides the YAML value."""
        monkeypatch.setenv("AUTONOMOUS_MONITOR_DRAWDOWN_THRESHOLD", "0.35")
        cfg = MonitorConfig(strategy_id="env_test")
        assert cfg.drawdown_threshold == 0.35

    def test_env_override_int(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AUTONOMOUS_MONITOR_COMPUTE_INTERVAL overrides the default."""
        monkeypatch.setenv("AUTONOMOUS_MONITOR_COMPUTE_INTERVAL", "300")
        cfg = MonitorConfig(strategy_id="env_int")
        assert cfg.compute_interval == 300

    def test_env_override_precedence_over_yaml(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ENV var takes precedence over YAML value for the same key."""
        yaml_content = """
        strategy_id: prec_test
        drawdown_threshold: 0.10
        compute_interval: 60
        """
        monkeypatch.setenv("AUTONOMOUS_MONITOR_DRAWDOWN_THRESHOLD", "0.50")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            tmp_path = f.name

        try:
            cfg = MonitorConfig.from_yaml(tmp_path)
            # Env wins over YAML
            assert cfg.drawdown_threshold == 0.50
            # Non-overridden fields still come from YAML
            assert cfg.compute_interval == 60
        finally:
            os.unlink(tmp_path)

    def test_env_override_notifiers_not_affected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Env override of a numeric field does not clobber notifiers from YAML."""
        yaml_content = """
        strategy_id: notif_test
        notifiers:
          slack:
            webhook: https://hooks.example.com
        """
        monkeypatch.setenv("AUTONOMOUS_MONITOR_COMPUTE_INTERVAL", "999")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml_content)
            tmp_path = f.name

        try:
            cfg = MonitorConfig.from_yaml(tmp_path)
            assert cfg.compute_interval == 999
            assert cfg.notifiers["slack"]["webhook"] == "https://hooks.example.com"
        finally:
            os.unlink(tmp_path)

    def test_env_unknown_var_ignored(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unknown AUTONOMOUS_MONITOR_* vars are silently ignored."""
        monkeypatch.setenv("AUTONOMOUS_MONITOR_NONEXISTENT", "99")
        cfg = MonitorConfig(strategy_id="safe")
        # No crash, defaults preserved
        assert cfg.drawdown_threshold == 0.15
        assert cfg.compute_interval == 60

    def test_env_invalid_value_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Invalid env var values (non-numeric for float fields) fall back to default."""
        monkeypatch.setenv("AUTONOMOUS_MONITOR_DRAWDOWN_THRESHOLD", "not-a-number")
        cfg = MonitorConfig(strategy_id="fallback")
        # Should fall back to the YAML/default value without crashing
        assert cfg.drawdown_threshold == 0.15


# ── NotifierDispatcher ──────────────────────────────────────────────────────


class TestNotifierDispatcher:
    """NotifierDispatcher severity→channel routing and failure tolerance."""

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _make_mock_notifier(name: str = "mock") -> AsyncMock:
        """Build a mock notifier with ``send`` as an async method."""
        notifier = AsyncMock(spec=["send"])
        notifier.send = AsyncMock()
        return notifier

    # ── Routing ─────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_critical_routes_to_all_configured(self) -> None:
        """CRITICAL severity dispatches to ALL configured notifiers."""
        slack = self._make_mock_notifier()
        email = self._make_mock_notifier()
        webhook = self._make_mock_notifier()

        dispatcher = NotifierDispatcher(notifiers={
            "slack": slack,
            "email": email,
            "webhook": webhook,
        })

        await dispatcher.dispatch({
            "type": "DRAWDOWN_BREACH",
            "severity": "CRITICAL",
            "message": "Drawdown exceeded 15%",
        })

        slack.send.assert_awaited_once()
        email.send.assert_awaited_once()
        webhook.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_warning_routes_to_slack_and_webhook(self) -> None:
        """WARNING severity dispatches to slack and webhook, NOT email."""
        slack = self._make_mock_notifier()
        email = self._make_mock_notifier()
        webhook = self._make_mock_notifier()

        dispatcher = NotifierDispatcher(notifiers={
            "slack": slack,
            "email": email,
            "webhook": webhook,
        })

        await dispatcher.dispatch({
            "type": "SHARPE_DEGRADATION",
            "severity": "WARNING",
            "message": "Sharpe degraded 50%",
        })

        slack.send.assert_awaited_once()
        webhook.send.assert_awaited_once()
        email.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_info_routes_to_none(self) -> None:
        """INFO severity dispatches to NO notifiers (logged only)."""
        slack = self._make_mock_notifier()
        dispatcher = NotifierDispatcher(notifiers={"slack": slack})

        await dispatcher.dispatch({
            "type": "INFO",
            "severity": "INFO",
            "message": "Routine update",
        })

        slack.send.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_severity_falls_back_to_info(self) -> None:
        """Unknown severity defaults to INFO (no dispatch)."""
        slack = self._make_mock_notifier()
        dispatcher = NotifierDispatcher(notifiers={"slack": slack})

        await dispatcher.dispatch({
            "type": "TEST",
            "severity": "UNKNOWN_LEVEL",
            "message": "Test",
        })

        slack.send.assert_not_called()

    # ── Failure handling ────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_notifier_failure_logged_and_continues(self) -> None:
        """When a notifier raises, subsequent notifiers still receive the alert."""
        slack = self._make_mock_notifier()
        email = self._make_mock_notifier()
        webhook = self._make_mock_notifier()

        # First notifier in route order raises
        email.send.side_effect = RuntimeError("SMTP unavailable")

        dispatcher = NotifierDispatcher(notifiers={
            "slack": slack,
            "email": email,
            "webhook": webhook,
        })

        # Should not propagate the exception
        await dispatcher.dispatch({
            "type": "CRITICAL",
            "severity": "CRITICAL",
            "message": "Something broke",
        })

        # All should have been called despite email failure
        slack.send.assert_awaited_once()
        email.send.assert_awaited_once()  # was called, but raised
        webhook.send.assert_awaited_once()

    # ── Edge cases ──────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_empty_config_no_error(self) -> None:
        """No notifiers configured → dispatch completes without error."""
        dispatcher = NotifierDispatcher(notifiers={})
        await dispatcher.dispatch({
            "type": "DRAWDOWN_BREACH",
            "severity": "CRITICAL",
            "message": "Test",
        })
        # No assertion needed — just must not crash

    @pytest.mark.asyncio
    async def test_unknown_channel_skipped(self) -> None:
        """A channel name in the route table with no configured notifier is skipped."""
        slack = self._make_mock_notifier()
        dispatcher = NotifierDispatcher(notifiers={"slack": slack})
        # Critical routes to slack, email, webhook — only slack is configured
        await dispatcher.dispatch({
            "type": "DRAWDOWN_BREACH",
            "severity": "CRITICAL",
            "message": "Test",
        })
        slack.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_notifier_send_receives_alert_payload(self) -> None:
        """Notifier.send() receives the full alert dict as kwargs."""
        slack = self._make_mock_notifier()
        dispatcher = NotifierDispatcher(notifiers={"slack": slack})

        alert = {
            "type": "DRAWDOWN_BREACH",
            "severity": "CRITICAL",
            "message": "DD breach",
            "strategy_id": "strat_x",
            "details": {"current_dd": 0.18},
        }
        await dispatcher.dispatch(alert)

        slack.send.assert_awaited_once_with(
            "DD breach",
            **alert,
        )


# ── AutoActionExecutor ──────────────────────────────────────────────────────


class TestAutoActionExecutor:
    """AutoActionExecutor threshold-breach action dispatch."""

    @pytest.fixture
    def config(self) -> MonitorConfig:
        return MonitorConfig(strategy_id="test_strat")

    @pytest.fixture
    def store(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def executor(self, config: MonitorConfig, store: MagicMock) -> AutoActionExecutor:
        return AutoActionExecutor(config, store)

    # ── Stop-strategy ───────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_stop_strategy_on_drawdown_breach(
        self,
        executor: AutoActionExecutor,
    ) -> None:
        """CRITICAL DRAWDOWN_BREACH with stop_strategy enabled dispatches stop."""
        action = await executor.execute({
            "type": "DRAWDOWN_BREACH",
            "severity": "CRITICAL",
            "strategy_id": "test_strat",
        })

        assert len(action) == 1
        assert action[0]["action"] == "stop_strategy"
        assert action[0]["strategy_id"] == "test_strat"
        assert action[0]["status"] == "dispatched"

    @pytest.mark.asyncio
    async def test_stop_strategy_skipped_when_disabled(
        self,
        config: MonitorConfig,
        store: MagicMock,
    ) -> None:
        """DRAWDOWN_BREACH does NOT trigger stop_strategy when disabled."""
        executor = AutoActionExecutor(config, store, enabled_actions={})
        action = await executor.execute({
            "type": "DRAWDOWN_BREACH",
            "severity": "CRITICAL",
            "strategy_id": "test_strat",
        })
        assert len(action) == 0

    # ── Reduce position ─────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_reduce_position_on_regime_shift(
        self,
        executor: AutoActionExecutor,
    ) -> None:
        """WARNING REGIME_SHIFT with reduce_position enabled reduces 50%."""
        action = await executor.execute({
            "type": "REGIME_SHIFT",
            "severity": "WARNING",
            "strategy_id": "test_strat",
        })

        assert len(action) == 1
        assert action[0]["action"] == "reduce_position"
        assert action[0]["reduction_pct"] == 50

    @pytest.mark.asyncio
    async def test_reduce_position_skipped_when_disabled(
        self,
        config: MonitorConfig,
        store: MagicMock,
    ) -> None:
        executor = AutoActionExecutor(config, store, enabled_actions={})
        action = await executor.execute({
            "type": "REGIME_SHIFT",
            "severity": "WARNING",
            "strategy_id": "test_strat",
        })
        assert len(action) == 0

    # ── Re-optimize ─────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_re_optimize_on_sharpe_degradation(
        self,
        executor: AutoActionExecutor,
    ) -> None:
        """WARNING SHARPE_DEGRADATION with re_optimize enabled triggers re-opt."""
        action = await executor.execute({
            "type": "SHARPE_DEGRADATION",
            "severity": "WARNING",
            "strategy_id": "test_strat",
        })

        assert len(action) == 1
        assert action[0]["action"] == "re_optimize"
        assert action[0]["strategy_id"] == "test_strat"

    @pytest.mark.asyncio
    async def test_re_optimize_skipped_when_disabled(
        self,
        config: MonitorConfig,
        store: MagicMock,
    ) -> None:
        executor = AutoActionExecutor(config, store, enabled_actions={})
        action = await executor.execute({
            "type": "SHARPE_DEGRADATION",
            "severity": "WARNING",
            "strategy_id": "test_strat",
        })
        assert len(action) == 0

    # ── Edge cases ──────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_unknown_alert_type_returns_empty(
        self,
        executor: AutoActionExecutor,
    ) -> None:
        """An alert type with no mapped action returns empty list."""
        action = await executor.execute({
            "type": "UNKNOWN_ALERT",
            "severity": "CRITICAL",
            "strategy_id": "test_strat",
        })
        assert action == []

    @pytest.mark.asyncio
    async def test_action_persisted_to_store(
        self,
        config: MonitorConfig,
        store: MagicMock,
    ) -> None:
        """Each executed action is persisted via store.append_alert()."""
        executor = AutoActionExecutor(config, store)
        await executor.execute({
            "type": "DRAWDOWN_BREACH",
            "severity": "CRITICAL",
            "strategy_id": "test_strat",
        })

        store.append_alert.assert_called_once()
        call_args = store.append_alert.call_args[0][0]
        assert call_args["type"] == "STRATEGY_STOPPED"
        assert call_args["strategy_id"] == "test_strat"


# ── AutonomousMonitorDaemon ──────────────────────────────────────────────────


class TestAutonomousMonitorDaemon:
    """AutonomousMonitorDaemon lifecycle, stall/reconnect, compute cycle, heartbeat."""

    # ── Stream helper ───────────────────────────────────────────────────────

    @staticmethod
    async def _stream_points(
        points: list[EquityPoint] | None = None,
        delay: float = 0.01,
        raise_on_iteration: int | None = None,
    ) -> AsyncGenerator[EquityPoint, None]:
        """Yield equity points, optionally raising on the Nth iteration."""
        if points is None:
            return
        for i, pt in enumerate(points):
            if raise_on_iteration is not None and i >= raise_on_iteration:
                msg = "simulated stream error"
                raise ConnectionError(msg)
            yield pt
            await asyncio.sleep(delay)

    # ── Fixtures ────────────────────────────────────────────────────────────

    @pytest.fixture
    def config(self) -> MonitorConfig:
        return MonitorConfig(
            strategy_id="test_daemon",
            compute_interval=999,        # very long — won't fire by accident
            heartbeat_interval=999,       # very long
            stream_timeout=999,           # very long
            knowledge_root="/tmp",
        )

    @pytest.fixture
    def points(self) -> list[EquityPoint]:
        now = datetime.now(timezone.utc)
        return [
            EquityPoint(timestamp=now, equity=100.0),
            EquityPoint(timestamp=now, equity=101.0),
            EquityPoint(timestamp=now, equity=102.0),
            EquityPoint(timestamp=now, equity=99.0),
            EquityPoint(timestamp=now, equity=100.5),
        ]

    @pytest.fixture
    def mock_agent(self) -> MagicMock:
        agent = MagicMock(spec=MonitoringAgent)
        agent.compute_rolling_metrics.return_value = {
            "sharpe": {"values": [1.5], "metric_name": "sharpe"},
            "drawdown": {"values": [0.05], "metric_name": "drawdown"},
            "volatility": {"values": [0.15], "metric_name": "volatility"},
        }
        agent.detect_regime_change.return_value = []
        agent.check_alerts.return_value = []
        return agent

    @pytest.fixture
    def mock_store(self) -> MagicMock:
        store = MagicMock(spec=TimeSeriesStore)
        return store

    @pytest.fixture
    def mock_dispatcher(self) -> MagicMock:
        return MagicMock(spec=NotifierDispatcher)

    @pytest.fixture
    def mock_executor(self) -> MagicMock:
        executor = MagicMock(spec=AutoActionExecutor)
        executor.execute = AsyncMock(return_value=[])
        return executor

    # ── Lifecycle (2.1) ─────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_start_changes_state_to_running(
        self,
        config: MonitorConfig,
        mock_agent: MagicMock,
        mock_store: MagicMock,
        mock_dispatcher: MagicMock,
        mock_executor: MagicMock,
    ) -> None:
        """Calling start() sets state to running and creates a background task."""
        daemon = AutonomousMonitorDaemon(
            config,
            agent=mock_agent,
            store=mock_store,
            dispatcher=mock_dispatcher,
            executor=mock_executor,
        )

        await daemon.start()
        try:
            assert daemon.status()["state"] == "running"
            assert daemon._task is not None
        finally:
            await daemon.stop()

    @pytest.mark.asyncio
    async def test_stop_changes_state_to_stopped(
        self,
        config: MonitorConfig,
        mock_agent: MagicMock,
        mock_store: MagicMock,
        mock_dispatcher: MagicMock,
        mock_executor: MagicMock,
    ) -> None:
        """Calling stop() transitions to stopped state."""
        daemon = AutonomousMonitorDaemon(
            config,
            agent=mock_agent,
            store=mock_store,
            dispatcher=mock_dispatcher,
            executor=mock_executor,
        )

        await daemon.start()
        await daemon.stop()
        assert daemon.status()["state"] == "stopped"

    @pytest.mark.asyncio
    async def test_status_returns_expected_fields(
        self,
        config: MonitorConfig,
        mock_agent: MagicMock,
        mock_store: MagicMock,
        mock_dispatcher: MagicMock,
        mock_executor: MagicMock,
    ) -> None:
        """status() returns dict with state, uptime_seconds, last_heartbeat, metrics_count."""
        daemon = AutonomousMonitorDaemon(
            config,
            agent=mock_agent,
            store=mock_store,
            dispatcher=mock_dispatcher,
            executor=mock_executor,
        )

        await daemon.start()
        try:
            st = daemon.status()
            assert "state" in st
            assert "uptime_seconds" in st
            assert "last_heartbeat" in st
            assert "metrics_count" in st
            assert st["state"] == "running"
        finally:
            await daemon.stop()

    @pytest.mark.asyncio
    async def test_start_idempotent(
        self,
        config: MonitorConfig,
        mock_agent: MagicMock,
        mock_store: MagicMock,
        mock_dispatcher: MagicMock,
        mock_executor: MagicMock,
    ) -> None:
        """Starting an already-running daemon is a no-op."""
        daemon = AutonomousMonitorDaemon(
            config,
            agent=mock_agent,
            store=mock_store,
            dispatcher=mock_dispatcher,
            executor=mock_executor,
        )

        await daemon.start()
        task_id_first = id(daemon._task)
        await daemon.start()  # second start — should be no-op
        task_id_second = id(daemon._task)

        try:
            assert daemon.status()["state"] == "running"
            assert task_id_first == task_id_second
        finally:
            await daemon.stop()

    @pytest.mark.asyncio
    async def test_stop_safe_when_not_running(
        self,
        config: MonitorConfig,
    ) -> None:
        """Stopping a daemon that was never started does not crash."""
        daemon = AutonomousMonitorDaemon(config)
        await daemon.stop()  # should not raise
        assert daemon.status()["state"] == "stopped"

    # ── Compute cycle (2.5) ─────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_compute_cycle_invokes_agent_methods(
        self,
        mock_agent: MagicMock,
        mock_store: MagicMock,
        mock_dispatcher: MagicMock,
        mock_executor: MagicMock,
        points: list[EquityPoint],
    ) -> None:
        """After accumulating points, compute cycle calls MonitoringAgent methods."""
        config = MonitorConfig(
            strategy_id="test_daemon",
            compute_interval=0.05,    # fire quickly
            heartbeat_interval=999,
            stream_timeout=999,
        )

        daemon = AutonomousMonitorDaemon(
            config,
            agent=mock_agent,
            store=mock_store,
            dispatcher=mock_dispatcher,
            executor=mock_executor,
        )

        # Inject mock stream
        stream = self._stream_points(points, delay=0.02)
        daemon._get_stream = lambda: stream  # type: ignore[method-assign]

        await daemon.start()
        await asyncio.sleep(0.25)  # enough for compute cycle to fire
        await daemon.stop()

        assert mock_agent.compute_rolling_metrics.called
        assert mock_agent.detect_regime_change.called
        assert mock_agent.check_alerts.called

    @pytest.mark.asyncio
    async def test_compute_cycle_dispatches_alerts(
        self,
        mock_agent: MagicMock,
        mock_store: MagicMock,
        mock_dispatcher: MagicMock,
        mock_executor: MagicMock,
        points: list[EquityPoint],
    ) -> None:
        """Alerts from MonitoringAgent are dispatched through NotifierDispatcher."""
        # Make check_alerts return an alert
        mock_agent.check_alerts.return_value = [
            {
                "type": "DRAWDOWN_BREACH",
                "severity": "CRITICAL",
                "strategy_id": "test_daemon",
                "message": "DD breach",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "details": {},
            }
        ]

        config = MonitorConfig(
            strategy_id="test_daemon",
            compute_interval=0.05,
            heartbeat_interval=999,
            stream_timeout=999,
        )

        daemon = AutonomousMonitorDaemon(
            config,
            agent=mock_agent,
            store=mock_store,
            dispatcher=mock_dispatcher,
            executor=mock_executor,
        )

        stream = self._stream_points(points, delay=0.02)
        daemon._get_stream = lambda: stream  # type: ignore[method-assign]

        await daemon.start()
        await asyncio.sleep(0.25)
        await daemon.stop()

        # Dispatcher should have been called with the breach alert
        assert mock_dispatcher.dispatch.called

    # ── Heartbeat (2.6) ─────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_heartbeat_emitted_at_interval(
        self,
        mock_agent: MagicMock,
        mock_store: MagicMock,
        mock_dispatcher: MagicMock,
        mock_executor: MagicMock,
    ) -> None:
        """Heartbeat is persisted at the configured interval."""
        config = MonitorConfig(
            strategy_id="hb_test",
            compute_interval=999,
            heartbeat_interval=0.05,   # fire every 50ms
            stream_timeout=999,
        )

        daemon = AutonomousMonitorDaemon(
            config,
            agent=mock_agent,
            store=mock_store,
            dispatcher=mock_dispatcher,
            executor=mock_executor,
        )

        points = [
            EquityPoint(timestamp=datetime.now(timezone.utc), equity=100.0),
            EquityPoint(timestamp=datetime.now(timezone.utc), equity=101.0),
        ]
        stream = self._stream_points(points, delay=0.03)
        daemon._get_stream = lambda: stream  # type: ignore[method-assign]

        await daemon.start()
        await asyncio.sleep(0.2)
        await daemon.stop()

        assert mock_store.append_heartbeat.called

    # ── Health check (2.6) ──────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_health_check_does_not_crash(
        self,
        mock_agent: MagicMock,
        mock_store: MagicMock,
        mock_dispatcher: MagicMock,
        mock_executor: MagicMock,
    ) -> None:
        """Health check runs between stream iterations without crashing."""
        config = MonitorConfig(
            strategy_id="health_test",
            compute_interval=999,
            heartbeat_interval=999,
            stream_timeout=999,
        )

        daemon = AutonomousMonitorDaemon(
            config,
            agent=mock_agent,
            store=mock_store,
            dispatcher=mock_dispatcher,
            executor=mock_executor,
        )

        # Empty stream — loop will check health between iterations
        async def empty_stream():
            return
            yield  # noqa: PIE781

        daemon._get_stream = lambda: empty_stream()  # type: ignore[method-assign]

        await daemon.start()
        await asyncio.sleep(0.2)
        await daemon.stop()

        # Must not crash — daemon should be stopped cleanly
        assert daemon.status()["state"] == "stopped"

    # ── Stall / reconnect (2.2) ─────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_max_retries_enters_error_state(
        self,
        config: MonitorConfig,
        mock_agent: MagicMock,
        mock_store: MagicMock,
        mock_dispatcher: MagicMock,
        mock_executor: MagicMock,
    ) -> None:
        """After max_retries connection failures, daemon enters error state."""
        config = MonitorConfig(
            strategy_id="err_test",
            compute_interval=999,
            heartbeat_interval=999,
            stream_timeout=999,
            max_retries=2,           # low for fast test
        )

        daemon = AutonomousMonitorDaemon(
            config,
            agent=mock_agent,
            store=mock_store,
            dispatcher=mock_dispatcher,
            executor=mock_executor,
        )

        # Stream that raises ConnectionError immediately
        async def failing_stream():
            raise ConnectionError("stream failed")
            yield  # pragma: no cover  # noqa: PIE781

        daemon._get_stream = lambda: failing_stream()  # type: ignore[method-assign]
        daemon._reconnect_base = 0.01  # fast backoff for test

        await daemon.start()
        await asyncio.sleep(0.8)  # enough for retries to exhaust (3 * 0.1 sleep + backoff)

        # Assert error state BEFORE stopping (stop resets to "stopped")
        assert daemon.status()["state"] == "error"
        # STREAM_LOST alert should have been dispatched
        assert mock_dispatcher.dispatch.called

        await daemon.stop()


# ── E2E: Full daemon with SQLite persistence (4.3) ──────────────────────────


class TestE2EDaemon:
    """End-to-end test: mock stream → metrics → alerts → SQLite persistence."""

    @pytest.mark.asyncio
    async def test_e2e_full_flow(self) -> None:
        """Mock 3 equity points → compute cycle → alerts dispatched → persisted."""
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name

        try:
            store = TimeSeriesStore(db_path)
            config = MonitorConfig(
                strategy_id="e2e_strat",
                compute_interval=0.05,
                heartbeat_interval=999,
                stream_timeout=999,
            )

            # Mock agent to produce deterministic metrics + alerts
            mock_agent = MagicMock(spec=MonitoringAgent)
            mock_agent.compute_rolling_metrics.return_value = {
                "sharpe": {"values": [1.5], "metric_name": "sharpe"},
                "drawdown": {"values": [0.12], "metric_name": "drawdown"},
                "volatility": {"values": [0.18], "metric_name": "volatility"},
            }
            mock_agent.detect_regime_change.return_value = []
            mock_agent.check_alerts.return_value = [
                {
                    "type": "DRAWDOWN_BREACH",
                    "severity": "CRITICAL",
                    "strategy_id": "e2e_strat",
                    "message": "DD exceeded threshold",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "details": {"current_dd": "15%", "threshold": "10%"},
                },
            ]

            daemon = AutonomousMonitorDaemon(
                config,
                store=store,
                agent=mock_agent,
            )

            # Provide equity points
            now = datetime.now(timezone.utc)
            points = [
                EquityPoint(timestamp=now, equity=100.0),
                EquityPoint(timestamp=now, equity=101.0),
                EquityPoint(timestamp=now, equity=99.0),
            ]

            stream = _stream_points(points, delay=0.05)
            daemon._get_stream = lambda: stream  # type: ignore[method-assign]

            await daemon.start()
            await asyncio.sleep(0.4)
            await daemon.stop()

            # Assert alerts were persisted to SQLite
            rows = store._conn.execute(
                "SELECT type, severity FROM alerts WHERE strategy_id = ?",
                ("e2e_strat",),
            ).fetchall()
            assert len(rows) > 0, "Expected at least one alert persisted"

            # Assert metrics were persisted
            metric_rows = store._conn.execute(
                "SELECT DISTINCT metric_name FROM metrics WHERE strategy_id = ?",
                ("e2e_strat",),
            ).fetchall()
            assert len(metric_rows) > 0, "Expected metrics persisted"

        finally:
            os.unlink(db_path)


# ── Module-level stream helper for E2E tests ────────────────────────────────


async def _stream_points(
    points: list[EquityPoint] | None = None,
    delay: float = 0.01,
    raise_on_iteration: int | None = None,
) -> AsyncGenerator[EquityPoint, None]:
    """Yield equity points with optional delay, optionally raising on Nth iteration."""
    if points is None:
        return
    for i, pt in enumerate(points):
        if raise_on_iteration is not None and i >= raise_on_iteration:
            msg = "simulated stream error"
            raise ConnectionError(msg)
        yield pt
        await asyncio.sleep(delay)
