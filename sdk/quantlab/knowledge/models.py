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
    total_return: Optional[float] = None


@dataclass
class CampaignSummary:
    """Summary of a campaign for query results."""
    campaign_id: str
    name: str
    metrics: Optional[CampaignMetrics] = None
    tags: list[str] = field(default_factory=list)
    created: Optional[datetime] = None
    path: Optional[Path] = None
    market: Optional[str] = None
    timeframe: Optional[str] = None
    status: Optional[str] = None


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
    docs: list[dict[str, object]] | None = None


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


@dataclass
class PhaseEnvelope:
    """Structured envelope for a single pipeline phase execution."""

    campaign_id: str
    phase: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration: Optional[float] = None
    artifacts: list[str] = field(default_factory=list)
    error: Optional[str] = None
    next_gate: Optional[str] = None
    gate_decision: Optional[str] = None


@dataclass
class ParameterMatrixEntry:
    """One SQX parameter justification entry."""

    tab: str
    parameter: str
    value: Any
    rationale: str
    source: str = "default"
    confidence: float = 0.5
    hypothesis_ref: Optional[str] = None


@dataclass
class FeedbackRecord:
    """Guardian feedback record for live degradation or parameter drift."""

    campaign_id: str
    strategy_id: Optional[str] = None
    event_type: str = "DEGRADING"
    severity: str = "WARNING"
    metric_delta: Optional[dict[str, float]] = None
    parameter_deltas: list[dict[str, Any]] = field(default_factory=list)
    detected_at: Optional[str] = None
    recommended_action: Optional[str] = None


@dataclass
class MaintenancePlan:
    """Campaign maintenance plan and replacement runbook."""

    campaign_id: str
    review_cycle_days: int = 30
    replacement_candidates: list[str] = field(default_factory=list)
    live_strategy_ids: list[str] = field(default_factory=list)
    disconnected_strategy_ids: list[str] = field(default_factory=list)
    notes: Optional[str] = None
    updated_at: Optional[str] = None