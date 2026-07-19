"""Knowledge Lake indexer — extract campaign metrics and build enhanced index.

Provides the Indexer class that reads campaign stats YAML from the Knowledge
Lake ``knowledge/stats/`` directory, extracts structured metric data, and
enriches the index with campaign metadata, tags, and link relationships.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# v2 index fields (beyond the basic IndexEntry from store.py)
METRIC_FIELDS = [
    "sharpe_ratio",
    "profit_factor",
    "win_rate",
    "max_drawdown",
    "total_trades",
    "net_profit",
    "expectancy",
    "sortino_ratio",
    "recovery_factor",
    "mar_ratio",
]


class Indexer:
    """Enhanced indexer for Knowledge Lake campaign metadata.

    Reads campaign stats YAML files, extracts metrics, and produces
    a v2 index schema with metric fields, tags, and links.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self._stats_dir = self.root / "stats"
        self._tags_dir = self.root / "tags"
        self._links_dir = self.root / "links"

    # ── Public API ──────────────────────────────────────────────────────────────

    def build_index(self) -> dict[str, dict[str, Any]]:
        """Scan the Knowledge Lake and build a v2 enriched index.

        Walks ``knowledge/stats/`` for campaign YAML files, extracts
        metric fields, tags, and links, and returns the enriched index.

        Returns:
            Dict mapping campaign path -> enriched metadata dict with
            metrics, tags, links, and basic file info.
        """
        index: dict[str, dict[str, Any]] = {}

        # Scan stats directory for campaign YAML files
        if not self._stats_dir.exists():
            return index

        for yaml_path in sorted(self._stats_dir.rglob("*.yaml")):
            try:
                campaign_id = yaml_path.stem  # filename without .yaml
                stats_data = self._load_stats_yaml(yaml_path)
                if stats_data is None:
                    continue

                entry = self._build_entry(campaign_id, stats_data)
                entry["tags"] = self._load_tags(campaign_id)
                entry["links"] = self._load_links(campaign_id)
                index[campaign_id] = entry

            except Exception as e:
                logger.warning(f"Failed to index {yaml_path}: {e}")
                continue

        return index

    def enhance_index(self, store: Any) -> dict[str, dict[str, Any]]:
        """Read stats YAML, extract metrics, enrich index entries.

        Compatibility wrapper that works with a KnowledgeStore instance.
        Reads the current index and enriches it with metric data.

        Args:
            store: KnowledgeStore instance (or any object with a root attribute).

        Returns:
            Enriched index dict with metric fields added to each entry.
        """
        store_root = Path(store.root) if hasattr(store, "root") else self.root
        indexer = Indexer(store_root)
        return indexer.build_index()

    # ── Tag & Link Management ────────────────────────────────────────────────────

    @staticmethod
    def tag_campaign(
        store: Any, campaign_id: str, tags: list[str]
    ) -> None:
        """Tag a campaign with the given tags.

        Tags are stored as individual files in ``knowledge/tags/{campaign_id}.yaml``.

        Args:
            store: KnowledgeStore instance.
            campaign_id: Campaign identifier.
            tags: List of tag strings to apply.
        """
        root = Path(store.root) if hasattr(store, "root") else Path("knowledge")
        tags_dir = root / "tags"
        tags_dir.mkdir(parents=True, exist_ok=True)

        tag_file = tags_dir / f"{campaign_id}.yaml"

        # Load existing tags and merge
        existing: list[str] = []
        if tag_file.exists():
            try:
                data = yaml.safe_load(tag_file.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "tags" in data:
                    existing = data["tags"]
            except Exception:
                pass

        # Merge: union of existing + new tags
        merged = list(dict.fromkeys(existing + tags))  # ordered unique

        tag_file.write_text(
            yaml.dump({"campaign_id": campaign_id, "tags": merged}),
            encoding="utf-8",
        )

    @staticmethod
    def get_tags(store: Any, campaign_id: str) -> list[str]:
        """Get tags for a campaign.

        Args:
            store: KnowledgeStore instance.
            campaign_id: Campaign identifier.

        Returns:
            List of tag strings, or empty list if not found.
        """
        root = Path(store.root) if hasattr(store, "root") else Path("knowledge")
        tag_file = root / "tags" / f"{campaign_id}.yaml"
        if not tag_file.exists():
            return []
        try:
            data = yaml.safe_load(tag_file.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "tags" in data:
                return data["tags"]
        except Exception:
            pass
        return []

    @staticmethod
    def link_campaigns(
        store: Any, parent: str, children: list[str]
    ) -> None:
        """Create parent-child links between campaigns.

        Links are stored bidirectionally in
        ``knowledge/links/{campaign_id}.yaml``.

        Args:
            store: KnowledgeStore instance.
            parent: Parent campaign identifier.
            children: List of child campaign identifiers.
        """
        root = Path(store.root) if hasattr(store, "root") else Path("knowledge")
        links_dir = root / "links"
        links_dir.mkdir(parents=True, exist_ok=True)

        # Parent -> children link
        parent_file = links_dir / f"{parent}.yaml"
        existing_parent: dict[str, list[str]] = {"children": []}
        if parent_file.exists():
            try:
                data = yaml.safe_load(parent_file.read_text(encoding="utf-8"))
                if isinstance(data, dict) and "children" in data:
                    existing_parent["children"] = data["children"]
            except Exception:
                pass

        merged_children = list(dict.fromkeys(existing_parent["children"] + children))
        parent_file.write_text(
            yaml.dump({"campaign_id": parent, "children": merged_children}),
            encoding="utf-8",
        )

        # Also store reverse links for each child
        for child in children:
            child_file = links_dir / f"{child}.yaml"
            existing_child: dict[str, list[str]] = {"parents": []}
            if child_file.exists():
                try:
                    data = yaml.safe_load(child_file.read_text(encoding="utf-8"))
                    if isinstance(data, dict) and "parents" in data:
                        existing_child["parents"] = data["parents"]
                except Exception:
                    pass

            if parent not in existing_child["parents"]:
                existing_child["parents"].append(parent)

            child_file.write_text(
                yaml.dump({"campaign_id": child, "parents": existing_child["parents"]}),
                encoding="utf-8",
            )

    @staticmethod
    def get_links(store: Any, campaign_id: str) -> dict[str, list[str]]:
        """Get links for a campaign (both parents and children).

        Args:
            store: KnowledgeStore instance.
            campaign_id: Campaign identifier.

        Returns:
            Dict with optional 'parents' and 'children' keys.
        """
        root = Path(store.root) if hasattr(store, "root") else Path("knowledge")
        link_file = root / "links" / f"{campaign_id}.yaml"
        if not link_file.exists():
            return {}
        try:
            data = yaml.safe_load(link_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                result: dict[str, list[str]] = {}
                if "parents" in data:
                    result["parents"] = data["parents"]
                if "children" in data:
                    result["children"] = data["children"]
                return result
        except Exception:
            pass
        return {}

    # ── Legacy v1 → v2 Migration ────────────────────────────────────────────────

    @staticmethod
    def migrate_v1_to_v2(v1_index: dict) -> dict:
        """Migrate a v1 index schema to v2.

        v1 schema::

            _generated: "..."
            _version: "1"
            directories:
              raw:
                "raw/campaign_123.yaml":
                  size: 1234
                  sha256: "abc..."
                  created: "2024-01-01T00:00:00"

        v2 schema adds metric fields, tags, and links per campaign entry.

        Args:
            v1_index: The v1 index dict loaded from index.yaml.

        Returns:
            Index dict upgraded to v2 schema with enriched entries.
        """
        v2 = dict(v1_index)
        v2["_version"] = "2"

        # v2 adds an enriched 'campaigns' section alongside 'directories'
        if "campaigns" not in v2:
            v2["campaigns"] = {}

        return v2

    # ── Internal Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _load_stats_yaml(path: Path) -> dict[str, Any] | None:
        """Load and validate a campaign stats YAML file."""
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
            return None
        except Exception:
            return None

    def _build_entry(
        self, campaign_id: str, stats_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Build an enriched index entry from stats data."""
        entry: dict[str, Any] = {
            "campaign_id": campaign_id,
            "indexed_at": datetime.now().isoformat(),
        }

        # Extract metrics
        metrics: dict[str, float | int | None] = {}
        for field in METRIC_FIELDS:
            # Try multiple key naming conventions
            value = stats_data.get(field)
            if value is None:
                value = stats_data.get(field.lower())
            if value is None:
                value = stats_data.get(field.replace("_", ""))
            if value is not None:
                try:
                    metrics[field] = float(value)
                except (ValueError, TypeError):
                    pass

        if metrics:
            entry["metrics"] = metrics

        # Extract campaign metadata from stats
        for meta_field in ("name", "symbol", "timeframe", "created_at", "campaign_type"):
            if meta_field in stats_data:
                entry[meta_field] = stats_data[meta_field]

        return entry

    def _load_tags(self, campaign_id: str) -> list[str]:
        """Load tags for a campaign from ``knowledge/tags/``."""
        tag_file = self._tags_dir / f"{campaign_id}.yaml"
        if not tag_file.exists():
            return []
        try:
            data = yaml.safe_load(tag_file.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "tags" in data:
                return data["tags"]
        except Exception:
            pass
        return []

    def _load_links(self, campaign_id: str) -> dict[str, list[str]]:
        """Load links for a campaign from ``knowledge/links/``."""
        link_file = self._links_dir / f"{campaign_id}.yaml"
        if not link_file.exists():
            return {}
        try:
            data = yaml.safe_load(link_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                result: dict[str, list[str]] = {}
                if "parents" in data:
                    result["parents"] = data["parents"]
                if "children" in data:
                    result["children"] = data["children"]
                return result
        except Exception:
            pass
        return {}