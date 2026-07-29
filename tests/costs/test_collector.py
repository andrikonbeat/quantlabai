"""Tests for quantlab.costs.collector — CostCollector duck-type protocol."""

import pytest


class TestCostCollectorSlippage:
    """CostCollector.get_recent_slippage() and .slippage property."""

    def test_get_recent_slippage_returns_float(self):
        """get_recent_slippage returns current slippage in pips."""
        from quantlab.costs.collector import CostCollector

        collector = CostCollector()
        slippage = collector.get_recent_slippage("EURUSD")
        assert isinstance(slippage, float)
        assert slippage >= 0.0

    def test_get_recent_slippage_reflects_profile_slippage(self):
        """With a Dukascopy engine, slippage matches profile."""
        from quantlab.costs.engine import CostEngine
        from quantlab.costs.profiles import BrokerProfile
        from quantlab.costs.collector import CostCollector

        engine = CostEngine(BrokerProfile.dukascopy())
        collector = CostCollector(engine=engine)
        # Dukascopy static slippage = 0.5
        assert collector.get_recent_slippage("EURUSD") == pytest.approx(0.5)

    def test_get_recent_slippage_ib_lower_slippage(self):
        """IB profile has tighter slippage (0.3)."""
        from quantlab.costs.engine import CostEngine
        from quantlab.costs.profiles import BrokerProfile
        from quantlab.costs.collector import CostCollector

        engine = CostEngine(BrokerProfile.interactive_brokers())
        collector = CostCollector(engine=engine)
        assert collector.get_recent_slippage("EURUSD") == pytest.approx(0.3)

    def test_slippage_property_returns_float(self):
        """.slippage property provides default slippage value."""
        from quantlab.costs.collector import CostCollector

        collector = CostCollector()
        val = collector.slippage
        assert isinstance(val, float)
        assert val >= 0.0

    def test_slippage_property_matches_get_recent_slippage(self):
        """.slippage returns same as get_recent_slippage for default symbol."""
        from quantlab.costs.collector import CostCollector

        collector = CostCollector()
        assert collector.slippage == collector.get_recent_slippage("EURUSD")

    def test_hasattr_get_recent_slippage_true(self):
        """ExecutionGuardian hasattr check passes for get_recent_slippage."""
        from quantlab.costs.collector import CostCollector

        collector = CostCollector()
        assert hasattr(collector, "get_recent_slippage")

    def test_hasattr_slippage_true(self):
        """ExecutionGuardian hasattr check passes for slippage property."""
        from quantlab.costs.collector import CostCollector

        collector = CostCollector()
        assert hasattr(collector, "slippage")


class TestCostCollectorSpread:
    """CostCollector.spread_pips() — market spread."""

    def test_spread_pips_returns_float(self):
        """spread_pips returns current spread in pips."""
        from quantlab.costs.collector import CostCollector

        collector = CostCollector()
        spread = collector.spread_pips("EURUSD")
        assert isinstance(spread, float)
        assert spread >= 0.0

    def test_spread_pips_default_profile(self):
        """Without engine, spread_pips returns default_spread."""
        from quantlab.costs.collector import CostCollector

        collector = CostCollector()
        assert collector.spread_pips("EURUSD") == pytest.approx(1.5)

    def test_spread_pips_with_dukascopy_engine(self):
        """With Dukascopy engine, spread reflects profile."""
        from quantlab.costs.engine import CostEngine
        from quantlab.costs.profiles import BrokerProfile
        from quantlab.costs.collector import CostCollector

        engine = CostEngine(BrokerProfile.dukascopy())
        collector = CostCollector(engine=engine)
        # Dukascopy base spread 0.8 * London multiplier 1.0 = 0.8
        assert collector.spread_pips("EURUSD") == pytest.approx(0.8)

    def test_spread_pips_session_aware(self):
        """spread_pips accepts session parameter."""
        from quantlab.costs.engine import CostEngine
        from quantlab.costs.profiles import BrokerProfile
        from quantlab.costs.collector import CostCollector

        engine = CostEngine(BrokerProfile.dukascopy())
        collector = CostCollector(engine=engine)
        # NewYork multiplier 1.2 → 0.8 * 1.2 = 0.96
        assert collector.spread_pips("EURUSD", session="NewYork") == pytest.approx(0.96)


