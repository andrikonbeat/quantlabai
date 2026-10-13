"""Tests for sections emitter/parser."""

import pytest

from quantlab.sqx.sections import (
    parse_cross_checks,
    parse_money_management,
    parse_trading_options,
    parse_costs,
    parse_fitness,
    parse_what_to_build,
    parse_stop,
    parse_range,
)


class TestSections:
    """Sections parser tests."""

    def test_parse_cross_checks_valid(self):
        """Parse valid cross-checks dict."""
        cc = {
            "RetestOnAdditionalMarkets": {"use": True, "date_from": "2020-01-01", "date_to": "2024-01-01"},
            "WalkForwardOptimization": {"use": True, "period": 10, "optimization": 15},
        }
        parsed = parse_cross_checks(cc)
        assert "RetestOnAdditionalMarkets" in parsed
        assert "WalkForwardOptimization" in parsed
        assert parsed["RetestOnAdditionalMarkets"]["use"] is True

    def test_parse_cross_checks_aliases(self):
        """Aliases should be normalized."""
        cc = {"mc_retest": {"use": True}}
        parsed = parse_cross_checks(cc)
        assert "MonteCarloRetest" in parsed

    def test_reject_invalid_cross_check_key(self):
        """Invalid cross-check key should fail."""
        cc = {"RetestWithHigherPrecision": {"use": True, "invalid_key": 123}}
        with pytest.raises(ValueError):
            parse_cross_checks(cc)

    def test_reject_missing_use(self):
        """Cross-check section missing 'use' should fail."""
        cc = {"RetestWithHigherPrecision": {"precision": 2}}
        with pytest.raises(ValueError):
            parse_cross_checks(cc)

    def test_parse_money_management_valid(self):
        """Valid money management dict should parse."""
        mm = {"method": "fixed_size", "size": 0.01, "initial_capital": 10000}
        parsed = parse_money_management(mm)
        assert parsed["method"] == "fixed_size"
        assert parsed["size"] == 0.01

    def test_reject_invalid_mm_method(self):
        """Invalid MM method should fail."""
        mm = {"method": "InvalidMethod", "size": 0.01, "initial_capital": 100}
        with pytest.raises(ValueError):
            parse_money_management(mm)

    def test_parse_trading_options(self):
        """Parse trading options."""
        to = {"session": "London", "max_trades_per_day": 2}
        parsed = parse_trading_options(to)
        assert parsed["session"] == "London"

    def test_parse_costs(self):
        """Parse costs section."""
        costs = {"spread": 5, "slippage": 1}
        parsed = parse_costs(costs)
        assert parsed["spread"] == 5

    def test_parse_fitness(self):
        """Parse fitness."""
        assert parse_fitness("ReturnDDRatio") == "ReturnDDRatio"
        assert parse_fitness(None) is None

    def test_parse_what_to_build(self):
        """Parse what_to_build."""
        wtb = {"market_sides": "both", "entry_symmetry": True}
        parsed = parse_what_to_build(wtb)
        assert parsed["market_sides"] == "both"

    def test_parse_stop(self):
        """Parse stop section."""
        stop = {"type": "passed-count", "count": 100}
        parsed = parse_stop(stop)
        assert parsed["type"] == "passed-count"
        assert parsed["count"] == 100

    def test_parse_stop_missing_type(self):
        """Missing stop type should fail."""
        with pytest.raises(ValueError):
            parse_stop({})

    def test_parse_range(self):
        """Parse range section."""
        r = {"from": "2010-01-01", "to": "2024-10-30"}
        parsed = parse_range(r)
        assert parsed["from"] == "2010-01-01"
        assert parsed["to"] == "2024-10-30"

    def test_parse_range_missing(self):
        """Missing range keys should fail."""
        with pytest.raises(ValueError):
            parse_range({"from": "2010-01-01"})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
