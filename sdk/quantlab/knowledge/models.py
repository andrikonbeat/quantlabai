"""Knowledge Lake query and index models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class CampaignMetrics:
    """Key metrics for a campaign."""
    sharpe_ratio: float | None = None
    profit_factor: float | None = None
    win_rate: float | None = None
    max_drawdown: float | None = None
    total_trades: int | None = None
    net_profit: float | None = None
    total_return: float | None = None


@dataclass
class CampaignSummary:
    """Summary of a campaign for query results."""
    campaign_id: str
    name: str
    metrics: CampaignMetrics | None = None
    tags: list[str] = field(default_factory=list)
    created: datetime | None = None
    path: Path | None = None
    market: str | None = None
    timeframe: str | None = None
    status: str | None = None


@dataclass
class QueryFilter:
    """Filters for campaign queries."""
    sharpe_min: float | None = None
    sharpe_max: float | None = None
    profit_factor_min: float | None = None
    win_rate_min: float | None = None
    max_drawdown_max: float | None = None
    tags: list[str] = field(default_factory=list)
    date_start: datetime | None = None
    date_end: datetime | None = None
    text_search: str | None = None
    sort_by: str = "created"
    sort_ascending: bool = False
    limit: int | None = None
    offset: int = 0
    agent_name: str | None = field(default=None)
    campaign_id: str | None = field(default=None)

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
    last_updated: str | None = None
    embedding_ref: str | None = None
    memory_content: dict | None = field(default=None)

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
    started_at: str | None = None
    completed_at: str | None = None
    duration: float | None = None
    artifacts: list[str] = field(default_factory=list)
    error: str | None = None
    next_gate: str | None = None
    gate_decision: str | None = None


@dataclass
class ParameterMatrixEntry:
    """One SQX parameter justification entry."""

    tab: str
    parameter: str
    value: Any
    rationale: str
    source: str = "default"
    confidence: float = 0.5
    hypothesis_ref: str | None = None


@dataclass
class FeedbackRecord:
    """Guardian feedback record for live degradation or parameter drift."""

    campaign_id: str
    strategy_id: str | None = None
    event_type: str = "DEGRADING"
    severity: str = "WARNING"
    metric_delta: dict[str, float] | None = None
    parameter_deltas: list[dict[str, Any]] = field(default_factory=list)
    detected_at: str | None = None
    recommended_action: str | None = None


@dataclass
class MaintenancePlan:
    """Campaign maintenance plan and replacement runbook."""

    campaign_id: str
    review_cycle_days: int = 30
    replacement_candidates: list[str] = field(default_factory=list)
    live_strategy_ids: list[str] = field(default_factory=list)
    disconnected_strategy_ids: list[str] = field(default_factory=list)
    notes: str | None = None
    updated_at: str | None = None