"""Tests for Indexer strategy-type metrics aggregation (T9 task 1.4)."""

from __future__ import annotations

import pytest

from quantlab.knowledge.indexer import Indexer


SAMPLE_CAMPAIGNS = [
    {"campaign_id": "c1", "tags": ["trend", "macd"], "sharpe_ratio": 1.5, "win_rate": 0.55,
     "market": "EURUSD", "parameters": {"fast": 12, "slow": 26}},
    {"campaign_id": "c2", "tags": ["trend", "macd"], "sharpe_ratio": 2.5, "win_rate": 0.60,
     "market": "EURUSD", "parameters": {"fast": 8, "slow": 21}},
    {"campaign_id": "c3", "tags": ["mean_reversion", "rsi"], "sharpe_ratio": 0.5, "win_rate": 0.45,
     "market": "GBPUSD", "parameters": {"period": 14}},
    {"campaign_id": "c4", "tags": ["mean_reversion"], "sharpe_ratio": 1.0, "win_rate": None,
     "market": "GBPUSD", "parameters": {"period": 7}},
]


class TestComputeTagSharpeStats:
    """Indexer.compute_tag_sharpe_stats consolidates TagCalibrator logic."""

    def test_returns_per_tag_averages(self) -> None:
        stats = Indexer.compute_tag_sharpe_stats(SAMPLE_CAMPAIGNS)
        assert set(stats) == {"trend", "macd", "mean_reversion", "rsi"}
        assert stats["trend"]["avg_sharpe"] == pytest.approx(2.0)
        assert stats["trend"]["sample_count"] == 2
        assert stats["mean_reversion"]["avg_sharpe"] == pytest.approx(0.75)
        assert stats["rsi"]["avg_sharpe"] == pytest.approx(0.5)

    def test_matches_tag_calibrator(self) -> None:
        """Single implementation of the math: identical to TagCalibrator."""
        from quantlab.agents.tag_calibrator import TagCalibrator

        assert (
            Indexer.compute_tag_sharpe_stats(SAMPLE_CAMPAIGNS)
            == TagCalibrator._build_tag_stats(SAMPLE_CAMPAIGNS)
        )

    def test_accepts_indexer_entry_shape(self) -> None:
        """Also reads metrics/tags nested as build_index() emits them."""
        entries = [
            {"campaign_id": "c1", "tags": ["trend"],
             "metrics": {"sharpe_ratio": 1.5, "win_rate": 0.55}},
            {"campaign_id": "c2", "tags": ["trend"],
             "metrics": {"sharpe_ratio": 2.5, "win_rate": 0.65}},
        ]
        stats = Indexer.compute_tag_sharpe_stats(entries)
        assert stats["trend"]["avg_sharpe"] == pytest.approx(2.0)
        assert stats["trend"]["sample_count"] == 2

    def test_empty_input(self) -> None:
        assert Indexer.compute_tag_sharpe_stats([]) == {}

    def test_ignores_invalid_sharpes(self) -> None:
        campaigns = [
            {"campaign_id": "c1", "tags": ["x"], "sharpe_ratio": "bad"},
            {"campaign_id": "c2", "tags": ["x"], "sharpe_ratio": None},
        ]
        stats = Indexer.compute_tag_sharpe_stats(campaigns)
        assert stats["x"]["avg_sharpe"] == pytest.approx(0.0)
        assert stats["x"]["sample_count"] == 2


class TestComputeBestParamsByMarket:
    """Indexer.compute_best_params_by_market picks the best-sharpe params per market."""

    def test_picks_best_sharpe_per_market(self) -> None:
        best = Indexer.compute_best_params_by_market(SAMPLE_CAMPAIGNS)
        assert set(best) == {"EURUSD", "GBPUSD"}
        assert best["EURUSD"]["parameters"] == {"fast": 8, "slow": 21}
        assert best["EURUSD"]["sharpe_ratio"] == pytest.approx(2.5)
        assert best["EURUSD"]["campaign_id"] == "c2"
        assert best["GBPUSD"]["parameters"] == {"period": 7}
        assert best["GBPUSD"]["campaign_id"] == "c4"

    def test_accepts_indexer_entry_shape(self) -> None:
        entries = [
            {"campaign_id": "c1", "market": "EURUSD",
             "metrics": {"sharpe_ratio": 1.0}, "parameters": {"a": 1}},
            {"campaign_id": "c2", "market": "EURUSD",
             "metrics": {"sharpe_ratio": 3.0}, "parameters": {"a": 2}},
        ]
        best = Indexer.compute_best_params_by_market(entries)
        assert best["EURUSD"]["parameters"] == {"a": 2}
        assert best["EURUSD"]["campaign_id"] == "c2"

    def test_skips_entries_without_market_or_sharpe(self) -> None:
        campaigns = [
            {"campaign_id": "c1", "tags": ["x"]},  # no market, no sharpe
            {"campaign_id": "c2", "market": "EURUSD"},  # no sharpe
            {"campaign_id": "c3", "sharpe_ratio": 1.0},  # no market
        ]
        assert Indexer.compute_best_params_by_market(campaigns) == {}

    def test_empty_input(self) -> None:
        assert Indexer.compute_best_params_by_market([]) == {}
