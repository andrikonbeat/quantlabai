"""Tests for AssetEvaluator (E5)."""

import pytest
from quantlab.exploration.steps.asset_evaluator import AssetEvaluator, AssetScore


class TestAssetEvaluator:
    """Tests for the AssetEvaluator class."""

    def setup_method(self):
        self.evaluator = AssetEvaluator(
            capital_usd=100.0,
            max_risk_per_trade_pct=1.0,
            max_spread_pct_of_sl=0.20,
        )

    def test_evaluate_all_instruments(self):
        """Test evaluating all instruments."""
        results = self.evaluator.evaluate()

        assert len(results) > 0
        for score in results:
            assert isinstance(score, AssetScore)
            assert 0.0 <= score.score <= 1.0
            assert score.symbol in self.evaluator.INSTRUMENT_META
            assert score.min_viable_sl_pips > 0
            assert score.spread_cost_pct_of_sl >= 0.0
            assert score.capital_utilization_pct >= 0.0

    def test_evaluate_specific_symbols(self):
        """Test evaluating specific symbols."""
        results = self.evaluator.evaluate(["EURUSD", "GBPUSD", "XAUUSD"])

        assert len(results) == 3
        symbols = {r.symbol for r in results}
        assert symbols == {"EURUSD", "GBPUSD", "XAUUSD"}

    def test_allowed_markets_filter(self):
        """Test filtering by market type."""
        evaluator = AssetEvaluator(
            capital_usd=100.0,
            allowed_markets=["forex"],
        )
        results = evaluator.evaluate()
        for score in results:
            assert score.market == "forex"

    def test_tight_sl_feasibility(self):
        """Test tight SL feasibility for major pairs."""
        evaluator = AssetEvaluator(
            capital_usd=100.0,
            max_risk_per_trade_pct=1.0,
        )
        results = evaluator.evaluate(["EURUSD", "GBPUSD", "XAUUSD"])
        
        eur = next(r for r in results if r.symbol == "EURUSD")
        xau = next(r for r in results if r.symbol == "XAUUSD")
        
        # EURUSD should be feasible with tight SL
        assert eur.tight_sl_feasible is True
        # XAUUSD has higher min stop, might be less feasible
        # but still feasible with 100 USD capital

    def test_score_ordering(self):
        """Test that results are sorted by score descending."""
        results = self.evaluator.evaluate()
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_capital_utilization(self):
        """Test capital utilization calculation."""
        evaluator = AssetEvaluator(capital_usd=100.0)
        results = evaluator.evaluate(["EURUSD"])
        
        eur = results[0]
        assert eur.capital_utilization_pct > 0
        assert eur.capital_utilization_pct < 100  # Should not exceed 100%

    def test_filter_by_market(self):
        """Test filtering by market type."""
        evaluator = AssetEvaluator(
            capital_usd=100.0,
            allowed_markets=["metals"],
        )
        results = evaluator.evaluate()
        for score in results:
            assert score.market == "metals"
        
        # Should include XAUUSD, XAGUSD
        symbols = {r.symbol for r in results}
        assert "XAUUSD" in symbols


if __name__ == "__main__":
    pytest.main([__file__, "-v"])