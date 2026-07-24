"""Shared campaign data types — enums and dataclasses.

Extracted from ``campaign_orchestrator`` to break the circular import
with ``checkpoint``.  Re-exported by ``campaign_orchestrator`` for
backward compatibility.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CampaignPhase(str, Enum):
    """Pipeline execution phases."""

    VALIDATE = "validate"
    TRANSLATE = "translate"
    DAEMON_START = "daemon_start"
    LOAD_CONFIG = "load_config"
    RUN = "run"
    POLL = "poll"
    EXPORT = "export"
    READ = "read"
    COMPUTE = "compute"
    STORE = "store"
    COMPLETE = "complete"


class PhaseStatus(str, Enum):
    """Phase execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PhaseResult:
    """Result of a single pipeline phase."""

    phase: CampaignPhase
    status: PhaseStatus
    detail: str = ""
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    error: Optional[str] = None

    @property
    def duration(self) -> float:
        end = self.completed_at or time.time()
        return end - self.started_at
