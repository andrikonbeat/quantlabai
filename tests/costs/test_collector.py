"""Tests for CostCollector — slippage/spread contract."""
from quantlab.costs.collector import CostCollector


class TestCostCollector:
    def test_get_recent_slippage_zero_arg_does_not_raise(self):
        collector = CostCollector()
        value = collector.get_recent_slippage()
        assert isinstance(value, float)

    def test_get_recent_slippage_with_symbol_returns_default(self):
        collector = CostCollector()
        assert collector.get_recent_slippage("EURUSD") == collector.get_recent_slippage()
