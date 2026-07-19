"""Knowledge Lake query builder — fluent API for campaign queries."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from quantlab.knowledge.models import CampaignSummary, CampaignMetrics, QueryFilter, QueryResult


class QueryBuilder:
    """Fluent query builder for Knowledge Lake campaigns."""

    def __init__(self, index: dict, root: Path):
        self._index = index
        self._root = root
        self._filter = QueryFilter()

    def filter_by_sharpe(self, min_val: float = None, max_val: float = None) -> "QueryBuilder":
        """Filter by Sharpe ratio range."""
        if min_val is not None:
            self._filter.sharpe_min = min_val
        if max_val is not None:
            self._filter.sharpe_max = max_val
        return self

    def filter_by_profit_factor(self, min_val: float = None) -> "QueryBuilder":
        """Filter by minimum profit factor."""
        self._filter.profit_factor_min = min_val
        return self

    def filter_by_win_rate(self, min_val: float = None) -> "QueryBuilder":
        """Filter by minimum win rate."""
        self._filter.win_rate_min = min_val
        return self

    def filter_by_max_drawdown(self, max_val: float = None) -> "QueryBuilder":
        """Filter by maximum drawdown (upper bound)."""
        self._filter.max_drawdown_max = max_val
        return self

    def filter_by_tags(self, tags: list[str], match_all: bool = True) -> "QueryBuilder":
        """Filter by tags (AND match by default)."""
        self._filter.tags = tags
        return self

    def filter_by_date(self, start: str | datetime = None, end: str | datetime = None) -> "QueryBuilder":
        """Filter by creation date range."""
        if isinstance(start, str):
            start = datetime.fromisoformat(start)
        if isinstance(end, str):
            end = datetime.fromisoformat(end)
        self._filter.date_start = start
        self._filter.date_end = end
        return self

    def search_text(self, text: str) -> "QueryBuilder":
        """Full-text search across campaign names and tags."""
        self._filter.text_search = text
        return self

    def sort_by(self, field: str, ascending: bool = False) -> "QueryBuilder":
        """Set sort field and order."""
        self._filter.sort_by = field
        self._filter.sort_ascending = ascending
        return self

    def limit(self, n: int) -> "QueryBuilder":
        """Limit number of results."""
        self._filter.limit = n
        return self

    def offset(self, n: int) -> "QueryBuilder":
        """Skip first N results."""
        self._filter.offset = n
        return self

    def execute(self, root: Path = None) -> "QueryResult":
        """Execute the query and return results."""
        import time
        start = time.time()

        # Lazy import to avoid circular import
        from quantlab.knowledge.store import KnowledgeStore
        store = KnowledgeStore(root or self._root)
        index = store.read_index()

        campaigns = self._extract_campaigns(index)
        filtered = self._apply_filters(campaigns)
        sorted_campaigns = self._sort_results(filtered)

        # Apply pagination
        total = len(sorted_campaigns)
        paginated = sorted_campaigns[self._filter.offset:]
        if self._filter.limit:
            paginated = paginated[:self._filter.limit]

        return QueryResult(
            campaigns=paginated,
            total_count=total,
            query_time_ms=(time.time() - start) * 1000,
        )

    def _extract_campaigns(self, index: dict) -> list:
        """Extract campaign summaries from index."""
        from quantlab.knowledge.models import CampaignSummary, CampaignMetrics
        campaigns = []

        for dir_name in ["results", "campaigns"]:
            if dir_name not in index.get("directories", {}):
                continue

            for rel_path, info in index.get("directories", {}).get(dir_name, {}).items():
                campaign_id = info.get("path", "").split("/")[-1] if "/" in info.get("path", "") else ""

                metrics = info.get("metrics", {})
                if metrics:
                    campaign_metrics = CampaignMetrics(
                        sharpe_ratio=metrics.get("sharpe_ratio"),
                        profit_factor=metrics.get("profit_factor"),
                        win_rate=metrics.get("win_rate"),
                        max_drawdown=metrics.get("max_drawdown"),
                        total_trades=metrics.get("total_trades"),
                        net_profit=metrics.get("net_profit"),
                    )
                else:
                    campaign_metrics = None

                campaigns.append(CampaignSummary(
                    campaign_id=campaign_id,
                    name=campaign_id,
                    metrics=campaign_metrics,
                    tags=info.get("tags", []),
                    created=datetime.fromisoformat(info.get("created")) if info.get("created") else None,
                    path=info.get("path", ""),
                ))

        return campaigns

    def _apply_filters(self, campaigns: list) -> list:
        """Apply all filters to campaign list."""
        filtered = campaigns

        for campaign in campaigns:
            if not self._matches_filters(campaign):
                filtered = [c for c in filtered if c.campaign_id != campaign.campaign_id]

        return filtered

    def _matches_filters(self, campaign: "CampaignSummary") -> bool:
        """Check if campaign matches all filters."""
        f = self._filter
        m = campaign.metrics

        if m:
            if f.sharpe_min is not None and (m.sharpe_ratio is None or m.sharpe_ratio < f.sharpe_min):
                return False
            if f.sharpe_max is not None and (m.sharpe_ratio is None or m.sharpe_ratio > f.sharpe_max):
                return False
            if f.profit_factor_min is not None and (m.profit_factor is None or m.profit_factor < f.profit_factor_min):
                return False
            if f.win_rate_min is not None and (m.win_rate is None or m.win_rate < f.win_rate_min):
                return False
            if f.max_drawdown_max is not None and (m.max_drawdown is None or m.max_drawdown > f.max_drawdown_max):
                return False

        # Tags (AND match)
        if f.tags:
            campaign_tags = set(campaign.tags)
            if not all(tag in campaign_tags for tag in f.tags):
                return False

        # Date range
        if campaign.created:
            if f.date_start and campaign.created < f.date_start:
                return False
            if f.date_end and campaign.created > f.date_end:
                return False

        # Text search
        if f.text_search:
            search_lower = f.text_search.lower()
            searchable = f"{campaign.campaign_id} {' '.join(campaign.tags)}".lower()
            if search_lower not in searchable:
                return False

        return True

    def _sort_results(self, campaigns: list) -> list:
        """Sort campaigns by specified field."""
        f = self._filter

        def sort_key(c):
            if f.sort_by == "sharpe":
                return c.metrics.sharpe_ratio if c.metrics and c.metrics.sharpe_ratio else float('-inf')
            elif f.sort_by == "pf":
                return c.metrics.profit_factor if c.metrics and c.metrics.profit_factor else float('-inf')
            elif f.sort_by == "win_rate":
                return c.metrics.win_rate if c.metrics and c.metrics.win_rate else float('-inf')
            elif f.sort_by == "created":
                return c.created.timestamp() if c.created else float('-inf')
            return c.campaign_id

        return sorted(campaigns, key=sort_key, reverse=not f.sort_ascending)