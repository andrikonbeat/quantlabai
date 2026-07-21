"""Knowledge Lake query and index models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class CampaignMetrics:
    """Key metrics for a campaign."""
    sharpe_ratio: Optional[float] = None
    profit_factor: Optional[float] = None
    win_rate: Optional[float] = None
    max_drawdown: Optional[float] = None
    total_trades: Optional[int] = None
    net_profit: Optional[float] = None


@dataclass
class CampaignSummary:
    """Summary of a campaign for query results."""
    campaign_id: str
    name: str
    metrics: Optional[CampaignMetrics] = None
    tags: list[str] = field(default_factory=list)
    created: Optional[datetime] = None
    path: Optional[Path] = None


@dataclass
class QueryFilter:
    """Filters for campaign queries."""
    sharpe_min: Optional[float] = None
    sharpe_max: Optional[float] = None
    profit_factor_min: Optional[float] = None
    win_rate_min: Optional[float] = None
    max_drawdown_max: Optional[float] = None
    tags: list[str] = field(default_factory=list)
    date_start: Optional[datetime] = None
    date_end: Optional[datetime] = None
    text_search: Optional[str] = None
    sort_by: str = "created"
    sort_ascending: bool = False
    limit: Optional[int] = None
    offset: int = 0
    agent_name: Optional[str] = field(default=None)
    campaign_id: Optional[str] = field(default=None)


@dataclass
class QueryResult:
    """Result of a query."""
    campaigns: list[CampaignSummary]
    total_count: int
    query_time_ms: float = 0.0


@dataclass
class TaggedCampaign:
    """Campaign with tags and metadata."""
    campaign_id: str
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentMemoryEntry:
    """Metadata for a single agent memory artifact."""

    agent_name: str
    campaign_id: str
    memory_path: str
    checkpoint_paths: list[str] = field(default_factory=list)
    last_updated: Optional[str] = None
    embedding_ref: Optional[str] = None
    memory_content: Optional[dict] = field(default=None)

    def to_dict(self) -> dict[str, object]:
        d: dict[str, object] = {
            "agent_name": self.agent_name,
            "campaign_id": self.campaign_id,
            "memory_path": self.memory_path,
            "checkpoint_paths": self.checkpoint_paths,
            "last_updated": self.last_updated,
            "embedding_ref": self.embedding_ref,
        }
        if self.memory_content is not None:
            d["memory_content"] = self.memory_content
        return d