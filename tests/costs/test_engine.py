"""Tests for quantlab.costs.engine — CostEngine: compute, compute_symbol, set_profile."""

import pytest


class TestCostEngineCompute:
    """CostEngine.compute() — per-trade cost computation."""

    def test_compute_dukascopy_eurusd_long_london(self):
        """Dukascopy, EURUSD 1 lot LONG, London session — known cost."""
        from quantlab.costs.engine import CostEngine
        from quantlab.costs.profiles import BrokerProfile

        engine = CostEngine(BrokerProfile.dukascopy())
        result = engine.compute(symbol="EURUSD", volume=100_000, direction="LONG", session="London")

        assert result.symbol == "EURUSD"
        assert result.volume == 100_000
        assert result.direction == "LONG"
        # Commission: tiered — 100k * 3.0/100k = 3.0
        assert result.commission == pytest.approx(3.0)
        # Swap: 0 (not held overnight)
        assert result.swap == 0.0
        # Slippage: static 0.5
        assert result.slippage == pytest.approx(0.5)
        # Spread: base 0.8 * London 1.0 = 0.8
        assert result.spread == pytest.approx(0.8)
        # Total pips: 0 + 0.5 + 0.8 = 1.3
        assert result.total_pips == pytest.approx(1.3)
        # Pip value: 10.0 per lot, volume=100000=1 lot → 10.0
        # Total cost: 3.0 + (1.3 * 10.0) = 16.0
        assert result.total_cost == pytest.approx(16.0)

    def test_compute_dukascopy_intraday_no_swap(self):
        """Intraday trade, held_overnight=False — swap component is 0."""
        from quantlab.costs.engine import CostEngine
        from quantlab.costs.profiles import BrokerProfile

        engine = CostEngine(BrokerProfile.dukascopy())
        result = engine.compute(
            symbol="EURUSD", volume=100_000, direction="LONG",
            session="London", held_overnight=False,
        )
        assert result.swap == 0.0

    def test_compute_dukascopy_held_overnight_includes_swap(self):
        """Overnight trade — swap is included."""
        from quantlab.costs.engine import CostEngine
        from quantlab.costs.profiles import BrokerProfile

        engine = CostEngine(BrokerProfile.dukascopy())
        result = engine.compute(
            symbol="EURUSD", volume=100_000, direction="LONG",
            session="London", held_overnight=True,
        )
        # Dukascopy long_rate = -0.5
        assert result.swap == pytest.approx(-0.5)

    def test_compute_interactive_brokers_costs(self):
        """Interactive Brokers — tiered commission, tight spreads."""
        from quantlab.costs.engine import CostEngine
        from quantlab.costs.profiles import BrokerProfile

        engine = CostEngine(BrokerProfile.interactive_brokers())
        result = engine.compute(symbol="EURUSD", volume=100_000, direction="LONG", session="London")

        # Commission: 50k at 0.5/100k=0.25, 50k at 0.3/100k=0.15 → 0.40
        assert result.commission == pytest.approx(0.40)
        # Slippage: static 0.3
        assert result.slippage == pytest.approx(0.3)
        # Spread: base 0.6 * London 1.0 = 0.6
        assert result.spread == pytest.approx(0.6)

    def test_compute_oanda_zero_commission(self):
        """OANDA — spread-only pricing, commission is 0."""
        from quantlab.costs.engine import CostEngine
        from quantlab.costs.profiles import BrokerProfile

        engine = CostEngine(BrokerProfile.oanda())
        result = engine.compute(symbol="EURUSD", volume=100_000, direction="LONG", session="London")

        assert result.commission == 0.0
        # Spread: base 1.2 * London 1.0 = 1.2
        assert result.spread == pytest.approx(1.2)

    def test_compute_with_session_ny_spread_multiplier(self):
        """NewYork session applies higher spread multiplier."""
        from quantlab.costs.engine import CostEngine
        from quantlab.costs.profiles import BrokerProfile

        engine = CostEngine(BrokerProfile.dukascopy())
        result = engine.compute(
            symbol="EURUSD", volume=100_000, direction="SHORT", session="NewYork",
        )
        # Dukascopy NewYork multiplier = 1.2 → spread = 0.8 * 1.2 = 0.96
        assert result.spread == pytest.approx(0.96)

    def test_compute_short_direction_swap(self):
        """SHORT direction uses short_rate for swap."""
        from quantlab.costs.engine import CostEngine
        from quantlab.costs.profiles import BrokerProfile

        engine = CostEngine(BrokerProfile.dukascopy())
        result = engine.compute(
            symbol="EURUSD", volume=100_000, direction="SHORT",
            session="London", held_overnight=True,
        )
        # Dukascopy short_rate = -1.2
        assert result.swap == pytest.approx(-1.2)

    def test_compute_asia_session_different_multiplier(self):
        """Asia session — higher spread multiplier than London."""
        from quantlab.costs.engine import CostEngine
        from quantlab.costs.profiles import BrokerProfile

        engine = CostEngine(BrokerProfile.dukascopy())
        result = engine.compute(
            symbol="EURUSD", volume=100_000, direction="LONG", session="Asia",
        )
        # Dukascopy Asia multiplier = 1.5 → spread = 0.8 * 1.5 = 1.2
        assert result.spread == pytest.approx(1.2)

    def test_compute_unknown_session_no_multiplier(self):
        """Unknown session — no multiplier applied, defaults to 1.0."""
        from quantlab.costs.engine import CostEngine
        from quantlab.costs.profiles import BrokerProfile

        engine = CostEngine(BrokerProfile.dukascopy())
        result = engine.compute(
            symbol="EURUSD", volume=100_000, direction="LONG", session="Sydney",
        )
        # Sydney not in profile sessions → multiplier = 1.0 → spread = 0.8
        assert result.spread == pytest.approx(0.8)

    def test_compute_zero_volume(self):
        """Zero volume — zero costs across the board."""
        from quantlab.costs.engine import CostEngine
        from quantlab.costs.profiles import BrokerProfile

        engine = CostEngine(BrokerProfile.dukascopy())
        result = engine.compute(
            symbol="EURUSD", volume=0, direction="LONG", session="London",
        )
        assert result.commission == 0.0
        assert result.total_cost == 0.0

    def test_compute_different_symbol_preserves_metadata(self):
        """Different symbol is correctly recorded in the breakdown."""
        from quantlab.costs.engine import CostEngine
        from quantlab.costs.profiles import BrokerProfile

        engine = CostEngine(BrokerProfile.dukascopy())
        result = engine.compute("GBPJPY", 50_000, "SHORT", "NewYork")
        assert result.symbol == "GBPJPY"
        assert result.volume == 50_000
        assert result.direction == "SHORT"


