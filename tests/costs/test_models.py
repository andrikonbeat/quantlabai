"""Tests for quantlab.costs.models — commission, swap, slippage, sessions, spreads."""

import pytest
from pydantic import ValidationError


# ── CommissionSchema tests ─────────────────────────────────────────


class TestCommissionFixed:
    """CommissionSchema with type='fixed'."""

    def test_fixed_commission_flat_fee(self):
        from quantlab.costs.models import CommissionSchema

        c = CommissionSchema(type="fixed", value=5.0)
        assert c.compute(1.0) == 5.0

    def test_fixed_commission_ignores_volume(self):
        from quantlab.costs.models import CommissionSchema

        c = CommissionSchema(type="fixed", value=3.0)
        assert c.compute(10.0) == 3.0

    def test_fixed_commission_zero_value(self):
        from quantlab.costs.models import CommissionSchema

        c = CommissionSchema(type="fixed", value=0.0)
        assert c.compute(1.0) == 0.0


class TestCommissionPercent:
    """CommissionSchema with type='percent'."""

    def test_percent_commission_computes_correctly(self):
        from quantlab.costs.models import CommissionSchema

        c = CommissionSchema(type="percent", value=0.1)
        result = c.compute(volume=1.0, notional=100_000)
        assert result == 100.0  # 0.1% of 100k

    def test_percent_commission_no_notional_returns_zero(self):
        from quantlab.costs.models import CommissionSchema

        c = CommissionSchema(type="percent", value=0.1)
        assert c.compute(volume=1.0) == 0.0

    def test_percent_small_notional(self):
        from quantlab.costs.models import CommissionSchema

        c = CommissionSchema(type="percent", value=0.05)
        result = c.compute(volume=0.1, notional=10_000)
        assert result == 5.0  # 0.05% of 10k


class TestCommissionTiered:
    """CommissionSchema with type='tiered'."""

    def test_tiered_commission_first_tier_only(self):
        from quantlab.costs.models import CommissionSchema

        c = CommissionSchema(
            type="tiered",
            tiers=[(0, 100_000, 3.0), (100_000, 1_000_000_000, 2.0)],
        )
        # 50k notional → all in first tier: 50k * 3.0 / 100k = 1.5
        result = c.compute(volume=0.5, notional=50_000)
        assert result == pytest.approx(1.5)

    def test_tiered_commission_spans_tiers(self):
        from quantlab.costs.models import CommissionSchema

        c = CommissionSchema(
            type="tiered",
            tiers=[(0, 100_000, 3.0), (100_000, 1_000_000_000, 2.0)],
        )
        # 200k notional → first 100k at 3.0/100k = 3.0, next 100k at 2.0/100k = 2.0
        result = c.compute(volume=2.0, notional=200_000)
        assert result == pytest.approx(5.0)

    def test_tiered_commission_no_notional_returns_zero(self):
        from quantlab.costs.models import CommissionSchema

        c = CommissionSchema(
            type="tiered",
            tiers=[(0, 100_000, 3.0), (100_000, 1_000_000_000, 2.0)],
        )
        assert c.compute(volume=1.0) == 0.0

    def test_tiered_commission_empty_tiers(self):
        from quantlab.costs.models import CommissionSchema

        c = CommissionSchema(type="tiered", tiers=[])
        result = c.compute(volume=1.0, notional=100_000)
        assert result == 0.0


# ── SwapRule tests ────────────────────────────────────────────────


class TestSwapOvernight:
    """SwapRule night-hold swap computation."""

    def test_overnight_swap_long(self):
        from quantlab.costs.models import SwapRule

        s = SwapRule(long_rate=0.5, short_rate=-1.2, triple_day="Wednesday")
        result = s.compute(direction="LONG", weekday="Tuesday")
        assert result == 0.5

    def test_overnight_swap_short(self):
        from quantlab.costs.models import SwapRule

        s = SwapRule(long_rate=0.5, short_rate=-1.2, triple_day="Wednesday")
        result = s.compute(direction="SHORT", weekday="Tuesday")
        assert result == -1.2

    def test_triple_swap_long(self):
        from quantlab.costs.models import SwapRule

        s = SwapRule(long_rate=0.5, short_rate=-1.2, triple_day="Wednesday")
        result = s.compute(direction="LONG", weekday="Wednesday")
        assert result == 1.5  # 0.5 * 3

    def test_triple_swap_short(self):
        from quantlab.costs.models import SwapRule

        s = SwapRule(long_rate=0.5, short_rate=-1.2, triple_day="Wednesday")
        result = s.compute(direction="SHORT", weekday="Wednesday")
        assert result == pytest.approx(-3.6)  # -1.2 * 3

    def test_swap_default_weekday_is_tuesday(self):
        from quantlab.costs.models import SwapRule

        s = SwapRule(long_rate=0.5, short_rate=-1.2, triple_day="Wednesday")
        # No weekday specified → default is Tuesday (non-triple)
        result = s.compute(direction="LONG")
        assert result == 0.5

    def test_triple_swap_different_triple_day(self):
        from quantlab.costs.models import SwapRule

        s = SwapRule(long_rate=0.3, short_rate=-0.8, triple_day="Friday")
        result = s.compute(direction="SHORT", weekday="Friday")
        assert result == pytest.approx(-2.4)  # -0.8 * 3


# ── SlippageProfile tests ─────────────────────────────────────────


class TestSlippageStatic:
    """SlippageProfile in static mode."""

    def test_static_slippage_returns_fixed_pips(self):
        from quantlab.costs.models import SlippageProfile

        s = SlippageProfile(mode="static", fixed_pips=0.5)
        assert s.get_slippage() == 0.5

    def test_static_slippage_ignores_session(self):
        from quantlab.costs.models import SlippageProfile

        s = SlippageProfile(mode="static", fixed_pips=0.5)
        assert s.get_slippage(session="London") == 0.5


