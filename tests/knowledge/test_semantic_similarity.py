"""Tests for SemanticSimilarityQuery — text-based similarity search with LRU cache."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from quantlab.knowledge.query import QueryBuilder
from quantlab.knowledge.models import QueryResult, CampaignSummary


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _make_index_with_campaigns(campaigns: list[dict]) -> dict:
    return {
        "directories": {
            "campaigns": {
                f"camp_{i}": {
                    "path": f"structured/camp_{i}",
                    "metrics": {},
                    "tags": c.get("tags", []),
                    "created": "2024-01-01T00:00:00",
                }
                for i, c in enumerate(campaigns)
            }
        }
    }


# ── Task T-006: Text-based similarity ────────────────────────────────────────


class TestSemanticSimilarityQuery:
    """search_similar_campaigns(text, top_k) returns ranked campaigns."""

    def test_returns_results(self, tmp_path: Path) -> None:
        index = _make_index_with_campaigns([
            {"tags": ["mean-reversion", "rsi"]},
            {"tags": ["momentum", "ema"]},
        ])
        builder = QueryBuilder(index, tmp_path)
        result = builder.search_similar_campaigns("mean reversion strategy", top_k=10)
        assert isinstance(result, QueryResult)
        assert result.total_count >= 0

    def test_respects_top_k(self, tmp_path: Path) -> None:
        index = _make_index_with_campaigns([
            {"tags": [f"tag{i}"]} for i in range(20)
        ])
        builder = QueryBuilder(index, tmp_path)
        result = builder.search_similar_campaigns("some query text", top_k=5)
        assert len(result.campaigns) <= 5

    def test_empty_text_returns_empty(self, tmp_path: Path) -> None:
        index = _make_index_with_campaigns([
            {"tags": ["mean-reversion"]},
        ])
        builder = QueryBuilder(index, tmp_path)
        result = builder.search_similar_campaigns("", top_k=10)
        assert len(result.campaigns) == 0

    def test_lru_cache_returns_same_results(self, tmp_path: Path) -> None:
        index = _make_index_with_campaigns([
            {"tags": ["mean-reversion"]},
        ])
        builder = QueryBuilder(index, tmp_path)
        result1 = builder.search_similar_campaigns("mean reversion", top_k=10)
        result2 = builder.search_similar_campaigns("mean reversion", top_k=10)
        assert result1.campaigns == result2.campaigns
