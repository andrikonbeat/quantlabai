"""Tests for MarketEvaluator (E3)."""

import pytest
from quantlab.exploration.steps.market_evaluator import MarketEvaluator, MarketScore


class TestMarketEvaluator:
    """Tests for the MarketEvaluator class."""

    def setup_method(self):
        self.evaluator = MarketEvaluator(
            capital_usd=100.0,
            user_risk_pct=1.0,
            max_spread_pips=3.0,
            forbidden_markets=["BTCUSD"],
            required_sessions=["London"],
        )

    def test_evaluate_all_markets(self):
        """Test evaluating all available markets."""
        results = self.evaluator.evaluate()

        assert len(results) > 0
        for score in results:
            assert isinstance(score, MarketScore)
            assert 0.0 <= score.score <= 1.0
            assert score.market in self.evaluator.MARKET_META
            assert score.capital_fit >= 0.0
            assert score.risk_fit >= 0.0
            assert score.liquidity_score >= 0.0

    def test_evaluate_specific_markets(self):
        """Test evaluating a specific list of markets."""
        results = self.evaluator.evaluate(["EURUSD", "GBPUSD", "XAUUSD"])

        assert len(results) == 3
        markets = {r.market for r in results}
        assert markets == {"EURUSD", "GBPUSD", "XAUUSD"}

    def test_forbidden_markets_excluded(self):
        """Test that forbidden markets are excluded."""
        results = self.evaluator.evaluate(["EURUSD", "BTCUSD"])
        markets = {r.market for r in results}
        assert "BTCUSD" not in markets
        assert "EURUSD" in markets

    def test_session_filter(self):
        """Test session filtering."""
        evaluator = MarketEvaluator(
            capital_usd=1000.0,
            required_sessions=["Tokyo"],
        )
        results = evaluator.evaluate()
        for score in results:
            assert "Tokyo" in score.trading_hours_overlap

    def test_spread_filter(self):
        """Test spread filtering."""
        evaluator = MarketEvaluator(
            capital_usd=1000.0,
            max_spread_pips=1.0,
        )
        results = evaluator.evaluate()
        for score in results:
            assert score.spread_typical_pips <= 1.0

    def test_score_ordering(self):
        """Test that results are sorted by score descending."""
        results = self.evaluator.evaluate()
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_rationale_contains_key_info(self):
        """Test that rationale contains key information."""
        results = self.evaluator.evaluate()
        for score in results:
            # The rationale uses the full market name from meta (e.g. 'EURUSD')
            # but may use the display name. Check for key terms instead.
            assert "spread" in score.rationale.lower()
            assert "daily range" in score.rationale.lower() or "daily range" in score.rationale.lower()
            assert "session" in score.rationale.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])