"""Tests for CapitalLimitsResolver (E7)."""

import pytest
from quantlab.exploration.steps.capital_limits import CapitalLimitsResolver, CapitalLimits, OperationalRestrictions


class TestCapitalLimitsResolver:
    """Tests for the CapitalLimitsResolver class."""

    def setup_method(self):
        self.resolver = CapitalLimitsResolver(min_lot_size=0.01, default_leverage=30.0)

    def test_resolve_basic(self):
        """Test basic capital limits resolution."""
        limits = self.resolver.resolve(
            capital_usd=1000.0,
            max_drawdown_pct=15.0,
            risk_per_trade_pct=1.0,
            max_concurrent_positions=3,
            instruments=["EURUSD"],
            timeframe="H1",
            leverage=30.0,
        )

        assert isinstance(limits, CapitalLimits)
        assert limits.max_drawdown_pct == 15.0
        assert limits.risk_per_trade_usd == 10.0  # 1% of 1000
        assert limits.max_concurrent_positions == 3
        assert limits.min_lot_size == 0.01
        assert limits.max_lot_size > 0.01
        assert limits.instruments == ["EURUSD"]
        assert limits.timeframe == "H1"

    def test_small_capital_tightens_drawdown(self):
        """Test that small capital tightens max drawdown."""
        limits = self.resolver.resolve(
            capital_usd=100.0,
            max_drawdown_pct=20.0,  # Request 20%, should be tightened
        )
        assert limits.max_drawdown_pct <= 15.0  # Should be tightened to 15% or less

    def test_risk_per_trade_usd_override(self):
        """Test explicit risk_per_trade_usd overrides percentage."""
        limits = self.resolver.resolve(
            capital_usd=1000.0,
            risk_per_trade_pct=1.0,
            risk_per_trade_usd=5.0,  # Explicit $5
        )
        assert limits.risk_per_trade_usd == 5.0

    def test_max_lot_by_leverage(self):
        """Test max lot calculation from leverage."""
        limits_low_lev = CapitalLimitsResolver().resolve(
            capital_usd=1000.0, leverage=10.0
        )
        limits_high_lev = CapitalLimitsResolver().resolve(
            capital_usd=1000.0, leverage=100.0
        )
        # Higher leverage should allow larger position
        assert limits_high_lev.max_lot_size >= limits_low_lev.max_lot_size

    def test_resolve_restrictions(self):
        """Test operational restrictions resolution."""
        restrictions = CapitalLimitsResolver().resolve_restrictions(
            trading_hours_utc="08:00-18:00",
            forbidden_days=["Saturday", "Sunday"],
            max_daily_trades=10,
            news_filter=True,
            max_spread_pips=2.0,
        )

        assert isinstance(restrictions, OperationalRestrictions)
        assert restrictions.trading_hours_utc == "08:00-18:00"
        assert restrictions.forbidden_days == ["Saturday", "Sunday"]
        assert restrictions.max_daily_trades == 10
        assert restrictions.news_filter is True
        assert restrictions.max_spread_pips == 2.0

    def test_default_restrictions(self):
        """Test default restrictions."""
        restrictions = CapitalLimitsResolver().resolve_restrictions()
        assert restrictions.trading_hours_utc == "00:00-23:59"
        assert restrictions.forbidden_days == []
        assert restrictions.max_daily_trades == 0
        assert restrictions.news_filter is False
        assert restrictions.max_spread_pips == 0.0

    def test_invalid_capital_raises(self):
        """Test that invalid capital raises ValueError."""
        with pytest.raises(ValueError):
            CapitalLimitsResolver().resolve(capital_usd=0.0)

        with pytest.raises(ValueError):
            CapitalLimitsResolver().resolve(capital_usd=-100.0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])