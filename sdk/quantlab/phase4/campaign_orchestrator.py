"""Campaign orchestrator — coordinates multi-stage campaign execution.

This module provides the CampaignResult model returned by the campaign
orchestrator after running a complete campaign pipeline. Used by the
reporting module and statistics aggregator for post-campaign analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from quantlab.readers.models import EquityPoint, Trade


@dataclass
class CampaignResult:
    """Result of a complete campaign execution.

    Contains the trades, equity curve, and statistics produced by
    executing a campaign through the SQX pipeline stages.
    """

    campaign_name: str
    trades: list[Trade] = field(default_factory=list)
    equity: list[EquityPoint] = field(default_factory=list)
    statistics: dict[str, Any] = field(default_factory=dict)
    campaign_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    cfx_path: Optional[Path] = None
    artifact_paths: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.campaign_id is None:
            self.campaign_id = self.campaign_name
