"""License manager — checks and activates SQX licenses.

Queries the sqcli binary for license state (``-license action=info``)
and supports activation via code (``-license action=update code=...``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from quantlab.cli.runner import CliResult, Executor


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

        Executes ``sqcli -license action=info`` and parses the output
        to determine the license status.

        Returns:
            A ``LicenseInfo`` with status and detail parsed from the
            sqcli output.
        """
        result = self._executor.execute(["-license", "action=info"])
        return self._parse_info(result.stdout)

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
