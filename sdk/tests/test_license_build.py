"""Build-number parsing tests (REQ-301).

REQ-301: the parser MUST extract the build number from ``sqcli -license``
output ("StrategyQuant X Ultimate Build 144 (Futlab license)") into
``LicenseInfo.build_number``, extracting the point version when present,
while expiry parsing remains unchanged. A missing Build token MUST yield
``build_number = null`` with a warning logged and no exception raised.
"""

import logging

from quantlab.pipeline.license import LicenseInfo, LicenseManager, LicenseStatus

# Trimmed but faithful excerpt of `sqcli -license action=info` real output:
# the decisive license-status line (see tests/sqx/test_license_guard.py).
REAL_BUILD_LINE = (
    "StrategyQuant X Ultimate Build 144 (Futlab license) - valid until "
    "14.08.2026, license FUTLABF255"
)
BUILD_LINE_WITH_POINT = (
    "StrategyQuant X Ultimate Build 144.2953 (Futlab license) - valid until "
    "14.08.2026, license FUTLABF255"
)
NO_BUILD_LINE = "licensed - valid until 14.08.2026, license FUTLABF255"


class TestBuildNumberParsing:
    """REQ-301: Build token on the license line → LicenseInfo.build_number."""

    def test_build_144_parses_build_number_major_only(self) -> None:
        # The real sqcli Build line carries no point version, so the
        # pinned format falls back to the major ("144").
        info = LicenseManager._parse_info(REAL_BUILD_LINE)
        assert info.status == LicenseStatus.LICENSED
        assert info.build_number == "144"

    def test_build_with_point_parses_full_pinned_format(self) -> None:
        info = LicenseManager._parse_info(BUILD_LINE_WITH_POINT)
        assert info.build_number == "144.2953"

    def test_expiry_date_remains_populated(self) -> None:
        # REQ-301: expiry parsing is unchanged when a Build token is present.
        info = LicenseManager._parse_info(REAL_BUILD_LINE)
        assert info.expiry_date == "14.08.2026"

    def test_missing_build_token_yields_null_warns_no_raise(
        self, caplog
    ) -> None:
        # REQ-301: no Build token → build_number null, a warning is logged,
        # and no exception is raised (license status still parses).
        with caplog.at_level(logging.WARNING, logger="quantlab.pipeline.license"):
            info = LicenseManager._parse_info(NO_BUILD_LINE)
        assert info.build_number is None
        assert info.status == LicenseStatus.LICENSED
        assert any("build" in r.message.lower() for r in caplog.records)

    def test_license_info_default_build_number_is_null(self) -> None:
        # The new structured field must default to null (fail-open contract).
        assert LicenseInfo().build_number is None
