"""Tests for quantlab.costs.profiles — broker presets and overrides."""

import pytest


class TestDukascopyProfile:
    """Dukascopy preset profile."""

    def test_dukascopy_commission_tiered(self):
        from quantlab.costs.profiles import BrokerProfile

        p = BrokerProfile.dukascopy()
        assert p.name == "dukascopy"
        assert p.commission.type == "tiered"

    def test_dukascopy_commission_for_100k(self):
        from quantlab.costs.profiles import BrokerProfile

        p = BrokerProfile.dukascopy()
        result = p.commission.compute(volume=1.0, notional=100_000)
        # First tier: 100k * 3.0 / 100k = 3.0
        assert result == pytest.approx(3.0)

    def test_dukascopy_commission_for_200k(self):
        from quantlab.costs.profiles import BrokerProfile

        p = BrokerProfile.dukascopy()
        result = p.commission.compute(volume=2.0, notional=200_000)
        # First 100k at 3.0/100k = 3.0, second 100k at 2.0/100k = 2.0
        assert result == pytest.approx(5.0)

    def test_dukascopy_spread(self):
        from quantlab.costs.profiles import BrokerProfile

        p = BrokerProfile.dukascopy()
        assert p.spread_config.base_spread == 0.8

    def test_dukascopy_swap_long_short(self):
        from quantlab.costs.profiles import BrokerProfile

        p = BrokerProfile.dukascopy()
        assert p.swap.long_rate == -0.5
        assert p.swap.short_rate == -1.2


class TestInteractiveBrokersProfile:
    """Interactive Brokers preset profile."""

    def test_ib_profile_name(self):
        from quantlab.costs.profiles import BrokerProfile

        p = BrokerProfile.interactive_brokers()
        assert p.name == "interactive_brokers"
        assert p.display_name == "Interactive Brokers"

    def test_ib_commission_tiered(self):
        from quantlab.costs.profiles import BrokerProfile

        p = BrokerProfile.interactive_brokers()
        assert p.commission.type == "tiered"
        assert len(p.commission.tiers) == 3

    def test_ib_commission_low_volume(self):
        from quantlab.costs.profiles import BrokerProfile

        p = BrokerProfile.interactive_brokers()
        # 10k notional → first tier: 10k * 0.5 / 100k = 0.05
        result = p.commission.compute(volume=0.1, notional=10_000)
        assert result == pytest.approx(0.05)

    def test_ib_commission_mid_volume(self):
        from quantlab.costs.profiles import BrokerProfile

        p = BrokerProfile.interactive_brokers()
        # 100k notional: 50k at 0.5/100k=0.25, 50k at 0.3/100k=0.15 → total 0.40
        result = p.commission.compute(volume=1.0, notional=100_000)
        assert result == pytest.approx(0.40)

    def test_ib_spread(self):
        from quantlab.costs.profiles import BrokerProfile

        p = BrokerProfile.interactive_brokers()
        assert p.spread_config.base_spread == 0.6


class TestOandaProfile:
    """OANDA preset profile."""

    def test_oanda_profile_name(self):
        from quantlab.costs.profiles import BrokerProfile

        p = BrokerProfile.oanda()
        assert p.name == "oanda"
        assert p.display_name == "OANDA"

    def test_oanda_commission_zero(self):
        from quantlab.costs.profiles import BrokerProfile

        p = BrokerProfile.oanda()
        assert p.commission.type == "fixed"
        assert p.commission.value == 0.0

    def test_oanda_spread(self):
        from quantlab.costs.profiles import BrokerProfile

        p = BrokerProfile.oanda()
        assert p.spread_config.base_spread == 1.2

    def test_oanda_swap(self):
        from quantlab.costs.profiles import BrokerProfile

        p = BrokerProfile.oanda()
        assert p.swap.long_rate == -0.4
        assert p.swap.short_rate == -1.0


class TestSessions:
    """Market sessions attached to broker profiles."""

    def test_dukascopy_has_three_sessions(self):
        from quantlab.costs.profiles import BrokerProfile

        p = BrokerProfile.dukascopy()
        assert len(p.sessions) == 3
        session_names = [s.name for s in p.sessions]
        assert "London" in session_names
        assert "NewYork" in session_names
        assert "Asia" in session_names

    def test_ib_has_sessions(self):
        from quantlab.costs.profiles import BrokerProfile

        p = BrokerProfile.interactive_brokers()
        assert len(p.sessions) >= 3


class TestCustomProfile:
    """BrokerProfile.with_overrides custom profiles."""

    def test_override_commission_only(self):
        from quantlab.costs.models import CommissionSchema
        from quantlab.costs.profiles import BrokerProfile

        base = BrokerProfile.dukascopy()
        custom = base.with_overrides(
            commission=CommissionSchema(type="fixed", value=2.0),
        )
        assert custom.commission.value == 2.0
        assert custom.commission.type == "fixed"
        # All other params inherit from Dukascopy
        assert custom.swap.long_rate == base.swap.long_rate
        assert custom.spread_config.base_spread == base.spread_config.base_spread
        assert custom.slippage.fixed_pips == base.slippage.fixed_pips

    def test_override_swap_only(self):
        from quantlab.costs.models import SwapRule
        from quantlab.costs.profiles import BrokerProfile

        base = BrokerProfile.dukascopy()
        custom = base.with_overrides(
            swap=SwapRule(long_rate=0.0, short_rate=0.0, triple_day="Wednesday"),
        )
        assert custom.swap.long_rate == 0.0
        assert custom.swap.short_rate == 0.0
        # Commission unchanged
        assert custom.commission.value == base.commission.value

    def test_override_spread_config(self):
        from quantlab.costs.models import SpreadConfig
        from quantlab.costs.profiles import BrokerProfile

        base = BrokerProfile.dukascopy()
        custom = base.with_overrides(
            spread_config=SpreadConfig(base_spread=0.5),
        )
        assert custom.spread_config.base_spread == 0.5
        assert custom.name == "dukascopy"

    def test_with_overrides_returns_new_instance(self):
        from quantlab.costs.profiles import BrokerProfile

        base = BrokerProfile.dukascopy()
        custom = base.with_overrides()
        # Should be a different instance with same values
        assert custom is not base
        assert custom.commission.value == base.commission.value
