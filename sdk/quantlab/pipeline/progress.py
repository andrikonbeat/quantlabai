"""Progress callback protocol for campaign lifecycle notifications."""

from __future__ import annotations

from enum import Enum
from typing import Protocol


class PhaseStatus(str, Enum):
    """Execution status for a single campaign phase.

    Each phase transitions: ``STARTED`` → ``SUCCESS`` | ``ERROR``.
    """

    STARTED = "started"
    SUCCESS = "success"
    ERROR = "error"


class ProgressCallback(Protocol):
    """Callback protocol for campaign progress notifications.

    Implementations receive a phase identifier, a status transition,
    and optional detail text at each phase boundary.

    Usage::

        def on_progress(
            phase: str, status: PhaseStatus, detail: str | None = None
        ) -> None:
            print(f"[{status.value}] {phase}: {detail or ''}")

        runner = CampaignRunner(progress=on_progress, ...)
    """

    def __call__(
        self,
        phase: str,
        status: PhaseStatus,
        detail: str | None = None,
    ) -> None: ...
