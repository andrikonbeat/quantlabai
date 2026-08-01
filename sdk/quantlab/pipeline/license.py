"""License manager — checks and activates SQX licenses.

Queries the sqcli binary for license state (``-license action=info``)
and supports activation via code (``-license action=update code=...``).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum

from quantlab.cli.runner import CliResult, Executor
from quantlab.tools.exceptions import LicenseError

logger = logging.getLogger(__name__)

# Env override for CI/dev: short-circuits check() with a fixed status.
SQX_LICENSE_ENV = "SQX_LICENSE"


class LicenseStatus(str, Enum):
    """Possible states of an SQX license."""

    LICENSED = "licensed"
    UNLICENSED = "unlicensed"
    EXPIRED = "expired"
    TRIAL = "trial"


@dataclass
class LicenseInfo:
    """Structured result from a license status check.

    Attributes:
        status: License status (licensed, unlicensed, expired, trial).
        detail: Raw output or human-readable detail from the check.
        expiry_date: Expiry date string, if reported by sqcli.
        trial_days_remaining: Remaining trial days, if applicable.
    """

    status: LicenseStatus = LicenseStatus.UNLICENSED
    detail: str = ""
    expiry_date: str | None = None
    trial_days_remaining: int | None = None


class LicenseManager:
    """Detects and manages the SQX license state.

    Args:
        executor: An ``Executor`` used to run license commands.
    """

    def __init__(self, executor: Executor) -> None:
        self._executor = executor

    def check(self) -> LicenseInfo:
        """Check the current SQX license state.

        Honors the ``SQX_LICENSE`` env override (CI/dev short-circuit,
        LIC-02): when set, its value is reported as the status without
        invoking sqcli. Otherwise executes ``sqcli -license action=info``,
        logs the raw output, and parses the status heuristically.

        Returns:
            A ``LicenseInfo`` with status and detail parsed from the
            sqcli output.
        """
        override = os.environ.get(SQX_LICENSE_ENV)
        if override:
            info = LicenseInfo(
                status=self._parse_status(override),
                detail=f"override (SQX_LICENSE): {override}",
            )
            logger.info("License check short-circuited by SQX_LICENSE override: %s", info.status.value)
            return info

        result = self._executor.execute(["-license", "action=info"])
        # Raw output must always be logged for diagnosis (LIC-02).
        logger.info("raw sqcli -license action=info output:\n%s", result.stdout)
        return self._parse_info(result.stdout)

    @staticmethod
    def _parse_status(value: str) -> LicenseStatus:
        """Map a raw status string onto LicenseStatus, leniently."""
        try:
            return LicenseStatus(value.strip().lower())
        except ValueError:
            return LicenseStatus.UNLICENSED

    @staticmethod
    def _parse_info(stdout: str) -> LicenseInfo:
        """Heuristic parser for ``-license action=info`` output.

        Matches known keywords in a case-insensitive fashion.  This
        parser is intentionally simple — replace it when the exact
        sqcli output format is known.
        """
        lower = stdout.lower()
        if "licensed" in lower:
            return LicenseInfo(status=LicenseStatus.LICENSED, detail=stdout)
        if "trial" in lower:
            return LicenseInfo(status=LicenseStatus.TRIAL, detail=stdout)
        if "expired" in lower:
            return LicenseInfo(status=LicenseStatus.EXPIRED, detail=stdout)
        return LicenseInfo(status=LicenseStatus.UNLICENSED, detail=stdout)

    def activate(self, code: str) -> CliResult:
        """Activate the license with a given activation code.

        Executes ``sqcli -license action=update code=<code>``.

        Args:
            code: The activation code string.

        Returns:
            A ``CliResult`` from the sqcli command execution.
        """
        return self._executor.execute(["-license", "action=update", f"code={code}"])


def license_preflight(executor: Executor, *, env: str | None = None) -> LicenseInfo:
    """Run the license pre-flight guard on a real dispatch (LIC-01).

    Non-LICENSED status logs a warning with the detail and the run
    proceeds, EXCEPT in ``QUANTLAB_ENV=production`` where a
    ``LicenseError`` is raised before any sqcli work beyond the license
    check itself. The mock path skips this entirely (callers only invoke
    it on real dispatch).

    Args:
        executor: Executor used to run the license check command.
        env: Override for the environment; defaults to ``QUANTLAB_ENV``.

    Returns:
        The ``LicenseInfo`` produced by the check.

    Raises:
        LicenseError: When the environment is production and the status
            is not LICENSED.
    """
    info = LicenseManager(executor).check()
    is_production = (env or os.environ.get("QUANTLAB_ENV", "")).lower() == "production"

    if info.status == LicenseStatus.LICENSED:
        logger.info("License pre-flight passed: %s", info.status.value)
        return info

    detail = (info.detail or info.status.value).strip()
    if is_production:
        raise LicenseError(
            f"SQX license check failed in production (status={info.status.value}): {detail}"
        )

    logger.warning(
        "SQX license is %s (non-production, proceeding): %s",
        info.status.value,
        detail,
    )
    return info
