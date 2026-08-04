"""RED tests for the mock-mode guard (MOK-01/02, threat matrix).

The guard must make silent simulation impossible:
- mock mode -> warning on logger AND stderr (MOK-02)
- QUANTLAB_ENV=production + mock without SQX_FORCE_MOCK=1 -> raise (MOK-01)
- production + explicit SQX_FORCE_MOCK=1 -> allowed (warns)
"""

from __future__ import annotations

import asyncio
import os
import urllib.parse
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from quantlab.dsl.models import LLMConfig
from quantlab.gates.notifiers import ConsoleNotifier, WebhookNotifier
from quantlab.sqx.cli_wrapper import dispatch_campaign, mock_mode_guard


class TestGuardNoOp:
    """No mock mode -> no warning, no raise."""

    def test_real_mode_is_noop(self, monkeypatch, capsys) -> None:
        monkeypatch.delenv("SQX_FORCE_MOCK", raising=False)
        monkeypatch.delenv("QUANTLAB_ENV", raising=False)
        mock_mode_guard(force_mock=False)
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_real_mode_in_production_is_noop(self, monkeypatch, capsys) -> None:
        monkeypatch.delenv("SQX_FORCE_MOCK", raising=False)
        monkeypatch.setenv("QUANTLAB_ENV", "production")
        mock_mode_guard(force_mock=False)
        captured = capsys.readouterr()
        assert captured.err == ""


class TestGuardWarnsOnMock:
    """Mock mode -> warning surfaces on stderr (MOK-02)."""

    def test_force_mock_warns(self, monkeypatch, capsys) -> None:
        monkeypatch.delenv("SQX_FORCE_MOCK", raising=False)
        mock_mode_guard(force_mock=True)
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "Mock" in captured.err

    def test_sqx_force_mock_env_warns(self, monkeypatch, capsys) -> None:
        monkeypatch.setenv("SQX_FORCE_MOCK", "1")
        mock_mode_guard(force_mock=False)
        captured = capsys.readouterr()
        assert "WARNING" in captured.err

    def test_explicit_override_allowed_in_production(self, monkeypatch, capsys) -> None:
        """Production + SQX_FORCE_MOCK=1 must NOT raise (MOK-01 exception)."""
        monkeypatch.setenv("QUANTLAB_ENV", "production")
        monkeypatch.setenv("SQX_FORCE_MOCK", "1")
        mock_mode_guard(force_mock=False)
        captured = capsys.readouterr()
        assert "WARNING" in captured.err


class TestGuardProduction:
    """QUANTLAB_ENV=production + mock without override -> raise (MOK-01)."""

    def test_production_force_mock_without_override_raises(
        self, monkeypatch
    ) -> None:
        monkeypatch.setenv("QUANTLAB_ENV", "production")
        monkeypatch.delenv("SQX_FORCE_MOCK", raising=False)
        with pytest.raises(RuntimeError, match="production"):
            mock_mode_guard(force_mock=True)


class TestGuardWiring:
    """dispatch_campaign() invokes the guard before dispatching."""

    @pytest.mark.asyncio
    async def test_dispatch_mock_path_warns(
        self, monkeypatch, capsys
    ) -> None:
        monkeypatch.delenv("QUANTLAB_ENV", raising=False)
        monkeypatch.setenv("SQX_FORCE_MOCK", "1")

        fake_mock = AsyncMock(return_value={"status": "completed", "export_paths": []})
        with patch("quantlab.sqx.cli_wrapper._dispatch_mock", fake_mock), \
             patch("quantlab.sqx.cli_wrapper._find_sqcli", return_value=None):
            await dispatch_campaign(
                cfx_bytes=b"<cfx/>",
                campaign_id="guard-test",
                config=None,
                sqx_install_path="/tmp/fake_sqx",
            )

        captured = capsys.readouterr()
        assert "WARNING" in captured.err

    @pytest.mark.asyncio
    async def test_dispatch_production_raises(self, monkeypatch) -> None:
        monkeypatch.setenv("QUANTLAB_ENV", "production")
        monkeypatch.delenv("SQX_FORCE_MOCK", raising=False)

        fake_mock = AsyncMock(return_value={"status": "completed", "export_paths": []})
        with patch("quantlab.sqx.cli_wrapper._dispatch_mock", fake_mock), \
             patch("quantlab.sqx.cli_wrapper._find_sqcli", return_value=None):
            with pytest.raises(RuntimeError, match="production"):
                # force_mock=True simulates a code-level dry_run flag — in
                # production this must raise without an explicit override.
                await dispatch_campaign(
                    cfx_bytes=b"<cfx/>",
                    campaign_id="guard-test-prod",
                    config=None,
                    sqx_install_path="/tmp/fake_sqx",
                    force_mock=True,
                )