class TestCostCollectorCollectAll:
    """CostCollector.collect_all() — full collection for MarketGuardian."""

    def test_collect_all_returns_dict(self):
        """collect_all returns dict per symbol."""
        from quantlab.costs.collector import CostCollector

        collector = CostCollector()
        result = collector.collect_all(["EURUSD", "GBPUSD"])
        assert isinstance(result, dict)
        assert "EURUSD" in result
        assert "GBPUSD" in result

    def test_collect_all_includes_spread_pips(self):
        """Each entry has spread_pips accessible via dict key (market.py pattern)."""
        from quantlab.costs.collector import CostCollector

        collector = CostCollector()
        result = collector.collect_all(["EURUSD"])
        assert "spread_pips" in result["EURUSD"]

    def test_collect_all_includes_slippage_pips(self):
        """Each entry has slippage_pips key."""
        from quantlab.costs.collector import CostCollector

        collector = CostCollector()
        result = collector.collect_all(["EURUSD"])
        assert "slippage_pips" in result["EURUSD"]

    def test_collect_all_includes_session_info(self):
        """Each entry has session_name and session_score."""
        from quantlab.costs.collector import CostCollector

        collector = CostCollector()
        result = collector.collect_all(["EURUSD"])
        assert "session_name" in result["EURUSD"]
        assert "session_score" in result["EURUSD"]

    def test_collect_all_hasattr_compatible(self):
        """Returned dicts work with market.py's hasattr(spread_pips) check."""
        from quantlab.costs.collector import CostCollector

        collector = CostCollector()
        result = collector.collect_all(["EURUSD"])
        pair_data = result["EURUSD"]
        # market.py uses: hasattr(pair_data, 'spread_pips') or pair_data['spread_pips']
        assert isinstance(pair_data, dict)
        assert "spread_pips" in pair_data

    def test_collect_all_with_engine_reflects_profile(self):
        """With Dukascopy engine, collected values match profile."""
        from quantlab.costs.engine import CostEngine
        from quantlab.costs.profiles import BrokerProfile
        from quantlab.costs.collector import CostCollector

        engine = CostEngine(BrokerProfile.dukascopy())
        collector = CostCollector(engine=engine)
        result = collector.collect_all(["EURUSD"])
        assert result["EURUSD"]["spread_pips"] == pytest.approx(0.8)
        assert result["EURUSD"]["slippage_pips"] == pytest.approx(0.5)

    def test_collect_all_empty_list(self):
        """Empty symbols list returns empty dict (no crash)."""
        from quantlab.costs.collector import CostCollector

        collector = CostCollector()
        result = collector.collect_all([])
        assert result == {}

    def test_collect_all_ib_profile(self):
        """IB profile produces tighter spread and slippage."""
        from quantlab.costs.engine import CostEngine
        from quantlab.costs.profiles import BrokerProfile
        from quantlab.costs.collector import CostCollector

        engine = CostEngine(BrokerProfile.interactive_brokers())
        collector = CostCollector(engine=engine)
        result = collector.collect_all(["EURUSD"])
        assert result["EURUSD"]["spread_pips"] == pytest.approx(0.6)
        assert result["EURUSD"]["slippage_pips"] == pytest.approx(0.3)


class TestCostCollectorDefaults:
    """CostCollector default state when no broker profile is configured."""

    def test_no_engine_default_spread(self):
        """Without engine, spread_pips returns default (1.5)."""
        from quantlab.costs.collector import CostCollector

        collector = CostCollector()
        assert collector.spread_pips("EURUSD") == pytest.approx(1.5)

    def test_no_engine_default_slippage(self):
        """Without engine, get_recent_slippage returns conservative default."""
        from quantlab.costs.collector import CostCollector

        collector = CostCollector()
        slippage = collector.get_recent_slippage("EURUSD")
        assert slippage == pytest.approx(0.5)

    def test_no_engine_collect_all_still_works(self):
        """collect_all works without raising when no engine configured."""
        from quantlab.costs.collector import CostCollector

        collector = CostCollector()
        result = collector.collect_all(["EURUSD"])
        assert isinstance(result, dict)

    def test_custom_default_spread(self):
        """Custom default_spread parameter is respected."""
        from quantlab.costs.collector import CostCollector

        collector = CostCollector(default_spread=2.0)
        assert collector.spread_pips("EURUSD") == pytest.approx(2.0)

    def test_spread_pips_unknown_session_falls_back(self):
        """Unknown session returns unmodified spread."""
        from quantlab.costs.collector import CostCollector

        collector = CostCollector()
        # Without engine, session is ignored
        assert collector.spread_pips("EURUSD", session="Sydney") == pytest.approx(1.5)
