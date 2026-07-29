"""Tests for MarketGuardian CostCollector wiring (Task 4.4)."""

import pytest
from unittest.mock import MagicMock, patch

from quantlab.guardian.market import MarketGuardian
from quantlab.guardian.models import GuardianStatus


class FakeRegimeCollector:
    """Minimal regime collector for testing."""
    def collect(self, name: str) -> dict:
        return {"regime": "TREND", "confidence": 0.8}


class TestMarketGuardianCostCollector:
    """CostCollector wiring in MarketGuardian."""

    def test_uses_cost_collector_collect_all(self) -> None:
        """GIVEN a MarketGuardian with a real cost_collector
        WHEN check() is called
        THEN it calls collect_all() with major pairs.
        """
        collector = MagicMock()
        collector.collect_all.return_value = {
            "EURUSD": {"spread_pips": 0.8, "slippage_pips": 0.3, "session_name": None, "session_score": 0.5},
            "GBPUSD": {"spread_pips": 1.0, "slippage_pips": 0.4, "session_name": None, "session_score": 0.5},
        }

        guardian = MarketGuardian(
            regime_collector=FakeRegimeCollector(),
            cost_collector=collector,
        )
        result = guardian.check()
        assert result is not None
        assert isinstance(result.score, float)
        collector.collect_all.assert_called_once()

    def test_collect_all_failure_returns_fallback(self) -> None:
        """GIVEN a cost_collector that raises on collect_all
        WHEN check() is called
        THEN it falls back to empty cost_data and returns a score.
        """
        collector = MagicMock()
        collector.collect_all.side_effect = RuntimeError("Collector failed")

        guardian = MarketGuardian(
            regime_collector=FakeRegimeCollector(),
            cost_collector=collector,
        )
        result = guardian.check()
        assert result is not None
        assert isinstance(result.score, float)

    def test_score_liquidity_with_data(self) -> None:
        """GIVEN cost_data with spread_pips
        WHEN _score_liquidity is called
        THEN it computes a score based on average spread.
        """
        cost_data = {
            "EURUSD": {"spread_pips": 0.8, "slippage_pips": 0.3, "session_name": None, "session_score": 0.5},
            "GBPUSD": {"spread_pips": 1.2, "slippage_pips": 0.4, "session_name": None, "session_score": 0.5},
        }
        collector = MagicMock()
        collector.collect_all.return_value = cost_data

        guardian = MarketGuardian(
            regime_collector=FakeRegimeCollector(),
            cost_collector=collector,
        )
        # avg spread = (0.8 + 1.2) / 2 = 1.0 → score = 1 - 1.0/5 = 0.8
        score = guardian._score_liquidity(cost_data)
        assert 0.79 <= score <= 0.81

    def test_score_liquidity_empty_returns_default(self) -> None:
        """GIVEN empty cost_data
        WHEN _score_liquidity is called
        THEN it returns the unknown liquidity default 0.5.
        """
        guardian = MarketGuardian(
            regime_collector=FakeRegimeCollector(),
            cost_collector=MagicMock(),
        )
        score = guardian._score_liquidity({})
        assert score == 0.5

    def test_wide_spreads_returns_low_liquidity_score(self) -> None:
        """GIVEN cost_data with very wide spreads
        WHEN _score_liquidity is called
        THEN it returns a low score reflecting poor liquidity.
        """
        cost_data = {
            "EURUSD": {"spread_pips": 4.0, "slippage_pips": 1.0},
            "GBPUSD": {"spread_pips": 5.0, "slippage_pips": 1.5},
        }
        guardian = MarketGuardian(
            regime_collector=FakeRegimeCollector(),
            cost_collector=MagicMock(),
        )
        score = guardian._score_liquidity(cost_data)
        # avg spread = 4.5 → score = 1 - 4.5/5 = 0.1
        assert 0.09 <= score <= 0.11

    def test_check_returns_proper_status(self) -> None:
        """GIVEN a MarketGuardian with valid regime + cost data
        WHEN check() is called
        THEN it returns a GuardianResult with GREEN/YELLOW/RED status.
        """
        collector = MagicMock()
        collector.collect_all.return_value = {
            "EURUSD": {"spread_pips": 0.8, "slippage_pips": 0.3, "session_name": None, "session_score": 0.5},
        }
        guardian = MarketGuardian(
            regime_collector=FakeRegimeCollector(),
            cost_collector=collector,
        )
        result = guardian.check()
        assert result.status in (GuardianStatus.GREEN, GuardianStatus.YELLOW, GuardianStatus.RED)