class TestCostEngineComputeSymbol:
    """CostEngine.compute_symbol() — per-symbol aggregation."""

    def test_compute_symbol_aggregates_multiple_trades(self):
        """Three EURUSD trades — returns aggregated totals."""
        from quantlab.costs.engine import CostEngine
        from quantlab.costs.profiles import BrokerProfile

        engine = CostEngine(BrokerProfile.dukascopy())
        # Trade 1: 1 lot LONG London
        engine.compute("EURUSD", 100_000, "LONG", "London")
        # Trade 2: 2 lots LONG London
        engine.compute("EURUSD", 200_000, "LONG", "London")
        # Trade 3: 0.5 lots SHORT NewYork
        engine.compute("EURUSD", 50_000, "SHORT", "NewYork")

        result = engine.compute_symbol("EURUSD")
        assert "total_cost" in result
        assert "avg_cost_per_trade" in result
        assert "min_commission" in result
        assert "max_commission" in result
        assert "trade_count" in result
        assert result["trade_count"] == 3
        assert isinstance(result["total_cost"], float)
        assert result["avg_cost_per_trade"] == pytest.approx(result["total_cost"] / 3, rel=1e-3)

    def test_compute_symbol_no_trades_returns_defaults(self):
        """No trades recorded for symbol — returns zeroed aggregation."""
        from quantlab.costs.engine import CostEngine
        from quantlab.costs.profiles import BrokerProfile

        engine = CostEngine(BrokerProfile.dukascopy())
        result = engine.compute_symbol("GBPUSD")
        assert result["trade_count"] == 0
        assert result["total_cost"] == 0.0

    def test_compute_symbol_separates_symbols(self):
        """Trades for different symbols are isolated."""
        from quantlab.costs.engine import CostEngine
        from quantlab.costs.profiles import BrokerProfile

        engine = CostEngine(BrokerProfile.dukascopy())
        engine.compute("EURUSD", 100_000, "LONG", "London")
        engine.compute("GBPUSD", 50_000, "SHORT", "London")
        engine.compute("EURUSD", 200_000, "LONG", "NewYork")

        eur = engine.compute_symbol("EURUSD")
        gbp = engine.compute_symbol("GBPUSD")
        assert eur["trade_count"] == 2
        assert gbp["trade_count"] == 1


class TestCostEngineSetProfile:
    """CostEngine.set_profile() — runtime profile switching."""

    def test_set_profile_by_name_switches_broker(self):
        """Switching from Dukascopy to IB changes cost parameters."""
        from quantlab.costs.engine import CostEngine
        from quantlab.costs.profiles import BrokerProfile

        engine = CostEngine(BrokerProfile.dukascopy())
        engine.set_profile("ib")
        result = engine.compute("EURUSD", 100_000, "LONG", "London")
        # IB commission should be lower than Dukascopy
        assert result.commission == pytest.approx(0.40)

    def test_set_profile_by_instance_switches_broker(self):
        """Passing a BrokerProfile instance switches the active profile."""
        from quantlab.costs.engine import CostEngine
        from quantlab.costs.profiles import BrokerProfile

        engine = CostEngine(BrokerProfile.dukascopy())
        engine.set_profile(BrokerProfile.oanda())
        result = engine.compute("EURUSD", 100_000, "LONG", "London")
        assert result.commission == 0.0

    def test_set_profile_unknown_name_raises(self):
        """Unknown profile name raises ValueError."""
        from quantlab.costs.engine import CostEngine
        from quantlab.costs.profiles import BrokerProfile

        engine = CostEngine(BrokerProfile.dukascopy())
        with pytest.raises(ValueError, match="Unknown profile"):
            engine.set_profile("nonexistent")

    def test_set_profile_preserves_capability(self):
        """After set_profile, engine still produces correct costs."""
        from quantlab.costs.engine import CostEngine
        from quantlab.costs.profiles import BrokerProfile

        engine = CostEngine(BrokerProfile.dukascopy())
        engine.set_profile("oanda")
        # OANDA has zero commission, wider spreads
        result = engine.compute("EURUSD", 100_000, "LONG", "London")
        assert result.commission == 0.0
        assert result.spread == pytest.approx(1.2)
