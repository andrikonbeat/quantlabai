"""RED tests for the license guard (LIC, LIC-02, threat matrix).

- SQX_LICENSE env short-circuits check() without invoking sqcli (LIC-02)
- raw sqcli -license action=info output is logged (LIC-02)
- production + non-LICENSED -> LicenseError before any dispatch (LIC-01)
- dev + non-LICENSED -> warning only, run proceeds (LIC-01)
- mock dispatch skips the license check entirely (LIC-01)
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, patch

import pytest

from quantlab.cli.runner import CliResult, MockExecutor
from quantlab.pipeline.license import (
    LicenseInfo,
    LicenseManager,
    LicenseStatus,
    license_preflight,
)
from quantlab.tools.exceptions import LicenseError
from quantlab.sqx.cli_wrapper import dispatch_campaign


class TestSQXLicenseOverride:
    """SQX_LICENSE env short-circuits check() (LIC-02)."""

    def test_override_reports_status_without_executor(self, monkeypatch) -> None:
        monkeypatch.setenv("SQX_LICENSE", "licensed")
        manager = LicenseManager(MockExecutor())
        info = manager.check()
        assert info.status == LicenseStatus.LICENSED

    def test_override_lowercase_insensitive(self, monkeypatch) -> None:
        monkeypatch.setenv("SQX_LICENSE", "TRIAL")
        manager = LicenseManager(MockExecutor())
        info = manager.check()
        assert info.status == LicenseStatus.TRIAL


class TestRawOutputLogged:
    """Raw sqcli -license action=info output is logged (LIC-02)."""

    def test_raw_output_logged(self, caplog) -> None:
        raw = "SQX license: licensed until 2030-01-01"
        executor = MockExecutor(default_result=CliResult(
            stdout=raw, stderr="", exit_code=0, duration_seconds=0.001,
        ))
        manager = LicenseManager(executor)
        with caplog.at_level(logging.INFO, logger="quantlab.pipeline.license"):
            info = manager.check()
        assert info.status == LicenseStatus.LICENSED
        assert raw in caplog.text


class TestLicensePreflight:
    """Pre-flight behavior per environment (LIC-01)."""

    def test_production_unlicensed_raises(self, monkeypatch) -> None:
        monkeypatch.setenv("QUANTLAB_ENV", "production")
        monkeypatch.delenv("SQX_LICENSE", raising=False)
        executor = MockExecutor(default_result=CliResult(
            stdout="no license found", stderr="", exit_code=1,
            duration_seconds=0.001,
        ))
        with pytest.raises(LicenseError):
            license_preflight(executor)

    def test_dev_unlicensed_warns(self, monkeypatch, caplog) -> None:
        monkeypatch.delenv("QUANTLAB_ENV", raising=False)
        monkeypatch.delenv("SQX_LICENSE", raising=False)
        executor = MockExecutor(default_result=CliResult(
            stdout="no license found", stderr="", exit_code=1,
            duration_seconds=0.001,
        ))
        with caplog.at_level(logging.WARNING, logger="quantlab.pipeline.license"):
            info = license_preflight(executor)
        assert info.status == LicenseStatus.UNLICENSED
        assert any("license" in r.message.lower() for r in caplog.records)

    def test_production_licensed_proceeds(self, monkeypatch) -> None:
        monkeypatch.setenv("QUANTLAB_ENV", "production")
        monkeypatch.delenv("SQX_LICENSE", raising=False)
        executor = MockExecutor(default_result=CliResult(
            stdout="licensed", stderr="", exit_code=0, duration_seconds=0.001,
        ))
        info = license_preflight(executor)
        assert info.status == LicenseStatus.LICENSED


class TestMockSkipsLicense:
    """Mock dispatch must not invoke the license check (LIC-01)."""

    @pytest.mark.asyncio
    async def test_mock_dispatch_skips_license(self, monkeypatch) -> None:
        monkeypatch.delenv("QUANTLAB_ENV", raising=False)
        monkeypatch.setenv("SQX_FORCE_MOCK", "1")
        fake_mock = AsyncMock(return_value={"status": "completed", "export_paths": []})
        with patch("quantlab.sqx.cli_wrapper._dispatch_mock", fake_mock), \
             patch("quantlab.sqx.cli_wrapper._find_sqcli", return_value=None), \
             patch("quantlab.pipeline.license.license_preflight") as guard:
            await dispatch_campaign(
                cfx_bytes=b"<cfx/>",
                campaign_id="mock-license",
                config=None,
                sqx_install_path="/tmp/fake_sqx",
            )
        guard.assert_not_called()
