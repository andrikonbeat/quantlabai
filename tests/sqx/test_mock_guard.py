"""RED tests for the mock-mode guard (MOK-01/02, threat matrix).

The guard must make silent simulation impossible:
- mock mode -> warning on logger AND stderr (MOK-02)
- QUANTLAB_ENV=production + mock without SQX_FORCE_MOCK=1 -> raise (MOK-01)
- production + explicit SQX_FORCE_MOCK=1 -> allowed (warns)
"""

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, patch

import pytest

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
