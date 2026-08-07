"""Tests for the SQX license parser against the REAL sqcli output (LIC-01/02).

The real sqcli (assets/SQX_144_2953_linux_20260601) prints:

    StrategyQuant X Ultimate Build 144 (Futlab license) - valid until 14.08.2026, license FUTLABF255

The ``licensed`` keyword never appears — validity is signalled by
``valid until <date>``.  These tests lock the parser to that real format
and verify the fail-closed behavior (unknown ⇒ UNLICENSED, never crashes).
"""

from unittest.mock import MagicMock

from quantlab.cli.runner import CliResult
from quantlab.pipeline.license import LicenseInfo, LicenseManager, LicenseStatus

# Trimmed but faithful excerpt of `sqcli -license action=info` real output
# (first lines + the decisive license-status line).
REAL_VALID_LICENSE = """Server started on port 5050
SQX version: 144.2953
Hardware ID: CFEE3E2A95D0
Verifying license ...
Customizations loaded successfully, count=1
High priority: OFF
Using: 3 cores, core usage configuration: '-1'
Preparing thread executors: 3
Data loaded in 12758 ms
Volume profile subscription verified: active=true
Projects loaded in 79827 ms
HTTP API started, you can access it on http://localhost:5050/call?cmd=-h
--------------------------------------------------
Starting StrategyQuant X in command line mode.
Params: -license action=info
StrategyQuant X Ultimate Build 144 (Futlab license) - valid until 14.08.2026, license FUTLABF255
All tasks completed
"""

REAL_EMPTY_OUTPUT = ""
REAL_GARBAGE_OUTPUT = "some unparseable output without license hints"


class TestParseInfoRealOutput:
    """GIVEN the REAL sqcli license output WHEN parsed THEN LICENSED."""

    def test_real_valid_license_maps_to_licensed(self) -> None:
        info = LicenseManager._parse_info(REAL_VALID_LICENSE)
        assert info.status == LicenseStatus.LICENSED
        assert info.expiry_date == "14.08.2026"

    def test_real_valid_license_keeps_full_detail(self) -> None:
        info = LicenseManager._parse_info(REAL_VALID_LICENSE)
        assert info.detail == REAL_VALID_LICENSE

    def test_fail_closed_on_empty_output(self) -> None:
        info = LicenseManager._parse_info(REAL_EMPTY_OUTPUT)
        assert info.status == LicenseStatus.UNLICENSED

    def test_fail_closed_on_garbage_output(self) -> None:
        info = LicenseManager._parse_info(REAL_GARBAGE_OUTPUT)
        assert info.status == LicenseStatus.UNLICENSED

    def test_legacy_licensed_keyword_still_supported(self) -> None:
        info = LicenseManager._parse_info("licensed")
        assert info.status == LicenseStatus.LICENSED

    def test_trial_keyword_maps_to_trial(self) -> None:
        info = LicenseManager._parse_info("Trial license - valid until 01.01.2027")
        assert info.status == LicenseStatus.TRIAL

    def test_expired_keyword_maps_to_expired(self) -> None:
        info = LicenseManager._parse_info("license expired")
        assert info.status == LicenseStatus.EXPIRED


class TestLicenseManagerCheck:
    """GIVEN a LicenseManager wired to a real-output executor."""

    def _manager_with_stdout(self, stdout: str) -> LicenseManager:
        executor = MagicMock()
        executor.execute.return_value = CliResult(
            stdout=stdout,
            stderr="",
            exit_code=0,
            duration_seconds=1.0,
            is_dry_run=False,
            platform="linux",
        )
        return LicenseManager(executor)

    def test_check_real_output_reports_licensed(self, monkeypatch) -> None:
        monkeypatch.delenv("SQX_LICENSE", raising=False)
        manager = self._manager_with_stdout(REAL_VALID_LICENSE)
        info = manager.check()
        assert info.status == LicenseStatus.LICENSED
        assert info.expiry_date == "14.08.2026"

    def test_check_garbage_output_reports_unlicensed_fail_closed(self, monkeypatch) -> None:
        monkeypatch.delenv("SQX_LICENSE", raising=False)
        manager = self._manager_with_stdout(REAL_GARBAGE_OUTPUT)
        info = manager.check()
        assert info.status == LicenseStatus.UNLICENSED

    def test_check_override_short_circuits_sqcli(self, monkeypatch) -> None:
        monkeypatch.setenv("SQX_LICENSE", "licensed")
        executor = MagicMock()
        manager = LicenseManager(executor)
        info = manager.check()
        assert info.status == LicenseStatus.LICENSED
        executor.execute.assert_not_called()
