"""Knowledge Lake indexer — extracts metrics and builds enhanced index."""

from __future__ import annotations

import yaml
from pathlib import Path
from typing import Optional

from quantlab.knowledge.models import CampaignMetrics


class Indexer:
    """Enhances Knowledge Lake index with campaign metrics and tags."""

    def __init__(self, store):
        self._store = store

    def extract_campaign_metrics(self, campaign_id: str) -> Optional[dict]:
        """Extract metrics from campaign stats YAML."""
        stats_path = self._store.root / "stats" / f"{campaign_id}.yaml"
        if not stats_path.exists():
            return None

        try:
            with open(stats_path) as f:
                stats = yaml.safe_load(f)
            if not stats:
                return None

            return {
                "sharpe_ratio": stats.get("sharpe_ratio"),
                "profit_factor": stats.get("profit_factor"),
                "win_rate": stats.get("win_rate"),
                "max_drawdown": stats.get("max_drawdown"),
                "total_trades": stats.get("total_trades"),
                "net_profit": stats.get("net_profit"),
            }
        except Exception:
            return None

    def extract_campaign_tags(self, campaign_id: str) -> list[str]:
        """Extract tags from campaign directory or index."""
        index = self._store.read_index()
        for dir_name in ["results", "campaigns"]:
            for rel_path, info in index.get("directories", {}).get(dir_name, {}).items():
                if Path(rel_path).stem == campaign_id:
                    return info.get("tags", [])
        return []

    def build_index(self, existing_index: dict | None = None) -> dict:
        """Build enhanced v2 index with metrics and tags.

        Args:
            existing_index: Pre-built index dict (from filesystem scan).
                If None, reads the current index from the store.

        Returns:
            Enhanced index dict with metrics and tags added.
        """
        if existing_index is not None:
            index = existing_index
        else:
            index = self._store.read_index()
        index["_version"] = 2

        # Enhance existing entries with metrics and tags
        for dir_name in ["results", "campaigns"]:
            if dir_name not in index.get("directories", {}):
                continue

            for rel_path, info in index["directories"][dir_name].items():
                campaign_id = Path(rel_path).stem

                # Extract and add metrics
                metrics = self.extract_campaign_metrics(campaign_id)
                if metrics:
                    info["metrics"] = {k: v for k, v in metrics.items() if v is not None}

                # Add tags
                tags = self.extract_campaign_tags(campaign_id)
                if tags:
                    info["tags"] = tags

        return index

    def tag_campaign(self, campaign_id: str, tags: list[str]) -> bool:
        """Add tags to a campaign."""
        index = self._store.read_index()

        for dir_name in ["results", "campaigns"]:
            if dir_name not in index.get("directories", {}):
                continue

            for rel_path, info in index["directories"][dir_name].items():
                if Path(rel_path).stem == campaign_id:
                    existing = set(info.get("tags", []))
                    existing.update(tags)
                    info["tags"] = sorted(existing)
                    self._store._write_index(index)
                    return True

        return False

    def link_campaigns(self, parent_id: str, child_ids: list[str]) -> bool:
        """Create parent-child relationships between campaigns."""
        index = self._store.read_index()

        parent_path = None
        for dir_name in ["results", "campaigns"]:
            for rel_path, info in index.get("directories", {}).get(dir_name, {}).items():
                if Path(rel_path).stem == parent_id:
                    parent_path = rel_path
                    break

        if not parent_path:
            return False

        # Update parent with children
        info = index["directories"][dir_name][parent_path]
        existing_children = set(info.get("linked_campaigns", []))
        existing_children.update(child_ids)
        info["linked_campaigns"] = sorted(existing_children)

        # Update children with parent
        for child_id in child_ids:
            for dir_name in ["results", "campaigns"]:
                for rel_path, info in index.get("directories", {}).get(dir_name, {}).items():
                    if Path(rel_path).stem == child_id:
                        existing_parents = set(info.get("linked_campaigns", []))
                        existing_parents.add(parent_id)
                        info["linked_campaigns"] = sorted(existing_parents)

        self._store._write_index(index)
        return True