class TestSlippageSession:
    """SlippageProfile in session mode."""

    def test_session_slippage_returns_session_pips(self):
        from quantlab.costs.models import SlippageProfile

        s = SlippageProfile(
            mode="session",
            fixed_pips=0.5,
            session_pips={"London": 0.3, "NewYork": 0.7},
        )
        assert s.get_slippage(session="London") == 0.3
        assert s.get_slippage(session="NewYork") == 0.7

    def test_session_slippage_fallback_to_fixed(self):
        from quantlab.costs.models import SlippageProfile

        s = SlippageProfile(
            mode="session",
            fixed_pips=0.5,
            session_pips={"London": 0.3},
        )
        # Asia not in session_pips → falls back to fixed_pips
        assert s.get_slippage(session="Asia") == 0.5

    def test_session_slippage_no_session_returns_fixed(self):
        from quantlab.costs.models import SlippageProfile

        s = SlippageProfile(
            mode="session",
            fixed_pips=0.5,
            session_pips={"London": 0.3},
        )
        assert s.get_slippage() == 0.5


# ── MarketSession tests ──────────────────────────────────────────


class TestMarketSession:
    """MarketSession model."""

    def test_session_has_name_and_multiplier(self):
        from quantlab.costs.models import MarketSession

        s = MarketSession(name="London", spread_multiplier=1.0)
        assert s.name == "London"
        assert s.spread_multiplier == 1.0

    def test_session_defaults(self):
        from quantlab.costs.models import MarketSession

        s = MarketSession(name="Tokyo")
        assert s.open_time == "00:00"
        assert s.close_time == "00:00"
        assert s.spread_multiplier == 1.0

    def test_session_negative_multiplier_raises(self):
        from quantlab.costs.models import MarketSession

        with pytest.raises(ValidationError):
            MarketSession(name="Invalid", spread_multiplier=-1.0)


# ── SpreadConfig tests ────────────────────────────────────────────


class TestSpreadConfig:
    """SpreadConfig — base, session overrides, effective spread."""

    def test_base_spread_unmodified_no_session(self):
        from quantlab.costs.models import SpreadConfig

        s = SpreadConfig(base_spread=1.2)
        assert s.effective_spread() == 1.2

    def test_session_aware_spread(self):
        from quantlab.costs.models import SpreadConfig

        s = SpreadConfig(base_spread=1.2, session_overrides={"London": 0.8})
        assert s.effective_spread(session="London") == 0.96

    def test_missing_session_uses_default_multiplier(self):
        from quantlab.costs.models import SpreadConfig

        s = SpreadConfig(base_spread=1.2, session_overrides={"London": 0.8})
        # Asia is not in overrides → multiplier = 1.0
        assert s.effective_spread(session="Asia") == 1.2

    def test_asset_defaults_not_used_in_effective_spread(self):
        from quantlab.costs.models import SpreadConfig

        s = SpreadConfig(
            base_spread=1.0,
            session_overrides={"London": 0.8},
            asset_defaults={"EURUSD": 0.5},
        )
        assert s.effective_spread(session="London") == 0.8
        assert s.effective_spread() == 1.0

    def test_negative_base_spread_raises(self):
        from quantlab.costs.models import SpreadConfig

        with pytest.raises(ValidationError):
            SpreadConfig(base_spread=-0.5)


# ── CostBreakdown tests ──────────────────────────────────────────


class TestCostBreakdown:
    """CostBreakdown structured result model."""

    def test_breakdown_holds_all_fields(self):
        from quantlab.costs.models import CostBreakdown

        b = CostBreakdown(
            symbol="EURUSD",
            volume=1.0,
            direction="LONG",
            commission=3.0,
            swap=0.5,
            slippage=0.3,
            spread=0.8,
            total_pips=1.6,
            total_cost=16.0,
        )
        assert b.symbol == "EURUSD"
        assert b.total_pips == 1.6
        assert b.total_cost == 16.0

    def test_breakdown_defaults(self):
        from quantlab.costs.models import CostBreakdown

        b = CostBreakdown(symbol="GBPUSD", volume=0.5, direction="SHORT")
        assert b.commission == 0.0
        assert b.swap == 0.0
        assert b.total_cost == 0.0


# ── CostsConfig tests ────────────────────────────────────────────


class TestCostsConfig:
    """CostsConfig DSL model."""

    def test_costs_config_requires_broker(self):
        from quantlab.costs.models import CostsConfig

        c = CostsConfig(broker="dukascopy")
        assert c.broker == "dukascopy"
        assert c.slippage_mode == "static"
        assert c.commission_override is None

    def test_costs_config_with_override(self):
        from quantlab.costs.models import CommissionSchema, CostsConfig

        c = CostsConfig(
            broker="oanda",
            commission_override=CommissionSchema(type="fixed", value=2.0),
            slippage_mode="session",
        )
        assert c.broker == "oanda"
        assert c.commission_override is not None
        assert c.commission_override.value == 2.0
        assert c.slippage_mode == "session"


# ── Model validation tests ────────────────────────────────────────


class TestCommissionValidation:
    """CommissionSchema Pydantic validation."""

    def test_invalid_commission_type_raises(self):
        from quantlab.costs.models import CommissionSchema

        with pytest.raises(ValidationError):
            CommissionSchema(type="invalid", value=1.0)

    def test_commission_defaults(self):
        from quantlab.costs.models import CommissionSchema

        c = CommissionSchema(type="fixed", value=5.0)
        assert c.currency == "USD"
        assert c.tiers == []
