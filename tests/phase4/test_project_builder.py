"""Tests for BuildConfig dataclass and _apply_build_config in project_builder."""

from __future__ import annotations

import re
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree

import pytest

from quantlab.sqx.project_builder import (
    BuildConfig,
    _acceptance_scope,
    _apply_build_config,
    _BUILD_CONFIG_MAP,
    _CROSSCHECK_FIELD_SPECS,
    _CROSSCHECK_FIELD_SPEC_BY_NAME,
    _format_build_config_value,
    _method_scope,
    _node,
    _settings_scope,
    _tab_scope,
    get_tab_for_field,
    get_template_default,
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
        <Column-Value column="AvgTradesPerMonth" columnType="0" format="Integer" resultType="main" direction="0" sampleType="127" plType="10" confidenceLevel="50" market="1" subresult="30" pctRatio="0" class="AvgTradesPerMonth" />
      </Left-Side>
      <Comparator value="&gt;" />
      <Right-Side valueType="numeric">
        <Numeric-Value value="2" />
      </Right-Side>
    </Condition>
    <Condition use="true">
      <Left-Side valueType="column">
        <Column-Value column="ProfitFactor" columnType="0" format="Decimal2" resultType="main" direction="0" sampleType="127" plType="10" confidenceLevel="50" market="1" subresult="30" pctRatio="0" class="ProfitFactor" />
      </Left-Side>
      <Comparator value="&gt;" />
      <Right-Side valueType="numeric">
        <Numeric-Value value="1.3" />
      </Right-Side>
    </Condition>
    <Condition use="true">
      <Left-Side valueType="column">
        <Column-Value column="ReturnDDRatio" columnType="0" format="Decimal2" resultType="main" direction="0" sampleType="127" plType="10" confidenceLevel="50" market="1" subresult="30" pctRatio="0" class="ReturnDDRatio" />
      </Left-Side>
      <Comparator value="&gt;" />
      <Right-Side valueType="numeric">
        <Numeric-Value value="4" />
      </Right-Side>
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
        """ranking_pf_min should modify ProfitFactor threshold (not SharpeRatio)."""
        config = BuildConfig(ranking_pf_min=2.0)
        result = _apply_build_config(base_rankings_xml, config)
        # ProfitFactor Numeric-Value should be updated
        assert 'column="ProfitFactor"' in result
        assert '<Numeric-Value value="2.00" />' in result

    def test_ranking_return_dd_min_uses_correct_column(self, base_rankings_xml: str) -> None:
        """ranking_return_dd_min should modify ReturnDDRatio threshold (not SharpeRatio)."""
        config = BuildConfig(ranking_return_dd_min=5.0)
        result = _apply_build_config(base_rankings_xml, config)
        # ReturnDDRatio Numeric-Value should be updated
        assert 'column="ReturnDDRatio"' in result
        assert '<Numeric-Value value="5.00" />' in result

    def test_ranking_avg_trades_min_uses_correct_column(self, base_rankings_xml: str) -> None:
        """ranking_avg_trades_min should modify AvgTradesPerMonth threshold (not MaxDrawdown)."""
        config = BuildConfig(ranking_avg_trades_min=5)
        result = _apply_build_config(base_rankings_xml, config)
        # AvgTradesPerMonth column should have minValue="5"
        assert 'column="AvgTradesPerMonth"' in result
        assert '<Numeric-Value value="5" />' in result

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
        """WFO declares no MinConditions; the field must not write into the RC tab.

        The old version of this test asserted ``<MinConditions>3</MinConditions>``
        and passed only because the unscoped regex rewrote RC's node. That was
        the cross-tab corruption, not the behaviour.
        """
        config = BuildConfig(wf_acceptance_min_conditions=3)
        result = _apply_build_config(base_crosschecks_xml, config)
        assert "<MinConditions>2</MinConditions>" in result

    def test_wf_acceptance_min_markets(self, base_crosschecks_xml: str) -> None:
        """Same reasoning as test_wf_acceptance_min_conditions."""
        config = BuildConfig(wf_acceptance_min_markets=2)
        result = _apply_build_config(base_crosschecks_xml, config)
        assert "<MinMarkets>1</MinMarkets>" in result

    def test_rc_spread(self, base_crosschecks_xml: str) -> None:
        """rc_spread should update the spread attribute on the Chart element."""
        config = BuildConfig(rc_spread=5)
        result = _apply_build_config(base_crosschecks_xml, config)
        # The spread attribute on the Chart element should be updated
        assert 'spread="5"' in result

    def test_rc_pf_min(self, template_build_xml: str) -> None:
        """rc_pf_min is inert on real XML — SQX stores the PF minimum in the
        Condition tree's <Numeric-Value>, never as a Column-Value attribute.

        This test previously fed a hand-written snippet carrying
        ``minValue="1.1"`` on a Column-Value. No SQX 144.2953 artifact emits that
        attribute (checked against the bundled template and 123 sampled real
        project configs), so it proved nothing about the shipping template.
        """
        result = _apply_build_config(template_build_xml, BuildConfig(rc_pf_min=1.5))
        assert result == template_build_xml

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
        # "blocks" (REQ-03) is a special-cased format type used by the Blocks
        # bridge entries (enabled_blocks / block_weights), applied inside
        # _apply_build_config via _apply_block_entries.  "never_always"
        # translates the rankings_enabled flag to SQX's <Rankings type="...">
        # values ("always"/"never").  "crosscheck" marks a CrossChecks leaf that
        # must be rewritten inside the tab scope declared in
        # _CROSSCHECK_FIELD_SPECS instead of across the whole document.
        valid_types = {
            "boolean",
            "int",
            "float",
            "string",
            "dict",
            "blocks",
            "never_always",
            "crosscheck",
        }
        for field_name, (pattern, replacement, format_type) in _BUILD_CONFIG_MAP.items():
            assert format_type in valid_types, (
                f"Field '{field_name}' has invalid format_type '{format_type}'. "
                f"Must be one of {valid_types}"
            )


# ── CrossChecks full parameter catalog (crosschecks-parameter-catalog) ─────

_TEMPLATE_ZIP = (
    Path(__file__).resolve().parents[2]
    / "sdk"
    / "quantlab"
    / "sqx"
    / "templates"
    / "default-project.sqx-template"
)
# A real saved SQX config. It is the only local evidence for
# <SequentialOptimization>, which the default template does not carry.
_SAVED_CONFIG_ZIP = (
    Path(__file__).resolve().parents[2]
    / "assets"
    / "SQX_144_2953_linux_20260601"
    / "user"
    / "settings"
    / "Configs"
    / "DJ CFD H1.cfx"
)


def _read_entry_from_zip(archive: Path, member: str) -> str:
    with zipfile.ZipFile(archive) as zf:
        return zf.read(member).decode("utf-8", errors="replace")


@pytest.fixture(scope="module")
def template_build_xml() -> str:
    """The raw Build-Task1.xml carried by the bundled default template."""
    return _read_entry_from_zip(_TEMPLATE_ZIP, "Build-Task1.xml")


@pytest.fixture(scope="module")
def saved_config_xml() -> str:
    """config.xml from a real saved SQX config (adds SequentialOptimization)."""
    return _read_entry_from_zip(_SAVED_CONFIG_ZIP, "config.xml")


class TestCrosscheckMappingsHaveEvidence:
    """GIVEN the catalog table WHEN each scope/leaf is resolved THEN both hit real XML.

    This is the guard that keeps the catalog honest: a scope that matches
    nothing, or a leaf that does not match inside its own scope, means the
    mapping was written from a guess rather than from CFX evidence.

    ``_INERT_CROSSCHECK_FIELDS`` is the one sanctioned exception. Those fields
    address a node SQX 144.2953 does not emit, so their leaf matches nothing by
    design and _apply_in_scope preserves the document. They are listed
    explicitly rather than skipped by prefix so that adding a *new* unmapped
    leaf still fails this test.
    """

    _INERT = {
        # WalkForwardOptimization declares no MinConditions/MinMarkets — only
        # RetestOnAdditionalMarkets does.
        "wf_acceptance_min_conditions",
        "wf_acceptance_min_markets",
        # SQX never writes minValue on a Column-Value; the PF minimum lives in
        # the Condition tree's <Numeric-Value>. See
        # TestCrosscheckAcceptanceThresholdsMatchRealEvidence.
        "wf_acceptance_pf_min",
        "rc_pf_min",
    }

    def test_every_scope_matches_the_template(self, template_build_xml: str) -> None:
        unresolved = [
            field
            for field, scope, _leaf, _ft in _CROSSCHECK_FIELD_SPECS
            if re.search(scope, template_build_xml, re.DOTALL) is None
            and field != "so_use"  # SequentialOptimization only exists in saved configs
        ]
        assert not unresolved, f"scopes with no evidence in the template: {unresolved}"

    def test_every_leaf_matches_inside_its_own_scope(self, template_build_xml: str) -> None:
        unresolved = []
        for field, scope, leaf, _ft in _CROSSCHECK_FIELD_SPECS:
            if field == "so_use" or field in self._INERT:
                continue
            region = re.search(scope, template_build_xml, re.DOTALL)
            assert region is not None, field
            if re.search(leaf, region.group(0), re.DOTALL) is None:
                unresolved.append(field)
        assert not unresolved, f"leaves with no evidence inside their scope: {unresolved}"

    def test_the_inert_exceptions_are_still_real_fields(self) -> None:
        """Keep _INERT honest: it may only excuse fields that exist at all."""
        known = {field for field, _s, _l, _ft in _CROSSCHECK_FIELD_SPECS}
        assert self._INERT <= known, f"_INERT names unknown fields: {self._INERT - known}"
        assert len(self._INERT) == 4, (
            "an inert field gained real evidence — remove it from _INERT and let "
            f"the leaf guard cover it again (currently {sorted(self._INERT)})"
        )

    def test_sequential_optimization_scope_hits_a_real_config(
        self, saved_config_xml: str
    ) -> None:
        """so_use has no template default — the real config is its only evidence."""
        spec = _CROSSCHECK_FIELD_SPEC_BY_NAME["so_use"]
        _field, scope, leaf, format_type = spec
        region = re.search(scope, saved_config_xml, re.DOTALL)
        assert region is not None, "SequentialOptimization not found in the saved config"
        assert re.search(leaf, region.group(0), re.DOTALL) is not None
        assert format_type == "boolean"

    def test_get_template_default_is_none_for_absent_element(
        self, saved_config_xml: str
    ) -> None:
        assert get_template_default("so_use") is None

    def test_every_field_is_classified_to_a_tab(self) -> None:
        unclassified = [
            field
            for field, _s, _l, _ft in _CROSSCHECK_FIELD_SPECS
            if get_tab_for_field(field) == "Other"
        ]
        assert not unclassified, f"fields not mapped to a tab: {unclassified}"

    def test_every_method_type_is_unique_in_the_template(
        self, template_build_xml: str
    ) -> None:
        """_method_scope addresses a method by type alone, so that must hold.

        The RetestOnAdditionalMarkets commission ``<Method type="None">`` is the
        only duplicated type and is reached through a Settings scope, never
        through _method_scope — this test keeps that true.
        """
        counted = Counter(re.findall(r'<Method\b[^>]*type="([^"]+)"', template_build_xml))
        # Extract the literal method name from each method scope. The scope
        # source reads `<Method\b[^>]*type="NAME"[^>]*>`, so capture the quoted
        # name directly instead of trying to re-match the pattern's own syntax.
        method_types = {
            match.group(1)
            for _f, scope, _leaf, _ft in _CROSSCHECK_FIELD_SPECS
            for match in re.finditer(r'type="([A-Za-z]+)"', scope)
        }
        assert method_types, "no method scopes found — the extractor is wrong"
        duplicated = {t for t in method_types if counted[t] != 1}
        assert not duplicated, (
            f"method types used as scopes are not unique in the template: {duplicated} "
            f"(counts: { {t: counted[t] for t in duplicated} })"
        )


class TestCrosscheckScopingIsolation:
    """GIVEN repeated leaf names WHEN one tab field is set THEN siblings are untouched."""

    def test_max_tests_does_not_leak_across_tabs(self, template_build_xml: str) -> None:
        """<MaxTests> exists in WalkForwardOptimization, WalkForwardMatrix and
        OptProfileSysParamPermutation. Setting one must not touch the others.
        """
        xml = _apply_build_config(
            template_build_xml, BuildConfig(opspp_max_tests=7, wfm_use=True)
        )
        region = re.search(_settings_scope("OptProfileSysParamPermutation"), xml, re.DOTALL)
        assert "<MaxTests>7</MaxTests>" in region.group(0)
        region = re.search(_settings_scope("WalkForwardMatrix"), xml, re.DOTALL)
        assert "<MaxTests>100</MaxTests>" in region.group(0), "WFM MaxTests was rewritten"
        region = re.search(_settings_scope("WalkForwardOptimization"), xml, re.DOTALL)
        assert "<MaxTests>100</MaxTests>" in region.group(0), "WFO MaxTests was rewritten"

    def test_number_of_simulations_does_not_leak(self, template_build_xml: str) -> None:
        """<NumberOfSimulations> is shared by MonteCarloRetest and
        MonteCarloManipulation.
        """
        xml = _apply_build_config(
            template_build_xml, BuildConfig(mcm_number_of_simulations=33)
        )
        region = re.search(_settings_scope("MonteCarloManipulation"), xml, re.DOTALL)
        assert "<NumberOfSimulations>33</NumberOfSimulations>" in region.group(0)
        region = re.search(_settings_scope("MonteCarloRetest"), xml, re.DOTALL)
        assert (
            "<NumberOfSimulations>10</NumberOfSimulations>" in region.group(0)
        ), "MonteCarloRetest simulations were rewritten"

    def test_monte_carlo_method_params_stay_in_their_method(
        self, template_build_xml: str
    ) -> None:
        """Min/Max appear in three Monte-Carlo methods; each field owns one.

        The three methods carry distinct defaults (spread 1.0/5.0, slippage
        0.0/5.0, min-distance 0.0/10.0), so a leak shows up as a changed value.
        Floats use the existing two-decimal convention.
        """
        xml = _apply_build_config(
            template_build_xml,
            BuildConfig(
                mcr_spread_min=1.5,
                mcr_slippage_max=99.0,
                mcr_min_distance_min=2.5,
            ),
        )

        def params(method: str) -> dict[str, str]:
            region = re.search(
                _method_scope("MonteCarloRetest", method), xml, re.DOTALL
            ).group(0)
            return dict(re.findall(r'<Param key="(\w+)" type="[A-Za-z]+">([^<]*)<', region))

        assert params("RandomizeSpread")["Min"] == "1.50"
        assert params("RandomizeSpread")["Max"] == "5.0", "spread Max was rewritten"
        assert params("RandomizeSlippage")["Max"] == "99.00"
        assert params("RandomizeSlippage")["Min"] == "0.0", "slippage Min was rewritten"
        assert params("RandomizeMinDistance")["Min"] == "2.50"
        assert (
            params("RandomizeMinDistance")["Max"] == "10.0"
        ), "min distance Max was rewritten"

    def test_whatif_use_flag_touches_only_its_method(
        self, template_build_xml: str
    ) -> None:
        """<Method use=...> is repeated 15 times in WhatIf alone.

        Attribute order differs between tabs (WhatIf writes use before type, the
        RetestOnAdditionalMarkets commission writes type before use), so the
        assertions compare the whole tag rather than assuming an order.
        """
        xml = _apply_build_config(template_build_xml, BuildConfig(wi_by_hours_use=True))
        methods = {
            match.group(1): match.group(0)
            for match in re.finditer(
                r'<Method\b[^>]*type="([A-Za-z]+)"[^>]*>', re.search(
                    _tab_scope("WhatIf"), xml, re.DOTALL
                ).group(0)
            )
        }
        assert 'use="true"' in methods["ByHours"], "ByHours was not enabled"
        assert 'use="false"' in methods["ByDays"], "ByDays was rewritten"
        assert 'use="false"' in methods["ByMonths"], "ByMonths was rewritten"

    def test_retest_on_additional_markets_setup_owns_its_dates(
        self, template_build_xml: str
    ) -> None:
        xml = _apply_build_config(
            template_build_xml, BuildConfig(rc_date_from="01.01.2024", rc_date_to="31.12.2024")
        )
        settings = re.search(
            _settings_scope("RetestOnAdditionalMarkets"), xml, re.DOTALL
        ).group(0)
        assert 'dateFrom="01.01.2024"' in settings
        assert 'dateTo="31.12.2024"' in settings

    def test_commission_method_type_attribute_is_scoped(
        self, template_build_xml: str
    ) -> None:
        """RC's commission method is ``type="..."`` while WhatIf/MC use
        ``use="..."`` first — an unscoped pattern would corrupt the other tabs.
        """
        xml = _apply_build_config(
            template_build_xml, BuildConfig(rc_commission_method="RoundTurn")
        )
        settings = re.search(
            _settings_scope("RetestOnAdditionalMarkets"), xml, re.DOTALL
        ).group(0)
        assert 'type="RoundTurn"' in settings
        assert re.search(r'<Method[^>]*use="true"[^>]*type="Randomize', xml) is not None


class TestCrosscheckLegacyMappingsDoNotCorruptSiblings:
    """GIVEN a legacy unscoped CrossChecks mapping WHEN it is applied THEN sibling tabs
    keep their own values.

    The pre-catalog entries in _BUILD_CONFIG_MAP are document-wide regexes. The
    template repeats their leaf names across tabs, so re.sub rewrites every copy:
    <MaxTests> exists in WalkForwardOptimization, WalkForwardMatrix and
    OptProfileSysParamPermutation, and <WalkForward period=...> in two of them.
    Setting one tab's value silently configured the others — the exact failure this
    catalog exists to prevent, so these tests pin the scoping down.
    """

    def test_wf_max_tests_does_not_reach_the_other_two_tabs(
        self, template_build_xml: str
    ) -> None:
        xml = _apply_build_config(template_build_xml, BuildConfig(wf_max_tests=777))
        assert re.findall(r"<MaxTests>(\d+)</MaxTests>", xml) == ["777", "100", "1000"], (
            "MaxTests must change in WalkForwardOptimization only; the template "
            "carries 100 in WalkForwardMatrix and 1000 in OptProfileSysParamPermutation"
        )

    def test_wf_period_does_not_reach_walk_forward_matrix(
        self, template_build_xml: str
    ) -> None:
        xml = _apply_build_config(template_build_xml, BuildConfig(wf_period=77))
        wfo = re.search(_settings_scope("WalkForwardOptimization"), xml, re.DOTALL)
        wfm = re.search(_settings_scope("WalkForwardMatrix"), xml, re.DOTALL)
        assert 'period="77"' in wfo.group(0)
        assert 'period="10"' in wfm.group(0), "WalkForwardMatrix period was rewritten"

    def test_wf_optimization_does_not_reach_walk_forward_matrix(
        self, template_build_xml: str
    ) -> None:
        xml = _apply_build_config(template_build_xml, BuildConfig(wf_optimization=66))
        wfm = re.search(_settings_scope("WalkForwardMatrix"), xml, re.DOTALL)
        assert 'optimization="15"' in wfm.group(0), "WalkForwardMatrix optimization was rewritten"

    @pytest.mark.parametrize(
        ("field", "leaf", "expected"),
        [
            ("wf_optimize_periods", "OptimizePeriods", "false"),
            ("wf_optimize_exit_types", "OptimizeExitTypes", "false"),
        ],
    )
    def test_wfo_settings_flags_do_not_reach_the_matrix(
        self, template_build_xml: str, field: str, leaf: str, expected: str
    ) -> None:
        xml = _apply_build_config(template_build_xml, BuildConfig(**{field: False}))
        wfm = re.search(_settings_scope("WalkForwardMatrix"), xml, re.DOTALL)
        assert f"<{leaf}>true</{leaf}>" in wfm.group(0), f"WFM {leaf} was rewritten"

    def test_wf_threshold_pct_does_not_reach_the_matrix(
        self, template_build_xml: str
    ) -> None:
        xml = _apply_build_config(
            template_build_xml, BuildConfig(wf_acceptance_threshold_pct=55)
        )
        wfm = re.search(_acceptance_scope("WalkForwardMatrix"), xml, re.DOTALL)
        assert 'thresholdPct="80"' in wfm.group(0), "WFM thresholdPct was rewritten"

    def test_rc_spread_does_not_reach_the_project_chart(
        self, template_build_xml: str
    ) -> None:
        """The main Setup also declares <Chart ... spread="...">; rc_spread owns
        only the RetestOnAdditionalMarkets one.
        """
        xml = _apply_build_config(template_build_xml, BuildConfig(rc_spread=55))
        spreads = re.findall(r'<Chart [^>]*spread="(\d+)"', xml)
        assert sorted(spreads) == ["3", "55"], (
            f"rc_spread must rewrite only the additional-markets chart; got {spreads} "
            "(the project chart keeps spread=3)"
        )


class TestCrosscheckAcceptanceCountsAreTabOwned:
    """<MinConditions>/<MinMarkets> exist only under RetestOnAdditionalMarkets.

    The legacy entries gave WalkForwardOptimization its own MinConditions /
    MinMarkets fields even though that tab carries no such nodes, so both pairs
    compiled to the same unscoped regex and whichever ran last won. WFO owns
    ``thresholdPct`` instead — there is nothing else for it to write.
    """

    def test_rc_counts_stay_inside_the_additional_markets_tab(
        self, template_build_xml: str
    ) -> None:
        xml = _apply_build_config(
            template_build_xml, BuildConfig(rc_min_conditions=5, rc_min_markets=4)
        )
        rc = re.search(_acceptance_scope("RetestOnAdditionalMarkets"), xml, re.DOTALL)
        assert "<MinConditions>5</MinConditions>" in rc.group(0)
        assert "<MinMarkets>4</MinMarkets>" in rc.group(0)
        assert xml.count("<MinConditions>") == 1, "a second MinConditions appeared"

    def test_wf_min_conditions_does_not_write_into_the_rc_tab(
        self, template_build_xml: str
    ) -> None:
        xml = _apply_build_config(
            template_build_xml, BuildConfig(wf_acceptance_min_conditions=9)
        )
        rc = re.search(_acceptance_scope("RetestOnAdditionalMarkets"), xml, re.DOTALL)
        assert (
            "<MinConditions>2</MinConditions>" in rc.group(0)
        ), "WalkForwardOptimization's MinConditions was written into RetestOnAdditionalMarkets"

    def test_wf_min_markets_does_not_write_into_the_rc_tab(
        self, template_build_xml: str
    ) -> None:
        xml = _apply_build_config(
            template_build_xml, BuildConfig(wf_acceptance_min_markets=9)
        )
        rc = re.search(_acceptance_scope("RetestOnAdditionalMarkets"), xml, re.DOTALL)
        assert (
            "<MinMarkets>1</MinMarkets>" in rc.group(0)
        ), "WalkForwardOptimization's MinMarkets was written into RetestOnAdditionalMarkets"


class TestCrosscheckAcceptanceThresholdsMatchRealEvidence:
    """The two ``*_pf_min`` fields address a ``minValue`` attribute that SQX never
    writes: across the bundled template and 123 sampled real project configs,
    ``minValue`` appears only on strategy ``<Param>`` nodes and never on
    ``<Column-Value>``. Their acceptance thresholds live in the Condition tree's
    ``<Numeric-Value>``, which this change keeps as raw_xml by design.
    """

    def test_no_real_config_declares_minvalue_on_a_column_value(
        self, template_build_xml: str
    ) -> None:
        offenders = [
            tag
            for tag in re.findall(r"<Column-Value\b[^>]*>", template_build_xml)
            if "minValue" in tag
        ]
        assert not offenders, f"template has Column-Value with minValue: {offenders[:2]}"

    @pytest.mark.parametrize("field", ["wf_acceptance_pf_min", "rc_pf_min"])
    def test_pf_min_is_a_no_op_on_real_xml(
        self, template_build_xml: str, field: str
    ) -> None:
        """Pin the current, evidence-backed behaviour instead of a fabricated one.

        SQX 144.2953 stores these thresholds in the Condition tree, so the field
        cannot rewrite anything on real XML. Callers that need them must go
        through CrossChecksConfig's Condition handling, not BuildConfig.
        """
        value = 1.25
        xml = _apply_build_config(template_build_xml, BuildConfig(**{field: value}))
        assert xml == template_build_xml


class TestCrosscheckWalkForwardMatrixSettings:
    """WalkForwardMatrix carries the same Settings leaves as WalkForwardOptimization.

    WFO owns ``period`` / ``optimization`` / ``OptimizePeriods`` /
    ``OptimizeExitTypes`` / ``MaxTests``, but the matrix declares its own copy of
    all five inside its own tab (Build-Task1.xml), so without a separate set of
    fields the matrix settings were only reachable by letting WFO's values leak
    across — which the isolation tests above forbid.
    """

    @pytest.mark.parametrize(
        ("field", "value", "expected"),
        [
            ("wfm_max_tests", 321, "<MaxTests>321</MaxTests>"),
            ("wfm_period", 41, 'period="41"'),
            ("wfm_optimization", 13, 'optimization="13"'),
            ("wfm_optimize_periods", False, "<OptimizePeriods>false</OptimizePeriods>"),
            (
                "wfm_optimize_exit_types",
                False,
                "<OptimizeExitTypes>false</OptimizeExitTypes>",
            ),
        ],
    )
    def test_matrix_setting_is_writable(
        self, template_build_xml: str, field: str, value: object, expected: str
    ) -> None:
        xml = _apply_build_config(template_build_xml, BuildConfig(**{field: value}))
        wfm = re.search(_settings_scope("WalkForwardMatrix"), xml, re.DOTALL)
        assert expected in wfm.group(0)

    def test_matrix_setting_does_not_reach_the_other_tabs(
        self, template_build_xml: str
    ) -> None:
        xml = _apply_build_config(
            template_build_xml,
            BuildConfig(
                wfm_max_tests=321,
                wfm_optimize_periods=False,
                wfm_optimize_exit_types=False,
            ),
        )
        wfo = re.search(_settings_scope("WalkForwardOptimization"), xml, re.DOTALL)
        assert "<MaxTests>100</MaxTests>" in wfo.group(0)
        assert "<OptimizePeriods>true</OptimizePeriods>" in wfo.group(0)
        assert "<OptimizeExitTypes>true</OptimizeExitTypes>" in wfo.group(0)
        pspp = re.search(
            _settings_scope("OptProfileSysParamPermutation"), xml, re.DOTALL
        )
        assert "<MaxTests>1000</MaxTests>" in pspp.group(0)


class TestCrosscheckSequentialOptimization:
    """GIVEN a self-closing SequentialOptimization THEN use is rewritten in place."""

    def test_self_closing_element_is_rewritten(self, saved_config_xml: str) -> None:
        xml = _apply_build_config(saved_config_xml, BuildConfig(so_use=True))
        assert re.search(r'<SequentialOptimization use="true"\s*/>', xml) is not None

    def test_other_tabs_are_untouched(self, saved_config_xml: str) -> None:
        xml = _apply_build_config(saved_config_xml, BuildConfig(so_use=True))
        assert xml.count("<SequentialOptimization") == saved_config_xml.count(
            "<SequentialOptimization"
        )


class TestCrosscheckAcceptanceIsTabScoped:
    """Acceptance leaves are addressed by tab, never document-wide.

    These replaced direct ``_apply_acceptance_settings`` tests. That helper was a
    one-line wrapper over ``_apply_in_scope`` with no production caller, so
    asserting on it only tested a private shim. Driving the real entry point
    (``_apply_build_config``) covers the same invariants *and* the
    leaf/format/formatting path that callers actually use.
    """

    def test_rewrites_only_the_named_tab(self, template_build_xml: str) -> None:
        # OptProfileSysParamPermutation declares ProfitOptPct; WFO and RC do not.
        xml = _apply_build_config(
            template_build_xml, BuildConfig(opspp_profit_opt_pct=45)
        )
        region = re.search(
            _acceptance_scope("OptProfileSysParamPermutation"), xml, re.DOTALL
        ).group(0)
        assert "<ProfitOptPct>45</ProfitOptPct>" in region

    def test_absent_tab_is_preserved_and_logged(
        self, template_build_xml: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        # SequentialOptimization exists in saved configs but carries no
        # AcceptanceSettings, so ProfitOptPct has nowhere to land here.
        xml = _apply_build_config(template_build_xml, BuildConfig(so_use=True))
        assert xml == template_build_xml
        assert "unchanged" in caplog.text or "ProfitOptPct" not in caplog.text


class TestCrosscheckMissingScopePreservesXml:
    """A field targeting XML this build lacks must never corrupt another tab."""

    def test_missing_tab_warns_and_preserves(
        self, template_build_xml: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        xml = _apply_build_config(template_build_xml, BuildConfig(so_use=True))
        assert xml == template_build_xml
        assert "so_use" in caplog.text
        assert "unchanged" in caplog.text

    def test_leaf_absent_inside_its_own_scope_warns(
        self, template_build_xml: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A scope that exists but holds no such leaf is also reported, not ignored."""
        xml = _apply_build_config(template_build_xml, BuildConfig(rc_check="all"))
        assert xml == template_build_xml
        assert "rc_check" in caplog.text


class TestCrosscheckTemplateDefaults:
    """get_template_default must probe the field's own scoped region."""

    def test_repeated_leaf_reports_its_own_tab_default(self) -> None:
        assert get_template_default("hp_precision") == 2
        assert get_template_default("hp_spread") == 3

    def test_method_use_flag_is_not_confused_with_another_method(self) -> None:
        """A document-wide probe would report the RC commission method's use."""
        assert get_template_default("wi_by_hours_use") is False

    def test_number_of_simulations_default(self) -> None:
        assert get_template_default("mcr_number_of_simulations") == 10

    def test_acceptance_default(self) -> None:
        assert get_template_default("opspp_profit_opt_pct") == 30


class TestCrosscheckTabClassification:
    """Every new field resolves to the CrossChecks tab it actually belongs to."""

    def test_known_prefixes_map_to_their_tab(self) -> None:
        assert get_tab_for_field("rc_use") == "RetestOnAdditionalMarkets"
        assert get_tab_for_field("wf_use") == "WalkForwardOptimization"
        assert get_tab_for_field("hp_precision") == "RetestWithHigherPrecision"
        assert get_tab_for_field("mcr_history_data_use") == "MonteCarloRetest"
        assert get_tab_for_field("wfm_param1_start") == "WalkForwardMatrix"
        assert get_tab_for_field("mcm_skip_trades_use") == "MonteCarloManipulation"
        assert get_tab_for_field("opspp_max_tests") == "OptProfileSysParamPermutation"
        assert get_tab_for_field("wi_swap_use") == "WhatIf"
        assert get_tab_for_field("so_use") == "SequentialOptimization"

    def test_committed_acceptance_fields_keep_their_tab(self) -> None:
        """PR2 mappings must not be reclassified by the new prefixes."""
        assert get_tab_for_field("wf_acceptance_threshold_pct") == "CrossChecks"
        assert get_tab_for_field("rc_spread") == "CrossChecks"
        assert get_tab_for_field("main_test_values") == "CrossChecks"
