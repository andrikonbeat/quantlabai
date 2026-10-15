"""Tests for SmallCapitalRiskWarner (E1)."""

import pytest
from quantlab.exploration.steps.risk_warner import SmallCapitalRiskWarner, CapitalRiskWarning


class TestSmallCapitalRiskWarner:
    """Tests for the SmallCapitalRiskWarner class."""

    def test_warn_100usd_capital(self):
        """Test warning generation for $100 capital."""
        warner = SmallCapitalRiskWarner()
        warning = warner.warn(100.0, 30.0)

        assert isinstance(warning, CapitalRiskWarning)
        assert warning.capital_usd == 100.0
        assert warning.max_lot_size > 0
        assert warning.min_stop_loss_pips >= 10
        assert "CAPITAL CHICO" in warning.warning_text
        assert "$100" in warning.warning_text
        assert "ADVERTENCIA" in warning.warning_text

    def test_warn_500usd_capital(self):
        """Test warning generation for $500 capital."""
        warner = SmallCapitalRiskWarner()
        warning = warner.warn(500.0, 30.0)

        assert warning.capital_usd == 500.0
        assert "PRECAUCIÓN" in warning.warning_text or "ADVERTENCIA" in warning.warning_text

    def test_warn_10000usd_capital(self):
        """Test warning generation for $10000 capital (no special warning)."""
        warner = SmallCapitalRiskWarner()
        warning = warner.warn(10000.0, 30.0)

        assert warning.capital_usd == 10000.0
        assert warning.risk_of_ruin_pct < 20.0

    def test_warn_with_custom_leverage(self):
        """Test warning with custom leverage."""
        warner = SmallCapitalRiskWarner()
        warning_low = warner.warn(100.0, 10.0)
        warning_high = warner.warn(100.0, 100.0)

        assert warning_high.max_lot_size > warning_low.max_lot_size

    def test_warn_zero_capital_raises(self):
        """Test that zero capital raises ValueError."""
        warner = SmallCapitalRiskWarner()
        with pytest.raises(ValueError):
            warner.warn(0.0, 30.0)

    def test_negative_capital_raises(self):
        """Test that negative capital raises ValueError."""
        warner = SmallCapitalRiskWarner()
        with pytest.raises(ValueError):
            warner.warn(-100.0, 30.0)

    def test_convenience_function(self):
        """Test the convenience function."""
        from quantlab.exploration.steps.risk_warner import generate_small_capital_warning
        text = generate_small_capital_warning(100.0, 30.0)
        assert "CAPITAL CHICO" in text
        assert "$100" in text


class TestCapitalRiskWarning:
    """Tests for the CapitalRiskWarning dataclass."""

    def test_to_dict(self):
        warning = CapitalRiskWarning(
            capital_usd=100.0,
            max_lot_size=0.01,
            min_stop_loss_pips=15,
            recommended_timeframes=["M15", "H1"],
            risk_of_ruin_pct=45.5,
            warning_text="Test warning",
        )
        d = warning.to_dict()
        assert d["capital_usd"] == 100.0
        assert d["max_lot_size"] == 0.01
        assert d["min_stop_loss_pips"] == 15
        assert d["recommended_timeframes"] == ["M15", "H1"]
        assert d["risk_of_ruin_pct"] == 45.5
        assert d["warning_text"] == "Test warning"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])