# ── WU-8: Orchestrated dispatch wiring (REQ-15/REQ-20, boundary 3, REQ-04) ──


class _FakeMonitor:
    """Records constructor kwargs and add_notifier calls for wiring tests."""

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.add_notifier_calls: list[object] = []
        self._events: list[object] = []

    def add_notifier(self, notifier: object) -> None:
        self.add_notifier_calls.append(notifier)

    @property
    def current_snapshot(self) -> None:
        return None

    async def run(self) -> list[object]:
        return []

    async def cancel(self) -> None:
        pass

    async def final_check(self) -> None:
        pass


def _fake_factory(store: _FakeMonitor):
    """Return a CampaignMonitor/LLMGenerationMonitor stand-in that records
    constructor kwargs onto ``store.kwargs``."""

    def _factory(*args: object, **kwargs: object) -> _FakeMonitor:
        store.kwargs = kwargs
        return store

    return _factory


def _patch_dispatch_internals(monkeypatch: pytest.MonkeyPatch) -> None:
    """Route orchestrated dispatch through the mock path, patching the
    real sqcli/monitor/mock-server machinery so the wiring is observable."""

    def fake_send(base_url: str, command: str) -> str:
        # A status response of "stopped" ends the poll loop on the first tick.
        if "action=status" in command:
            return "Project execution stopped"
        return "ok"

    monkeypatch.setattr("quantlab.sqx.cli_wrapper._ensure_mock_server",
                        AsyncMock(return_value="http://127.0.0.1:5050"))
    monkeypatch.setattr("quantlab.sqx.cli_wrapper._send_http",
                        AsyncMock(side_effect=fake_send))
    monkeypatch.setattr("quantlab.sqx.cli_wrapper.create_project", Mock())
    monkeypatch.setattr("quantlab.sqx.cli_wrapper._collect_exports",
                        lambda sqx, cid: [])


