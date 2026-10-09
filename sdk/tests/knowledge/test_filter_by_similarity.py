"""Tests for QueryBuilder.filter_by_similarity."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from quantlab.knowledge.query import QueryBuilder
from quantlab.knowledge.store import KnowledgeStore
from quantlab.knowledge.models import QueryFilter


# Helper to mock EmbeddingService with controlled similarity scores
def mock_embedding_service_with_scores(score_sequence: list[float]):
    """Create a mock EmbeddingService that returns controlled similarity scores.
    
    Args:
        score_sequence: List of similarity scores, one per campaign in alphabetical order
                        (hyp_bb, hyp_donchian, hyp_macd, hyp_rsi).
    """
    class MockEmbeddingService:
        fallback_enabled = True
        _model_loaded = True
        _model = None
        
        async def embed(self, texts):
            return np.random.rand(len(texts), 384).astype(np.float32)
        
        def similarity_batch(self, query, candidates):
            # Return the exact score_sequence as array (one per candidate)
            # campaigns are in alphabetical order: hyp_bb, hyp_donchian, hyp_macd, hyp_rsi
            return np.array(score_sequence, dtype=np.float32)
    
    return patch("quantlab.knowledge.embedding_service.EmbeddingService", return_value=MockEmbeddingService())


class TestFilterBySimilarity:
    """Tests for semantic similarity filtering."""

    @pytest.fixture
    def temp_store(self):
        """Create a temporary Knowledge Lake with test campaigns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = KnowledgeStore(root=Path(tmpdir))
            store.initialize()

            # Create campaign directories with metrics in "structured/" (what Indexer reads)
            for cid, tags, metrics in [
                ("hyp_rsi", ["mean_reversion", "rsi"], {"sharpe_ratio": 1.8}),
                ("hyp_macd", ["trend", "macd"], {"sharpe_ratio": 1.2}),
                ("hyp_bb", ["mean_reversion", "bollinger"], {"sharpe_ratio": 2.1}),
                ("hyp_donchian", ["breakout", "trend"], {"sharpe_ratio": 0.9}),
            ]:
                campaign_dir = store.root / "structured" / cid
                campaign_dir.mkdir(parents=True, exist_ok=True)
                (campaign_dir / "metrics.yaml").write_text(
                    "\n".join(f"{k}: {v}" for k, v in metrics.items()),
                    encoding="utf-8",
                )
                # Add tags
                store.tag(cid, tags)

            store.rebuild_index()
            yield store

    def test_filter_by_similarity_sets_fields(self):
        """filter_by_similarity sets the correct filter fields."""
        builder = QueryBuilder(index={}, root=Path("."))
        builder.filter_by_similarity("RSI mean reversion", top_k=5, threshold=0.5)

        assert builder._filter.similarity_text == "RSI mean reversion"
        assert builder._filter.similarity_top_k == 5
        assert builder._filter.similarity_threshold == 0.5

    def test_filter_by_similarity_defaults(self):
        """Defaults are top_k=10, threshold=0.7."""
        builder = QueryBuilder(index={}, root=Path("."))
        builder.filter_by_similarity("test")

        assert builder._filter.similarity_top_k == 10
        assert builder._filter.similarity_threshold == 0.7

    def test_chaining(self):
        """filter_by_similarity chains with other filters."""
        builder = QueryBuilder(index={}, root=Path("."))
        result = (
            builder.filter_by_similarity("RSI")
            .filter_by_sharpe(min_val=1.0)
            .limit(3)
        )
        assert result is builder

    @pytest.mark.asyncio
    async def test_similarity_ranking_rsi(self, temp_store):
        """Campaigns with RSI tags rank higher for RSI query."""
        # Campaigns are extracted in alphabetical order: hyp_bb, hyp_donchian, hyp_macd, hyp_rsi
        # Assign scores so hyp_rsi (last alphabetically) gets highest score
        with mock_embedding_service_with_scores([0.1, 0.3, 0.6, 0.9]):
            index = temp_store.read_index()
            builder = QueryBuilder(index=index, root=temp_store.root)
            builder.filter_by_similarity("RSI mean reversion", top_k=3, threshold=0.1)

            campaigns = builder._extract_campaigns(index)
            assert len(campaigns) == 4

            # Apply similarity filter
            filtered = builder._apply_similarity_filter(temp_store, campaigns)

            # Should return campaigns (all pass threshold=0.1 with mock)
            # RSI campaign should rank highest
            assert len(filtered) <= 3  # top_k=3
            assert filtered[0].campaign_id == "hyp_rsi"
            assert "mean_reversion" in filtered[0].tags

    @pytest.mark.asyncio
    async def test_similarity_respects_top_k(self, temp_store):
        """top_k limits results."""
        # Alphabetical order: hyp_bb, hyp_donchian, hyp_macd, hyp_rsi
        with mock_embedding_service_with_scores([0.2, 0.4, 0.6, 0.8]):
            index = temp_store.read_index()
            builder = QueryBuilder(index=index, root=temp_store.root)
            builder.filter_by_similarity("strategy", top_k=2, threshold=0.0)

            campaigns = builder._extract_campaigns(index)
            filtered = builder._apply_similarity_filter(temp_store, campaigns)

            assert len(filtered) == 2

    @pytest.mark.asyncio
    async def test_similarity_respects_threshold(self, temp_store):
        """threshold filters out low-similarity campaigns."""
        # All scores below 0.9 (max is 0.8 for hyp_rsi last)
        with mock_embedding_service_with_scores([0.2, 0.4, 0.6, 0.8]):
            index = temp_store.read_index()
            builder = QueryBuilder(index=index, root=temp_store.root)
            # Very high threshold - should filter most out
            builder.filter_by_similarity("completely unrelated text", top_k=10, threshold=0.9)

            campaigns = builder._extract_campaigns(index)
            filtered = builder._apply_similarity_filter(temp_store, campaigns)

            # All scores < 0.9, so filtered should be empty
            assert len(filtered) == 0

    def test_similarity_integration_in_execute(self, temp_store):
        """Full execute() with similarity filter works."""
        # Alphabetical: hyp_bb(0.3), hyp_donchian(0.5), hyp_macd(0.7), hyp_rsi(0.9)
        # After similarity filter (top_k=2, threshold=0.1): keeps top 2 (hyp_rsi, hyp_macd)
        with mock_embedding_service_with_scores([0.3, 0.5, 0.7, 0.9]):
            index = temp_store.read_index()
            builder = QueryBuilder(index=index, root=temp_store.root)
            builder.filter_by_similarity("RSI", top_k=2, threshold=0.1)

            result = builder.execute(root=temp_store.root)

            assert isinstance(result.campaigns, list)
            assert len(result.campaigns) <= 2
            assert result.total_count == 2  # After similarity top_k (before other filters/pagination)
            assert result.query_time_ms >= 0

    @pytest.mark.asyncio
    async def test_similarity_with_combined_filters(self, temp_store):
        """Similarity filter combines with sharpe filter."""
        # Alphabetical: hyp_bb(0.9), hyp_donchian(0.2), hyp_macd(0.4), hyp_rsi(0.6)
        # After sharpe >= 1.5 filter: only hyp_rsi (1.8) and hyp_bb (2.1) remain
        # Both are mean_reversion, so both should pass similarity
        with mock_embedding_service_with_scores([0.9, 0.2, 0.4, 0.6]):
            index = temp_store.read_index()
            builder = QueryBuilder(index=index, root=temp_store.root)
            builder.filter_by_similarity("mean reversion", top_k=5, threshold=0.1)
            builder.filter_by_sharpe(min_val=1.5)

            result = builder.execute(root=temp_store.root)

            # Only hyp_rsi (1.8) and hyp_bb (2.1) have sharpe >= 1.5
            # Both are mean_reversion, so both should pass similarity
            assert len(result.campaigns) == 2
            campaign_ids = {c.campaign_id for c in result.campaigns}
            assert campaign_ids == {"hyp_rsi", "hyp_bb"}


class TestQueryFilterSimilarityFields:
    """Test QueryFilter dataclass has similarity fields."""

    def test_similarity_fields_exist(self):
        """QueryFilter has similarity_text, top_k, threshold."""
        from quantlab.knowledge.models import QueryFilter

        f = QueryFilter()
        assert hasattr(f, "similarity_text")
        assert hasattr(f, "similarity_top_k")
        assert hasattr(f, "similarity_threshold")
        assert f.similarity_text is None
        assert f.similarity_top_k == 10
        assert f.similarity_threshold == 0.7

    def test_similarity_fields_settable(self):
        """Fields can be set."""
        from quantlab.knowledge.models import QueryFilter

        f = QueryFilter(
            similarity_text="test",
            similarity_top_k=5,
            similarity_threshold=0.5,
        )
        assert f.similarity_text == "test"
        assert f.similarity_top_k == 5
        assert f.similarity_threshold == 0.5