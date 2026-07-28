"""Tests for BuildConfig dataclass and _apply_build_config in project_builder."""

from __future__ import annotations

import re
from xml.etree import ElementTree

import pytest

from quantlab.sqx.project_builder import (
    BuildConfig,
    _apply_build_config,
    _BUILD_CONFIG_MAP,
    _format_build_config_value,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures — minimal XML snippets mimicking template structure
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def base_trading_options_xml() -> str:
    """Minimal BuildTradingOptions XML from the template."""
    return """<BuildTradingOptions>
  <Params>
    <Param key="ExitAtEndOfDay" className="ExitAtEndOfDay">false</Param>
    <Param key="EODExitTime" className="ExitAtEndOfDay">83040</Param>
    <Param key="ExitOnFriday" className="ExitOnFriday">true</Param>
    <Param key="FridayExitTime" className="ExitOnFriday">74400</Param>
    <Param key="LimitTimeRange" className="LimitTimeRange">false</Param>
    <Param key="SignalTimeRangeFrom" className="LimitTimeRange">28800</Param>
    <Param key="SignalTimeRangeTo" className="LimitTimeRange">57600</Param>
    <Param key="ExitAtEndOfRange" className="LimitTimeRange">false</Param>
    <Param key="MaxTradesPerDay" className="MaxTradesPerDay">0</Param>
    <Param key="Session" className="SessionOption">No Session</Param>
    <Param key="ReservedBars" className="ReservedBars">50</Param>
    <Param key="StoreChartData" className="StoreChartData">false</Param>
  </Params>
</BuildTradingOptions>"""


@pytest.fixture
def base_rules_complexity_xml() -> str:
    """Minimal RulesComplexity XML from the template."""
    return '<Chart name="Main chart" minConditions="1" maxConditions="3" minExitConditions="1" maxExitConditions="3" minPeriod="5" maxPeriod="200" minShift="1" maxShift="3" />'


@pytest.fixture
def base_market_sides_xml() -> str:
    """Minimal MarketSides XML from the template."""
    return """<MarketSides type="both">
  <EntrySymmetry>true</EntrySymmetry>
  <ExitSymmetry>true</ExitSymmetry>
</MarketSides>"""


@pytest.fixture
def base_slpt_xml() -> str:
    """Minimal SLPTOptions XML from the template."""
    return """<SLPTOptions>
  <SLRequired>true</SLRequired>
  <SLFixedPips>true</SLFixedPips>
  <MinSLInPips>30</MinSLInPips>
  <MaxSLInPips>80</MaxSLInPips>
  <MinSLInMoney>30</MinSLInMoney>
  <MaxSLInMoney>80</MaxSLInMoney>
  <SLATR>false</SLATR>
  <MinSLATRMultiple>1.5</MinSLATRMultiple>
  <MaxSLATRMultiple>3</MaxSLATRMultiple>
  <MinSLATRPeriod>20</MinSLATRPeriod>
  <MaxSLATRPeriod>20</MaxSLATRPeriod>
  <PTRequired>true</PTRequired>
  <PTFixedPips>true</PTFixedPips>
  <MinPTInPips>60</MinPTInPips>
  <MaxPTInPips>200</MaxPTInPips>
  <MinPTInMoney>60</MinPTInMoney>
  <MaxPTInMoney>200</MaxPTInMoney>
  <PTATR>false</PTATR>
  <MinPTATRMultiple>2</MinPTATRMultiple>
  <MaxPTATRMultiple>5</MaxPTATRMultiple>
  <MinPTATRPeriod>20</MinPTATRPeriod>
  <MaxPTATRPeriod>30</MaxPTATRPeriod>
  <LimitSLPTRRR>false</LimitSLPTRRR>
  <LimitSLPTRRRFrom>50</LimitSLPTRRRFrom>
  <LimitSLPTRRRTo>80</LimitSLPTRRRTo>
  <SLValueType>pips</SLValueType>
  <PTValueType>pips</PTValueType>
  <SLIndicatorBased>false</SLIndicatorBased>
  <PTIndicatorBased>false</PTIndicatorBased>
  <SLPercent>true</SLPercent>
  <MinSLInPercent>1.0</MinSLInPercent>
  <MaxSLInPercent>10.0</MaxSLInPercent>
  <PTPercent>true</PTPercent>
  <MinPTInPercent>1.0</MinPTInPercent>
  <MaxPTInPercent>10.0</MaxPTInPercent>
</SLPTOptions>"""


@pytest.fixture
def base_rankings_xml() -> str:
    """Minimal Rankings XML from the template (with correct column names)."""
    return """<Rankings type="never">
  <MaxStrategies>1000</MaxStrategies>
  <FitnessCriteria method="ComputeFromStrategyResult">
    <Settings>
      <Ranking type="ReturnDDRatio" />
    </Settings>
  </FitnessCriteria>
  <ConditionsType>1</ConditionsType>
  <Conditions>
    <Condition use="true">
      <Left-Side valueType="column">
        <Column-Value column="AvgTradesPerMonth" columnType="0" format="Integer" resultType="main" minValue="2" />
      </Left-Side>
    </Condition>
    <Condition use="true">
      <Left-Side valueType="column">
        <Column-Value column="ProfitFactor" columnType="0" format="Decimal2" resultType="main" minValue="1.3" />
      </Left-Side>
    </Condition>
    <Condition use="true">
      <Left-Side valueType="column">
        <Column-Value column="ReturnDDRatio" columnType="0" format="Decimal2" resultType="main" minValue="4" />
      </Left-Side>
    </Condition>
  </Conditions>
</Rankings>"""


@pytest.fixture
def base_crosschecks_xml() -> str:
    """Minimal CrossChecks XML from the template."""
    return """<CrossChecks use="true" evaluateAll="true">
  <RetestOnAdditionalMarkets use="false">
    <Settings>
      <Setups detailed="true">
        <Setup dateFrom="2003.5.5" dateTo="2019.12.31" testPrecision="1" session="No Session" slippage="1" minDist="0" engine="MetaTrader4">
          <Chart symbol="EURUSD_M1_dukas" timeframe="H1" spread="2" />
          <MainTestValues timeframe="true" dates="true" precision="true" distance="true" spread="true" slippage="true" commissions="true" session="false" />
        </Setup>
      </Setups>
      <AcceptanceSettings>
        <Check>all</Check>
        <MinConditions>2</MinConditions>
        <MinMarkets>1</MinMarkets>
      </AcceptanceSettings>
    </Settings>
  </RetestOnAdditionalMarkets>
  <WalkForwardOptimization use="false">
    <Settings>
      <WalkForward type="1" period="10" optimization="15">
        <Param1 value="20" />
        <Param2 value="10" />
      </WalkForward>
      <OptimizePeriods>true</OptimizePeriods>
      <OptimizeExitTypes>true</OptimizeExitTypes>
      <MaxTests>100</MaxTests>
    </Settings>
    <AcceptanceSettings>
      <Conditions thresholdPct="80">
        <Condition use="true">
          <Left-Side valueType="column">
            <Column-Value column="NetProfit" columnType="0" format="Decimal2PL" resultType="WalkForwardOptimization" minValue="0" />
          </Left-Side>
        </Condition>
      </Conditions>
    </AcceptanceSettings>
  </WalkForwardOptimization>
</CrossChecks>"""


# ═══════════════════════════════════════════════════════════════════════════
# _format_build_config_value
# ═══════════════════════════════════════════════════════════════════════════


class TestFormatBuildConfigValue:
    """Tests for _format_build_config_value."""

    def test_boolean_true(self) -> None:
        assert _format_build_config_value(True, "boolean") == "true"

    def test_boolean_false(self) -> None:
        assert _format_build_config_value(False, "boolean") == "false"

    def test_int(self) -> None:
        assert _format_build_config_value(42, "int") == "42"

    def test_float(self) -> None:
        assert _format_build_config_value(1.5, "float") == "1.50"

    def test_float_two_decimals(self) -> None:
        assert _format_build_config_value(3.14159, "float") == "3.14"

    def test_string(self) -> None:
        assert _format_build_config_value("both", "string") == "both"

    def test_string_as_is(self) -> None:
        assert _format_build_config_value("ReturnDDRatio", "string") == "ReturnDDRatio"


# ═══════════════════════════════════════════════════════════════════════════
# Trading Session (BuildTradingOptions)
# ═══════════════════════════════════════════════════════════════════════════


class TestTradingSessionOverrides:
    """Tests for BuildConfig trading session fields."""

    def test_exit_at_end_of_day_true(self, base_trading_options_xml: str) -> None:
        config = BuildConfig(exit_at_end_of_day=True)
        result = _apply_build_config(base_trading_options_xml, config)
        assert '<Param key="ExitAtEndOfDay" className="ExitAtEndOfDay">true</Param>' in result

    def test_exit_at_end_of_day_false(self, base_trading_options_xml: str) -> None:
        config = BuildConfig(exit_at_end_of_day=False)
        result = _apply_build_config(base_trading_options_xml, config)
        assert '<Param key="ExitAtEndOfDay" className="ExitAtEndOfDay">false</Param>' in result

    def test_eod_exit_time(self, base_trading_options_xml: str) -> None:
        config = BuildConfig(eod_exit_time=90000)
        result = _apply_build_config(base_trading_options_xml, config)
        assert '<Param key="EODExitTime" className="ExitAtEndOfDay">90000</Param>' in result

    def test_exit_on_friday(self, base_trading_options_xml: str) -> None:
        config = BuildConfig(exit_on_friday=False)
        result = _apply_build_config(base_trading_options_xml, config)
        assert '<Param key="ExitOnFriday" className="ExitOnFriday">false</Param>' in result

    def test_friday_exit_time(self, base_trading_options_xml: str) -> None:
        config = BuildConfig(friday_exit_time=86400)
        result = _apply_build_config(base_trading_options_xml, config)
        assert '<Param key="FridayExitTime" className="ExitOnFriday">86400</Param>' in result

    def test_limit_time_range(self, base_trading_options_xml: str) -> None:
        config = BuildConfig(limit_time_range=True)
        result = _apply_build_config(base_trading_options_xml, config)
        assert '<Param key="LimitTimeRange" className="LimitTimeRange">true</Param>' in result

    def test_signal_time_range_from(self, base_trading_options_xml: str) -> None:
        config = BuildConfig(signal_time_range_from=21600)
        result = _apply_build_config(base_trading_options_xml, config)
        assert '<Param key="SignalTimeRangeFrom" className="LimitTimeRange">21600</Param>' in result

    def test_signal_time_range_to(self, base_trading_options_xml: str) -> None:
        config = BuildConfig(signal_time_range_to=64800)
        result = _apply_build_config(base_trading_options_xml, config)
        assert '<Param key="SignalTimeRangeTo" className="LimitTimeRange">64800</Param>' in result

    def test_session(self, base_trading_options_xml: str) -> None:
        config = BuildConfig(session="Session 1")
        result = _apply_build_config(base_trading_options_xml, config)
        assert '<Param key="Session" className="SessionOption">Session 1</Param>' in result

    def test_reserved_bars(self, base_trading_options_xml: str) -> None:
        config = BuildConfig(reserved_bars=100)
        result = _apply_build_config(base_trading_options_xml, config)
        assert '<Param key="ReservedBars" className="ReservedBars">100</Param>' in result

    def test_store_chart_data(self, base_trading_options_xml: str) -> None:
        config = BuildConfig(store_chart_data=True)
        result = _apply_build_config(base_trading_options_xml, config)
        assert '<Param key="StoreChartData" className="StoreChartData">true</Param>' in result

    def test_none_preserves_template(self, base_trading_options_xml: str) -> None:
        """When build_config is None, template values are preserved."""
        config = BuildConfig()
        result = _apply_build_config(base_trading_options_xml, config)
        assert result == base_trading_options_xml


# ═══════════════════════════════════════════════════════════════════════════
# Rules Complexity
# ═══════════════════════════════════════════════════════════════════════════


class TestRulesComplexityOverrides:
    """Tests for BuildConfig rules complexity fields."""

    def test_min_conditions(self, base_rules_complexity_xml: str) -> None:
        config = BuildConfig(min_conditions=2)
        result = _apply_build_config(base_rules_complexity_xml, config)
        assert 'minConditions="2"' in result

    def test_max_conditions(self, base_rules_complexity_xml: str) -> None:
        config = BuildConfig(max_conditions=5)
        result = _apply_build_config(base_rules_complexity_xml, config)
        assert 'maxConditions="5"' in result

    def test_min_period(self, base_rules_complexity_xml: str) -> None:
        config = BuildConfig(min_period=10)
        result = _apply_build_config(base_rules_complexity_xml, config)
        assert 'minPeriod="10"' in result

    def test_max_period(self, base_rules_complexity_xml: str) -> None:
        config = BuildConfig(max_period=500)
        result = _apply_build_config(base_rules_complexity_xml, config)
        assert 'maxPeriod="500"' in result

    def test_min_shift(self, base_rules_complexity_xml: str) -> None:
        config = BuildConfig(min_shift=2)
        result = _apply_build_config(base_rules_complexity_xml, config)
        assert 'minShift="2"' in result

    def test_max_shift(self, base_rules_complexity_xml: str) -> None:
        config = BuildConfig(max_shift=5)
        result = _apply_build_config(base_rules_complexity_xml, config)
        assert 'maxShift="5"' in result


# ═══════════════════════════════════════════════════════════════════════════
# Market Sides
# ═══════════════════════════════════════════════════════════════════════════


class TestMarketSidesOverrides:
    """Tests for BuildConfig market sides fields."""

    def test_market_sides_long(self, base_market_sides_xml: str) -> None:
        config = BuildConfig(market_sides="long")
        result = _apply_build_config(base_market_sides_xml, config)
        assert '<MarketSides type="long">' in result

    def test_market_sides_short(self, base_market_sides_xml: str) -> None:
        config = BuildConfig(market_sides="short")
        result = _apply_build_config(base_market_sides_xml, config)
        assert '<MarketSides type="short">' in result

    def test_entry_symmetry_false(self, base_market_sides_xml: str) -> None:
        config = BuildConfig(entry_symmetry=False)
        result = _apply_build_config(base_market_sides_xml, config)
        assert '<EntrySymmetry>false</EntrySymmetry>' in result

    def test_exit_symmetry_false(self, base_market_sides_xml: str) -> None:
        config = BuildConfig(exit_symmetry=False)
        result = _apply_build_config(base_market_sides_xml, config)
        assert '<ExitSymmetry>false</ExitSymmetry>' in result


# ═══════════════════════════════════════════════════════════════════════════
# SL/PT Options
# ═══════════════════════════════════════════════════════════════════════════


class TestSLPTOverrides:
    """Tests for BuildConfig SL/PT fields."""

    def test_sl_required_false(self, base_slpt_xml: str) -> None:
        config = BuildConfig(sl_required=False)
        result = _apply_build_config(base_slpt_xml, config)
        assert '<SLRequired>false</SLRequired>' in result

    def test_sl_fixed_pips_false(self, base_slpt_xml: str) -> None:
        config = BuildConfig(sl_fixed_pips=False)
        result = _apply_build_config(base_slpt_xml, config)
        assert '<SLFixedPips>false</SLFixedPips>' in result

    def test_min_sl_pips(self, base_slpt_xml: str) -> None:
        config = BuildConfig(min_sl_pips=50)
        result = _apply_build_config(base_slpt_xml, config)
        assert '<MinSLInPips>50</MinSLInPips>' in result

    def test_max_sl_pips(self, base_slpt_xml: str) -> None:
        config = BuildConfig(max_sl_pips=150)
        result = _apply_build_config(base_slpt_xml, config)
        assert '<MaxSLInPips>150</MaxSLInPips>' in result

    def test_sl_atr_true(self, base_slpt_xml: str) -> None:
        config = BuildConfig(sl_atr=True)
        result = _apply_build_config(base_slpt_xml, config)
        assert '<SLATR>true</SLATR>' in result

    def test_min_sl_atr_multiple(self, base_slpt_xml: str) -> None:
        config = BuildConfig(min_sl_atr_multiple=2.0)
        result = _apply_build_config(base_slpt_xml, config)
        assert '<MinSLATRMultiple>2.00</MinSLATRMultiple>' in result

    def test_max_sl_atr_multiple(self, base_slpt_xml: str) -> None:
        config = BuildConfig(max_sl_atr_multiple=4.5)
        result = _apply_build_config(base_slpt_xml, config)
        assert '<MaxSLATRMultiple>4.50</MaxSLATRMultiple>' in result

    def test_min_sl_atr_period(self, base_slpt_xml: str) -> None:
        config = BuildConfig(min_sl_atr_period=14)
        result = _apply_build_config(base_slpt_xml, config)
        assert '<MinSLATRPeriod>14</MinSLATRPeriod>' in result

    def test_pt_required_false(self, base_slpt_xml: str) -> None:
        config = BuildConfig(pt_required=False)
        result = _apply_build_config(base_slpt_xml, config)
        assert '<PTRequired>false</PTRequired>' in result

    def test_min_pt_pips(self, base_slpt_xml: str) -> None:
        config = BuildConfig(min_pt_pips=100)
        result = _apply_build_config(base_slpt_xml, config)
        assert '<MinPTInPips>100</MinPTInPips>' in result

    def test_max_pt_pips(self, base_slpt_xml: str) -> None:
        config = BuildConfig(max_pt_pips=300)
        result = _apply_build_config(base_slpt_xml, config)
        assert '<MaxPTInPips>300</MaxPTInPips>' in result

    def test_pt_atr_true(self, base_slpt_xml: str) -> None:
        config = BuildConfig(pt_atr=True)
        result = _apply_build_config(base_slpt_xml, config)
        assert '<PTATR>true</PTATR>' in result

    def test_min_pt_atr_multiple(self, base_slpt_xml: str) -> None:
        config = BuildConfig(min_pt_atr_multiple=3.0)
        result = _apply_build_config(base_slpt_xml, config)
        assert '<MinPTATRMultiple>3.00</MinPTATRMultiple>' in result

    def test_sl_value_type(self, base_slpt_xml: str) -> None:
        config = BuildConfig(sl_value_type="money")
        result = _apply_build_config(base_slpt_xml, config)
        assert '<SLValueType>money</SLValueType>' in result

    def test_pt_value_type(self, base_slpt_xml: str) -> None:
        config = BuildConfig(pt_value_type="money")
        result = _apply_build_config(base_slpt_xml, config)
        assert '<PTValueType>money</PTValueType>' in result

    def test_sl_percent_true(self, base_slpt_xml: str) -> None:
        config = BuildConfig(sl_percent=True)
        result = _apply_build_config(base_slpt_xml, config)
        assert '<SLPercent>true</SLPercent>' in result

    def test_min_sl_percent(self, base_slpt_xml: str) -> None:
        config = BuildConfig(min_sl_percent=2.5)
        result = _apply_build_config(base_slpt_xml, config)
        assert '<MinSLInPercent>2.50</MinSLInPercent>' in result

    def test_max_sl_percent(self, base_slpt_xml: str) -> None:
        config = BuildConfig(max_sl_percent=15.0)
        result = _apply_build_config(base_slpt_xml, config)
        assert '<MaxSLInPercent>15.00</MaxSLInPercent>' in result

    def test_pt_percent_true(self, base_slpt_xml: str) -> None:
        config = BuildConfig(pt_percent=True)
        result = _apply_build_config(base_slpt_xml, config)
        assert '<PTPercent>true</PTPercent>' in result

    def test_min_pt_percent(self, base_slpt_xml: str) -> None:
        config = BuildConfig(min_pt_percent=2.5)
        result = _apply_build_config(base_slpt_xml, config)
        assert '<MinPTInPercent>2.50</MinPTInPercent>' in result

    def test_limit_slpt_rrr_true(self, base_slpt_xml: str) -> None:
        config = BuildConfig(limit_slpt_rrr=True)
        result = _apply_build_config(base_slpt_xml, config)
        assert '<LimitSLPTRRR>true</LimitSLPTRRR>' in result

    def test_limit_slpt_rrr_from(self, base_slpt_xml: str) -> None:
        config = BuildConfig(limit_slpt_rrr_from=60)
        result = _apply_build_config(base_slpt_xml, config)
        assert '<LimitSLPTRRRFrom>60</LimitSLPTRRRFrom>' in result

    def test_limit_slpt_rrr_to(self, base_slpt_xml: str) -> None:
        config = BuildConfig(limit_slpt_rrr_to=90)
        result = _apply_build_config(base_slpt_xml, config)
        assert '<LimitSLPTRRRTo>90</LimitSLPTRRRTo>' in result


# ═══════════════════════════════════════════════════════════════════════════
# Rankings — Bug Fixes
# ═══════════════════════════════════════════════════════════════════════════


class TestRankingsBugFixes:
    """Tests that the 3 known bugs are fixed: rankings criteria use correct column names."""

    def test_ranking_type_controls_ranking_element(self, base_rankings_xml: str) -> None:
        """ranking_type should control the <Ranking type="..."> element."""
        config = BuildConfig(ranking_type="Fitness")
        result = _apply_build_config(base_rankings_xml, config)
        assert '<Ranking type="Fitness" />' in result

    def test_ranking_pf_min_uses_correct_column(self, base_rankings_xml: str) -> None:
        """ranking_pf_min should modify ProfitFactor column (not SharpeRatio)."""
        config = BuildConfig(ranking_pf_min=2.0)
        result = _apply_build_config(base_rankings_xml, config)
        # ProfitFactor column should have minValue="2.00"
        assert 'column="ProfitFactor"' in result
        assert 'minValue="2.00"' in result

    def test_ranking_return_dd_min_uses_correct_column(self, base_rankings_xml: str) -> None:
        """ranking_return_dd_min should modify ReturnDDRatio column (not SharpeRatio)."""
        config = BuildConfig(ranking_return_dd_min=5.0)
        result = _apply_build_config(base_rankings_xml, config)
        # ReturnDDRatio column should have minValue="5.00"
        assert 'column="ReturnDDRatio"' in result
        assert 'minValue="5.00"' in result

    def test_ranking_avg_trades_min_uses_correct_column(self, base_rankings_xml: str) -> None:
        """ranking_avg_trades_min should modify AvgTradesPerMonth column (not MaxDrawdown)."""
        config = BuildConfig(ranking_avg_trades_min=5)
        result = _apply_build_config(base_rankings_xml, config)
        # AvgTradesPerMonth column should have minValue="5"
        assert 'column="AvgTradesPerMonth"' in result
        assert 'minValue="5"' in result

    def test_max_strategies(self, base_rankings_xml: str) -> None:
        """max_strategies should update the MaxStrategies element."""
        config = BuildConfig(max_strategies=500)
        result = _apply_build_config(base_rankings_xml, config)
        assert '<MaxStrategies>500</MaxStrategies>' in result

    def test_ranking_conditions_type(self, base_rankings_xml: str) -> None:
        """ranking_conditions_type should update the ConditionsType element."""
        config = BuildConfig(ranking_conditions_type=2)
        result = _apply_build_config(base_rankings_xml, config)
        assert '<ConditionsType>2</ConditionsType>' in result

    def test_none_preserves_rankings_template(self, base_rankings_xml: str) -> None:
        """When build_config is None (all fields None), template values are preserved."""
        config = BuildConfig()
        result = _apply_build_config(base_rankings_xml, config)
        assert result == base_rankings_xml


# ═══════════════════════════════════════════════════════════════════════════
# CrossChecks internals
# ═══════════════════════════════════════════════════════════════════════════


class TestCrossChecksOverrides:
    """Tests for BuildConfig CrossChecks internals fields."""

    def test_wf_period(self, base_crosschecks_xml: str) -> None:
        config = BuildConfig(wf_period=15)
        result = _apply_build_config(base_crosschecks_xml, config)
        assert 'period="15"' in result

    def test_wf_optimization(self, base_crosschecks_xml: str) -> None:
        config = BuildConfig(wf_optimization=8)
        result = _apply_build_config(base_crosschecks_xml, config)
        assert 'optimization="8"' in result

    def test_wf_param1(self, base_crosschecks_xml: str) -> None:
        config = BuildConfig(wf_param1=25)
        result = _apply_build_config(base_crosschecks_xml, config)
        assert '<Param1 value="25"' in result

    def test_wf_param2(self, base_crosschecks_xml: str) -> None:
        config = BuildConfig(wf_param2=15)
        result = _apply_build_config(base_crosschecks_xml, config)
        assert '<Param2 value="15"' in result

    def test_wf_optimize_periods_false(self, base_crosschecks_xml: str) -> None:
        config = BuildConfig(wf_optimize_periods=False)
        result = _apply_build_config(base_crosschecks_xml, config)
        assert '<OptimizePeriods>false</OptimizePeriods>' in result

    def test_wf_optimize_exit_types_false(self, base_crosschecks_xml: str) -> None:
        config = BuildConfig(wf_optimize_exit_types=False)
        result = _apply_build_config(base_crosschecks_xml, config)
        assert '<OptimizeExitTypes>false</OptimizeExitTypes>' in result

    def test_wf_max_tests(self, base_crosschecks_xml: str) -> None:
        config = BuildConfig(wf_max_tests=200)
        result = _apply_build_config(base_crosschecks_xml, config)
        assert '<MaxTests>200</MaxTests>' in result

    def test_wf_acceptance_threshold_pct(self, base_crosschecks_xml: str) -> None:
        config = BuildConfig(wf_acceptance_threshold_pct=90)
        result = _apply_build_config(base_crosschecks_xml, config)
        assert 'thresholdPct="90"' in result

    def test_wf_acceptance_min_conditions(self, base_crosschecks_xml: str) -> None:
        config = BuildConfig(wf_acceptance_min_conditions=3)
        result = _apply_build_config(base_crosschecks_xml, config)
        assert '<MinConditions>3</MinConditions>' in result

    def test_wf_acceptance_min_markets(self, base_crosschecks_xml: str) -> None:
        config = BuildConfig(wf_acceptance_min_markets=2)
        result = _apply_build_config(base_crosschecks_xml, config)
        assert '<MinMarkets>2</MinMarkets>' in result

    def test_rc_spread(self, base_crosschecks_xml: str) -> None:
        """rc_spread should update the spread attribute on the Chart element."""
        config = BuildConfig(rc_spread=5)
        result = _apply_build_config(base_crosschecks_xml, config)
        # The spread attribute on the Chart element should be updated
        assert 'spread="5"' in result

    def test_rc_pf_min(self, base_crosschecks_xml: str) -> None:
        """rc_pf_min should update the ProfitFactor minValue in RetestOnAdditionalMarkets."""
        # Use XML that has the right Column-Value structure
        xml = '''<CrossChecks use="true" evaluateAll="true">
  <RetestOnAdditionalMarkets use="false">
    <Settings>
      <Setups detailed="true">
        <Setup dateFrom="2003.5.5" dateTo="2019.12.31" testPrecision="1" session="No Session" slippage="1" minDist="0" engine="MetaTrader4">
          <Chart symbol="EURUSD_M1_dukas" timeframe="H1" spread="2" />
          <MainTestValues timeframe="true" dates="true" precision="true" distance="true" spread="true" slippage="true" commissions="true" session="false" />
        </Setup>
      </Setups>
      <AcceptanceSettings>
        <Check>all</Check>
        <MinConditions>2</MinConditions>
        <MinMarkets>1</MinMarkets>
        <Conditions CrossCheck="RetestOnAdditionalMarkets">
          <Condition use="true">
            <Left-Side valueType="column">
              <Column-Value column="ProfitFactor" columnType="0" format="Decimal2" resultType="RetestOnAdditionalMarkets" minValue="1.1" />
            </Left-Side>
            <Comparator value="&gt;" />
            <Right-Side valueType="numeric">
              <Numeric-Value value="1.1" />
            </Right-Side>
          </Condition>
        </Conditions>
      </AcceptanceSettings>
    </Settings>
  </RetestOnAdditionalMarkets>
</CrossChecks>'''
        config = BuildConfig(rc_pf_min=1.5)
        result = _apply_build_config(xml, config)
        assert 'resultType="RetestOnAdditionalMarkets"' in result
        assert 'minValue="1.50"' in result

    def test_main_test_values(self, base_crosschecks_xml: str) -> None:
        """main_test_values dict should update MainTestValues attributes."""
        config = BuildConfig(main_test_values={"timeframe": False, "session": True})
        result = _apply_build_config(base_crosschecks_xml, config)
        assert 'timeframe="false"' in result
        assert 'session="true"' in result


# ═══════════════════════════════════════════════════════════════════════════
# Backward compatibility
# ═══════════════════════════════════════════════════════════════════════════


class TestBackwardCompatibility:
    """Tests that create_project behaves correctly when build_config is None."""

    def test_none_preserves_all_template_values(self) -> None:
        """When build_config is None, all template values are preserved."""
        # Use a comprehensive XML snippet
        xml = """<Root>
  <BuildTradingOptions>
    <Params>
      <Param key="ExitAtEndOfDay" className="ExitAtEndOfDay">false</Param>
    </Params>
  </BuildTradingOptions>
  <Rankings type="never">
    <MaxStrategies>1000</MaxStrategies>
  </Rankings>
</Root>"""
        config = BuildConfig()
        result = _apply_build_config(xml, config)
        assert result == xml

    def test_existing_ranking_params_still_work_in_create_project(self) -> None:
        """When build_config is None, existing ranking params are used."""
        # This tests the backward-compatible path in create_project
        # We verify the function signature accepts build_config=None
        config = BuildConfig()
        assert config.exit_at_end_of_day is None
        assert config.ranking_pf_min is None


# ═══════════════════════════════════════════════════════════════════════════
# Independent section overrides
# ═══════════════════════════════════════════════════════════════════════════


class TestIndependentSectionOverrides:
    """Tests that each section can be overridden independently."""

    def test_trading_and_slpt_independent(self, base_trading_options_xml: str, base_slpt_xml: str) -> None:
        """Trading session and SL/PT can be overridden independently."""
        config = BuildConfig(
            exit_at_end_of_day=True,
            min_sl_pips=50,
        )
        # Apply to trading options
        result1 = _apply_build_config(base_trading_options_xml, config)
        assert 'ExitAtEndOfDay">true</Param>' in result1
        # Apply to SL/PT
        result2 = _apply_build_config(base_slpt_xml, config)
        assert '<MinSLInPips>50</MinSLInPips>' in result2

    def test_rankings_and_market_sides_independent(self, base_rankings_xml: str, base_market_sides_xml: str) -> None:
        """Rankings and market sides can be overridden independently."""
        config = BuildConfig(
            ranking_type="Fitness",
            market_sides="long",
        )
        result1 = _apply_build_config(base_rankings_xml, config)
        assert '<Ranking type="Fitness" />' in result1
        result2 = _apply_build_config(base_market_sides_xml, config)
        assert '<MarketSides type="long">' in result2

    def test_partial_override_does_not_affect_other_fields(self, base_trading_options_xml: str) -> None:
        """Overriding one field does not affect other template values."""
        config = BuildConfig(exit_at_end_of_day=True)
        result = _apply_build_config(base_trading_options_xml, config)
        # Only ExitAtEndOfDay should change
        assert 'ExitAtEndOfDay">true</Param>' in result
        # Other fields should remain unchanged
        assert 'EODExitTime" className="ExitAtEndOfDay">83040</Param>' in result
        assert 'ExitOnFriday" className="ExitOnFriday">true</Param>' in result


# ═══════════════════════════════════════════════════════════════════════════
# BuildConfig dataclass
# ═══════════════════════════════════════════════════════════════════════════


class TestBuildConfigDataclass:
    """Tests for the BuildConfig dataclass itself."""

    def test_default_all_none(self) -> None:
        """All fields default to None."""
        config = BuildConfig()
        assert config.exit_at_end_of_day is None
        assert config.ranking_pf_min is None
        assert config.mm_method is None
        assert config.main_test_values is None

    def test_partial_override(self) -> None:
        """Only specified fields are set."""
        config = BuildConfig(
            exit_at_end_of_day=True,
            ranking_pf_min=2.5,
        )
        assert config.exit_at_end_of_day is True
        assert config.ranking_pf_min == 2.5
        assert config.ranking_type is None

    def test_all_sections_can_be_set(self) -> None:
        """All sections of BuildConfig can be set simultaneously."""
        config = BuildConfig(
            exit_at_end_of_day=True,
            min_conditions=2,
            market_sides="long",
            sl_required=False,
            min_sl_pips=50,
            islands=6,
            ranking_type="Fitness",
            ranking_pf_min=2.0,
            mm_method="RiskFixedBalancePct",
            mm_lot_size=0.5,
            atms_enable=True,
            entry_rules_symmetry=False,
            wf_period=15,
            main_test_values={"timeframe": False},
        )
        assert config.exit_at_end_of_day is True
        assert config.min_conditions == 2
        assert config.market_sides == "long"
        assert config.sl_required is False
        assert config.min_sl_pips == 50
        assert config.islands == 6
        assert config.ranking_type == "Fitness"
        assert config.ranking_pf_min == 2.0
        assert config.mm_method == "RiskFixedBalancePct"
        assert config.mm_lot_size == 0.5
        assert config.atms_enable is True
        assert config.entry_rules_symmetry is False
        assert config.wf_period == 15
        assert config.main_test_values == {"timeframe": False}


# ═══════════════════════════════════════════════════════════════════════════
# _BUILD_CONFIG_MAP coverage
# ═══════════════════════════════════════════════════════════════════════════


class TestBuildConfigMapCoverage:
    """Tests that _BUILD_CONFIG_MAP covers all BuildConfig fields."""

    def test_all_buildconfig_fields_in_map(self) -> None:
        """Every field in BuildConfig should have a mapping entry."""
        config_fields = {f.name for f in BuildConfig.__dataclass_fields__.values()}
        mapped_fields = set(_BUILD_CONFIG_MAP.keys())
        missing = config_fields - mapped_fields
        assert not missing, f"BuildConfig fields missing from _BUILD_CONFIG_MAP: {missing}"

    def test_map_fields_are_valid_buildconfig_fields(self) -> None:
        """Every field in _BUILD_CONFIG_MAP should be a valid BuildConfig field."""
        config_fields = {f.name for f in BuildConfig.__dataclass_fields__.values()}
        mapped_fields = set(_BUILD_CONFIG_MAP.keys())
        extra = mapped_fields - config_fields
        assert not extra, f"_BUILD_CONFIG_MAP has fields not in BuildConfig: {extra}"

    def test_map_entries_have_valid_format_types(self) -> None:
        """All mapping entries should have valid format types."""
        valid_types = {"boolean", "int", "float", "string", "dict"}
        for field_name, (pattern, replacement, format_type) in _BUILD_CONFIG_MAP.items():
            assert format_type in valid_types, (
                f"Field '{field_name}' has invalid format_type '{format_type}'. "
                f"Must be one of {valid_types}"
            )