class TestOrchestratedDispatchWiring:
    """T8.4: orchestrated dispatch registers gate callbacks + webhook/console
    notifiers on the spawned monitors; non-orchestrated stays unchanged."""

    @pytest.fixture(autouse=True)
    def _clean_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("QUANTLAB_WEBHOOK_URL", raising=False)
        monkeypatch.delenv("QUANTLAB_ENV", raising=False)
        monkeypatch.setenv("SQX_FORCE_MOCK", "1")

    @staticmethod
    def _notifier_types(monitor: _FakeMonitor) -> list[type]:
        return [type(n) for n in monitor.add_notifier_calls]

    @pytest.mark.asyncio
    async def test_orchestrated_registers_notifiers_on_monitors(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """REQ-15/REQ-20: webhook + console notifiers are registered on both
        monitors; on_watcher_event/on_llm_verdict stay the primary channel."""
        fake_monitor = _FakeMonitor()
        fake_llm = _FakeMonitor()
        monkeypatch.setattr("quantlab.sqx.cli_wrapper.CampaignMonitor",
                            _fake_factory(fake_monitor))
        monkeypatch.setattr("quantlab.sqx.cli_wrapper.LLMGenerationMonitor",
                            _fake_factory(fake_llm))
        _patch_dispatch_internals(monkeypatch)

        agent_cb = Mock()
        llm_cb = Mock()
        await dispatch_campaign(
            cfx_bytes=b"<cfx/>",
            campaign_id="orch-wire",
            config={},
            force_mock=True,
            orchestrated=True,
            webhook_url="http://hook.example/x",
            on_watcher_event=agent_cb,
            llm_config=LLMConfig(),
            on_llm_verdict=llm_cb,
            poll_interval=0.01,
            timeout=5.0,
        )

        # Primary OpenCode agent channel preserved on both monitors.
        assert fake_monitor.kwargs["on_watcher_event"] is agent_cb
        assert fake_llm.kwargs["on_verdict"] is llm_cb
        # Console + webhook notifiers registered on both monitors.
        cm_types = self._notifier_types(fake_monitor)
        assert ConsoleNotifier in cm_types
        webhooks = [n for n in fake_monitor.add_notifier_calls
                    if isinstance(n, WebhookNotifier)]
        assert len(webhooks) == 1
        assert webhooks[0].url == "http://hook.example/x"
        assert ConsoleNotifier in self._notifier_types(fake_llm)
        assert any(
            isinstance(n, WebhookNotifier)
            for n in fake_llm.add_notifier_calls
        )

    @pytest.mark.asyncio
    async def test_orchestrated_registers_gate_writer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """REQ-20: orchestrated dispatch with gate_event_dir registers a gate
        writer on the campaign monitor (decision-file channel, not CLI)."""
        fake_monitor = _FakeMonitor()
        fake_llm = _FakeMonitor()
        monkeypatch.setattr("quantlab.sqx.cli_wrapper.CampaignMonitor",
                            _fake_factory(fake_monitor))
        monkeypatch.setattr("quantlab.sqx.cli_wrapper.LLMGenerationMonitor",
                            _fake_factory(fake_llm))
        _patch_dispatch_internals(monkeypatch)

        await dispatch_campaign(
            cfx_bytes=b"<cfx/>",
            campaign_id="orch-gate",
            config={},
            force_mock=True,
            orchestrated=True,
            gate_event_dir="/tmp/sqx-gates-test",
            on_watcher_event=None,
            poll_interval=0.01,
            timeout=5.0,
        )

        assert fake_monitor.kwargs["gate_writer"] is not None
        assert callable(fake_monitor.kwargs["gate_writer"])

    @pytest.mark.asyncio
    async def test_non_orchestrated_registers_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """REQ-20 scenario: non-orchestrated dispatch behavior unchanged —
        zero notifiers, zero gate writers."""
        fake_monitor = _FakeMonitor()
        monkeypatch.setattr("quantlab.sqx.cli_wrapper.CampaignMonitor",
                            _fake_factory(fake_monitor))
        monkeypatch.setattr("quantlab.sqx.cli_wrapper.LLMGenerationMonitor",
                            _fake_factory(_FakeMonitor()))
        _patch_dispatch_internals(monkeypatch)

        await dispatch_campaign(
            cfx_bytes=b"<cfx/>",
            campaign_id="legacy-wire",
            config={},
            force_mock=True,
            poll_interval=0.01,
            timeout=5.0,
        )

        assert fake_monitor.add_notifier_calls == []
        assert fake_monitor.kwargs.get("gate_writer") is None

    @pytest.mark.asyncio
    async def test_orchestrated_blocks_validation_fixture_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """REQ-04: orchestrated dispatch reports post-dispatch blocks
        validation; fixture fallback drives the CFX input. No exports →
        every intended block reported missing."""
        from quantlab.sqx.project_builder import BuildConfig

        fixture = Path(__file__).resolve().parents[2] / "tests" / "cfx" \
            / "fixtures" / "Builder.cfx"
        assert fixture.is_file()
        fake_monitor = _FakeMonitor()
        monkeypatch.setattr("quantlab.sqx.cli_wrapper.CampaignMonitor",
                            _fake_factory(fake_monitor))
        monkeypatch.setattr("quantlab.sqx.cli_wrapper.LLMGenerationMonitor",
                            _fake_factory(_FakeMonitor()))
        _patch_dispatch_internals(monkeypatch)

        result = await dispatch_campaign(
            cfx_bytes=fixture.read_bytes(),
            campaign_id="orch-blocks",
            config={},
            force_mock=True,
            orchestrated=True,
            build_config=BuildConfig(enabled_blocks=["Trend", "Momentum"]),
            poll_interval=0.01,
            timeout=5.0,
        )

        report = result.get("blocks_report")
        assert report is not None
        assert report["ok"] is False
        assert set(report["missing"]) == {"Trend", "Momentum"}


class TestHttpEncodingRegression:
    """Boundary 3: HTTP command encoding keeps '=' safe via urllib.parse.quote."""

    def test_command_quote_preserves_equals(self) -> None:
        encoded = urllib.parse.quote(
            "-project action=stop name=campaign1", safe="="
        )
        assert encoded == "-project%20action=stop%20name=campaign1"
        assert "%3D" not in encoded
