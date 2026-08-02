"""Build SQX project directories from DSL config using a clean template."""

from __future__ import annotations

import logging
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quantlab.costs.profiles import BrokerProfile

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_DEFAULT_TEMPLATE = _TEMPLATE_DIR / "default-project.sqx-template"

# Default JForex Dukascopy broker settings
_JFOREX_COMMISSION = 3.5       # USD per lot (standard Dukascopy)
_JFOREX_SLIPPAGE = 1           # pips
_JFOREX_SPREAD = 3             # pips base
_JFOREX_ENGINE = "MetaTrader4"  # Engine handles backtesting/generation, NOT data source.
                                  # Dukascopy data works fine with MetaTrader4 engine.

# Known max dates per symbol (from Dukascopy data availability as of 2024-10).
# date_to values beyond these cause silent generator failure.
_SYMBOL_MAX_DATES: dict[str, str] = {
    "EURUSD": "2024.10.30",
    "GBPUSD": "2024.10.30",
    "AUDUSD": "2024.10.30",
    "NZDUSD": "2024.10.30",
    "USDCAD": "2024.10.30",
    "USDCHF": "2024.10.30",
    "USDJPY": "2024.10.30",
    "XAUUSD": "2024.10.30",
    "XAGUSD": "2024.10.30",
}

_MAX_DATE_DEFAULT = "2024.6.30"  # conservative default with margin


def _clamp_date_to(symbol: str, requested: str) -> str:
    """Clamp date_to to the known max date for the symbol."""
    max_date = _SYMBOL_MAX_DATES.get(symbol.upper(), _MAX_DATE_DEFAULT)

    def _date_tuple(d: str) -> tuple[int, int, int]:
        parts = d.split(".")
        return int(parts[0]), int(parts[1]), int(parts[2])

    if _date_tuple(requested) > _date_tuple(max_date):
        return max_date
    return requested


def _template_path() -> Path:
    return _DEFAULT_TEMPLATE


@dataclass
class BuildConfig:
    """Configuration overrides for the SQX build template.

    Only specified (non-None) fields override the template defaults.
    Unspecified fields keep their template values.
    """

    # ── Trading Session (BuildTradingOptions) ──
    exit_at_end_of_day: bool | None = None
    eod_exit_time: int | None = None
    exit_on_friday: bool | None = None
    friday_exit_time: int | None = None
    limit_time_range: bool | None = None
    signal_time_range_from: int | None = None
    signal_time_range_to: int | None = None
    exit_at_end_of_range: bool | None = None
    max_trades_per_day: int | None = None
    session: str | None = None
    reserved_bars: int | None = None
    store_chart_data: bool | None = None

    # ── Rules Complexity ──
    min_conditions: int | None = None
    max_conditions: int | None = None
    min_exit_conditions: int | None = None
    max_exit_conditions: int | None = None
    min_period: int | None = None
    max_period: int | None = None
    min_shift: int | None = None
    max_shift: int | None = None

    # ── Market Sides ──
    market_sides: str | None = None  # "both", "long", "short"
    entry_symmetry: bool | None = None
    exit_symmetry: bool | None = None

    # ── SL/PT Options ──
    sl_required: bool | None = None
    sl_fixed_pips: bool | None = None
    min_sl_pips: int | None = None
    max_sl_pips: int | None = None
    min_sl_money: int | None = None
    max_sl_money: int | None = None
    sl_atr: bool | None = None
    min_sl_atr_multiple: float | None = None
    max_sl_atr_multiple: float | None = None
    min_sl_atr_period: int | None = None
    max_sl_atr_period: int | None = None
    pt_required: bool | None = None
    pt_fixed_pips: bool | None = None
    min_pt_pips: int | None = None
    max_pt_pips: int | None = None
    min_pt_money: int | None = None
    max_pt_money: int | None = None
    pt_atr: bool | None = None
    min_pt_atr_multiple: float | None = None
    max_pt_atr_multiple: float | None = None
    min_pt_atr_period: int | None = None
    max_pt_atr_period: int | None = None
    limit_slpt_rrr: bool | None = None
    limit_slpt_rrr_from: int | None = None
    limit_slpt_rrr_to: int | None = None
    sl_value_type: str | None = None
    pt_value_type: str | None = None
    sl_indicator_based: bool | None = None
    pt_indicator_based: bool | None = None
    sl_percent: bool | None = None
    min_sl_percent: float | None = None
    max_sl_percent: float | None = None
    pt_percent: bool | None = None
    min_pt_percent: float | None = None
    max_pt_percent: float | None = None

    # ── BuildMode (Genetic) ──
    generations: int | None = None
    population: int | None = None
    islands: int | None = None
    migration_modulo: int | None = None
    migration_rate: int | None = None
    init_generation_type: int | None = None
    decimation_coef: int | None = None
    evo_restart_on_finish: bool | None = None
    evo_restart_on_stagnation: bool | None = None
    evo_restart_stagnation_fitness_type: int | None = None
    evo_restart_stagnation_generations: int | None = None
    evo_in_sample_period_ratio: int | None = None
    fresh_blood_replace_similar: bool | None = None
    fresh_blood_replace_weakest: bool | None = None
    fresh_blood_weakest_pct: int | None = None
    fresh_blood_weakest_generations: int | None = None
    filter_initial_population: bool | None = None
    evo_fitness_restart_type: int | None = None
    evo_stagnation_restart_generations: int | None = None

    # ── Rankings ──
    max_strategies: int | None = None
    ranking_type: str | None = None  # "ReturnDDRatio", "Fitness"
    ranking_avg_trades_min: int | None = None
    ranking_pf_min: float | None = None
    ranking_return_dd_min: float | None = None
    ranking_conditions_type: int | None = None

    # ── MoneyManagement ──
    mm_method: str | None = None  # "FixedSize", "RiskFixedBalancePct", etc.
    mm_lot_size: float | None = None
    initial_capital: int | None = None
    mm_risk_pct: float | None = None
    mm_max_drawdown: int | None = None

    # ── ATMs ──
    atms_enable: bool | None = None
    atms_scale_out_type: int | None = None
    atms_size_decimals: int | None = None
    atms_min_size: float | None = None

    # ── PartsToImprove ──
    entry_rules_symmetry: bool | None = None
    entry_long_improvement: bool | None = None
    entry_short_improvement: bool | None = None
    exit_rules_symmetry: bool | None = None
    exit_long_improvement: bool | None = None
    exit_short_improvement: bool | None = None

    # ── CrossChecks internals ──
    wf_period: int | None = None
    wf_optimization: int | None = None
    wf_param1: int | None = None
    wf_param2: int | None = None
    wf_optimize_periods: bool | None = None
    wf_optimize_exit_types: bool | None = None
    wf_max_tests: int | None = None
    wf_acceptance_threshold_pct: int | None = None
    wf_acceptance_min_conditions: int | None = None
    wf_acceptance_min_markets: int | None = None
    wf_acceptance_pf_min: float | None = None
    rc_spread: int | None = None
    rc_pf_min: float | None = None
    rc_min_conditions: int | None = None
    rc_min_markets: int | None = None
    main_test_values: dict[str, bool] | None = None  # which cross-check validations to run

    # ── Blocks bridge (REQ-18 / REQ-03) ──
    enabled_blocks: list[str] | None = None  # DSL building-block names to enable in SQX
    block_weights: dict[str, float] | None = None  # per-block weight overrides


_BUILD_CONFIG_MAP: dict[str, tuple[str, str, str]] = {
    # ── Trading Session (BuildTradingOptions) ──
    "exit_at_end_of_day": (
        r'<Param key="ExitAtEndOfDay"[^>]*>[^<]*</Param>',
        r'<Param key="ExitAtEndOfDay" className="ExitAtEndOfDay">{value}</Param>',
        "boolean",
    ),
    "eod_exit_time": (
        r'<Param key="EODExitTime"[^>]*>[^<]*</Param>',
        r'<Param key="EODExitTime" className="ExitAtEndOfDay">{value}</Param>',
        "int",
    ),
    "exit_on_friday": (
        r'<Param key="ExitOnFriday"[^>]*>[^<]*</Param>',
        r'<Param key="ExitOnFriday" className="ExitOnFriday">{value}</Param>',
        "boolean",
    ),
    "friday_exit_time": (
        r'<Param key="FridayExitTime"[^>]*>[^<]*</Param>',
        r'<Param key="FridayExitTime" className="ExitOnFriday">{value}</Param>',
        "int",
    ),
    "limit_time_range": (
        r'<Param key="LimitTimeRange"[^>]*>[^<]*</Param>',
        r'<Param key="LimitTimeRange" className="LimitTimeRange">{value}</Param>',
        "boolean",
    ),
    "signal_time_range_from": (
        r'<Param key="SignalTimeRangeFrom"[^>]*>[^<]*</Param>',
        r'<Param key="SignalTimeRangeFrom" className="LimitTimeRange">{value}</Param>',
        "int",
    ),
    "signal_time_range_to": (
        r'<Param key="SignalTimeRangeTo"[^>]*>[^<]*</Param>',
        r'<Param key="SignalTimeRangeTo" className="LimitTimeRange">{value}</Param>',
        "int",
    ),
    "exit_at_end_of_range": (
        r'<Param key="ExitAtEndOfRange"[^>]*>[^<]*</Param>',
        r'<Param key="ExitAtEndOfRange" className="LimitTimeRange">{value}</Param>',
        "boolean",
    ),
    "max_trades_per_day": (
        r'<Param key="MaxTradesPerDay"[^>]*>[^<]*</Param>',
        r'<Param key="MaxTradesPerDay" className="MaxTradesPerDay">{value}</Param>',
        "int",
    ),
    "session": (
        r'<Param key="Session"[^>]*>[^<]*</Param>',
        r'<Param key="Session" className="SessionOption">{value}</Param>',
        "string",
    ),
    "reserved_bars": (
        r'<Param key="ReservedBars"[^>]*>[^<]*</Param>',
        r'<Param key="ReservedBars" className="ReservedBars">{value}</Param>',
        "int",
    ),
    "store_chart_data": (
        r'<Param key="StoreChartData"[^>]*>[^<]*</Param>',
        r'<Param key="StoreChartData" className="StoreChartData">{value}</Param>',
        "boolean",
    ),

    # ── Rules Complexity ──
    "min_conditions": (
        r'(minConditions=")\d+(")',
        r'\g<1>{value}\2',
        "int",
    ),
    "max_conditions": (
        r'(maxConditions=")\d+(")',
        r'\g<1>{value}\2',
        "int",
    ),
    "min_exit_conditions": (
        r'(minExitConditions=")\d+(")',
        r'\g<1>{value}\2',
        "int",
    ),
    "max_exit_conditions": (
        r'(maxExitConditions=")\d+(")',
        r'\g<1>{value}\2',
        "int",
    ),
    "min_period": (
        r'(minPeriod=")\d+(")',
        r'\g<1>{value}\2',
        "int",
    ),
    "max_period": (
        r'(maxPeriod=")\d+(")',
        r'\g<1>{value}\2',
        "int",
    ),
    "min_shift": (
        r'(minShift=")\d+(")',
        r'\g<1>{value}\2',
        "int",
    ),
    "max_shift": (
        r'(maxShift=")\d+(")',
        r'\g<1>{value}\2',
        "int",
    ),

    # ── Market Sides ──
    "market_sides": (
        r'<MarketSides type="[^"]*">',
        r'<MarketSides type="{value}">',
        "string",
    ),
    "entry_symmetry": (
        r'<EntrySymmetry>[^<]*</EntrySymmetry>',
        r'<EntrySymmetry>{value}</EntrySymmetry>',
        "boolean",
    ),
    "exit_symmetry": (
        r'<ExitSymmetry>[^<]*</ExitSymmetry>',
        r'<ExitSymmetry>{value}</ExitSymmetry>',
        "boolean",
    ),

    # ── SL/PT Options ──
    "sl_required": (
        r'<SLRequired>[^<]*</SLRequired>',
        r'<SLRequired>{value}</SLRequired>',
        "boolean",
    ),
    "sl_fixed_pips": (
        r'<SLFixedPips>[^<]*</SLFixedPips>',
        r'<SLFixedPips>{value}</SLFixedPips>',
        "boolean",
    ),
    "min_sl_pips": (
        r'<MinSLInPips>[^<]*</MinSLInPips>',
        r'<MinSLInPips>{value}</MinSLInPips>',
        "int",
    ),
    "max_sl_pips": (
        r'<MaxSLInPips>[^<]*</MaxSLInPips>',
        r'<MaxSLInPips>{value}</MaxSLInPips>',
        "int",
    ),
    "min_sl_money": (
        r'<MinSLInMoney>[^<]*</MinSLInMoney>',
        r'<MinSLInMoney>{value}</MinSLInMoney>',
        "int",
    ),
    "max_sl_money": (
        r'<MaxSLInMoney>[^<]*</MaxSLInMoney>',
        r'<MaxSLInMoney>{value}</MaxSLInMoney>',
        "int",
    ),
    "sl_atr": (
        r'<SLATR>[^<]*</SLATR>',
        r'<SLATR>{value}</SLATR>',
        "boolean",
    ),
    "min_sl_atr_multiple": (
        r'<MinSLATRMultiple>[^<]*</MinSLATRMultiple>',
        r'<MinSLATRMultiple>{value}</MinSLATRMultiple>',
        "float",
    ),
    "max_sl_atr_multiple": (
        r'<MaxSLATRMultiple>[^<]*</MaxSLATRMultiple>',
        r'<MaxSLATRMultiple>{value}</MaxSLATRMultiple>',
        "float",
    ),
    "min_sl_atr_period": (
        r'<MinSLATRPeriod>[^<]*</MinSLATRPeriod>',
        r'<MinSLATRPeriod>{value}</MinSLATRPeriod>',
        "int",
    ),
    "max_sl_atr_period": (
        r'<MaxSLATRPeriod>[^<]*</MaxSLATRPeriod>',
        r'<MaxSLATRPeriod>{value}</MaxSLATRPeriod>',
        "int",
    ),
    "pt_required": (
        r'<PTRequired>[^<]*</PTRequired>',
        r'<PTRequired>{value}</PTRequired>',
        "boolean",
    ),
    "pt_fixed_pips": (
        r'<PTFixedPips>[^<]*</PTFixedPips>',
        r'<PTFixedPips>{value}</PTFixedPips>',
        "boolean",
    ),
    "min_pt_pips": (
        r'<MinPTInPips>[^<]*</MinPTInPips>',
        r'<MinPTInPips>{value}</MinPTInPips>',
        "int",
    ),
    "max_pt_pips": (
        r'<MaxPTInPips>[^<]*</MaxPTInPips>',
        r'<MaxPTInPips>{value}</MaxPTInPips>',
        "int",
    ),
    "min_pt_money": (
        r'<MinPTInMoney>[^<]*</MinPTInMoney>',
        r'<MinPTInMoney>{value}</MinPTInMoney>',
        "int",
    ),
    "max_pt_money": (
        r'<MaxPTInMoney>[^<]*</MaxPTInMoney>',
        r'<MaxPTInMoney>{value}</MaxPTInMoney>',
        "int",
    ),
    "pt_atr": (
        r'<PTATR>[^<]*</PTATR>',
        r'<PTATR>{value}</PTATR>',
        "boolean",
    ),
    "min_pt_atr_multiple": (
        r'<MinPTATRMultiple>[^<]*</MinPTATRMultiple>',
        r'<MinPTATRMultiple>{value}</MinPTATRMultiple>',
        "float",
    ),
    "max_pt_atr_multiple": (
        r'<MaxPTATRMultiple>[^<]*</MaxPTATRMultiple>',
        r'<MaxPTATRMultiple>{value}</MaxPTATRMultiple>',
        "float",
    ),
    "min_pt_atr_period": (
        r'<MinPTATRPeriod>[^<]*</MinPTATRPeriod>',
        r'<MinPTATRPeriod>{value}</MinPTATRPeriod>',
        "int",
    ),
    "max_pt_atr_period": (
        r'<MaxPTATRPeriod>[^<]*</MaxPTATRPeriod>',
        r'<MaxPTATRPeriod>{value}</MaxPTATRPeriod>',
        "int",
    ),
    "limit_slpt_rrr": (
        r'<LimitSLPTRRR>[^<]*</LimitSLPTRRR>',
        r'<LimitSLPTRRR>{value}</LimitSLPTRRR>',
        "boolean",
    ),
    "limit_slpt_rrr_from": (
        r'<LimitSLPTRRRFrom>[^<]*</LimitSLPTRRRFrom>',
        r'<LimitSLPTRRRFrom>{value}</LimitSLPTRRRFrom>',
        "int",
    ),
    "limit_slpt_rrr_to": (
        r'<LimitSLPTRRRTo>[^<]*</LimitSLPTRRRTo>',
        r'<LimitSLPTRRRTo>{value}</LimitSLPTRRRTo>',
        "int",
    ),
    "sl_value_type": (
        r'<SLValueType>[^<]*</SLValueType>',
        r'<SLValueType>{value}</SLValueType>',
        "string",
    ),
    "pt_value_type": (
        r'<PTValueType>[^<]*</PTValueType>',
        r'<PTValueType>{value}</PTValueType>',
        "string",
    ),
    "sl_indicator_based": (
        r'<SLIndicatorBased>[^<]*</SLIndicatorBased>',
        r'<SLIndicatorBased>{value}</SLIndicatorBased>',
        "boolean",
    ),
    "pt_indicator_based": (
        r'<PTIndicatorBased>[^<]*</PTIndicatorBased>',
        r'<PTIndicatorBased>{value}</PTIndicatorBased>',
        "boolean",
    ),
    "sl_percent": (
        r'<SLPercent>[^<]*</SLPercent>',
        r'<SLPercent>{value}</SLPercent>',
        "boolean",
    ),
    "min_sl_percent": (
        r'<MinSLInPercent>[^<]*</MinSLInPercent>',
        r'<MinSLInPercent>{value}</MinSLInPercent>',
        "float",
    ),
    "max_sl_percent": (
        r'<MaxSLInPercent>[^<]*</MaxSLInPercent>',
        r'<MaxSLInPercent>{value}</MaxSLInPercent>',
        "float",
    ),
    "pt_percent": (
        r'<PTPercent>[^<]*</PTPercent>',
        r'<PTPercent>{value}</PTPercent>',
        "boolean",
    ),
    "min_pt_percent": (
        r'<MinPTInPercent>[^<]*</MinPTInPercent>',
        r'<MinPTInPercent>{value}</MinPTInPercent>',
        "float",
    ),
    "max_pt_percent": (
        r'<MaxPTInPercent>[^<]*</MaxPTInPercent>',
        r'<MaxPTInPercent>{value}</MaxPTInPercent>',
        "float",
    ),

    # ── BuildMode (Genetic) ──
    "generations": (
        r'<MaxGenerations>\d+</MaxGenerations>',
        r'<MaxGenerations>{value}</MaxGenerations>',
        "int",
    ),
    "population": (
        r'<PopulationSize>\d+</PopulationSize>',
        r'<PopulationSize>{value}</PopulationSize>',
        "int",
    ),
    "islands": (
        r'<Islands>\d+</Islands>',
        r'<Islands>{value}</Islands>',
        "int",
    ),
    "migration_modulo": (
        r'<MigrationModulo>\d+</MigrationModulo>',
        r'<MigrationModulo>{value}</MigrationModulo>',
        "int",
    ),
    "migration_rate": (
        r'<MigrationRate>\d+</MigrationRate>',
        r'<MigrationRate>{value}</MigrationRate>',
        "int",
    ),
    "init_generation_type": (
        r'<InitGenerationType>\d+</InitGenerationType>',
        r'<InitGenerationType>{value}</InitGenerationType>',
        "int",
    ),
    "decimation_coef": (
        r'<DecimationCoef>\d+</DecimationCoef>',
        r'<DecimationCoef>{value}</DecimationCoef>',
        "int",
    ),
    "evo_restart_on_finish": (
        r'<EvoRestartOnFinish status="[^"]*"',
        r'<EvoRestartOnFinish status="{value}"',
        "boolean",
    ),
    "evo_restart_on_stagnation": (
        r'<EvoRestartOnStagnation status="[^"]*"',
        r'<EvoRestartOnStagnation status="{value}"',
        "boolean",
    ),
    "evo_restart_stagnation_fitness_type": (
        r'<EvoRestartOnStagnation[^>]*fitnessType="\d+"',
        r'<EvoRestartOnStagnation status="{evo_restart_on_stagnation}" fitnessType="{value}" generations="{evo_restart_stagnation_generations}">',
        "int",
    ),
    "evo_restart_stagnation_generations": (
        r'<EvoRestartOnStagnation[^>]*generations="\d+"',
        r'<EvoRestartOnStagnation status="{evo_restart_on_stagnation}" fitnessType="{evo_restart_stagnation_fitness_type}" generations="{value}">',
        "int",
    ),
    "evo_in_sample_period_ratio": (
        r'<EvoInSamplePeriod ratio="\d+"',
        r'<EvoInSamplePeriod ratio="{value}">',
        "int",
    ),
    "fresh_blood_replace_similar": (
        r'<FreshBloodReplaceSimilar>[^<]*</FreshBloodReplaceSimilar>',
        r'<FreshBloodReplaceSimilar>{value}</FreshBloodReplaceSimilar>',
        "boolean",
    ),
    "fresh_blood_replace_weakest": (
        r'<FreshBloodReplaceWeakest>[^<]*</FreshBloodReplaceWeakest>',
        r'<FreshBloodReplaceWeakest>{value}</FreshBloodReplaceWeakest>',
        "boolean",
    ),
    "fresh_blood_weakest_pct": (
        r'<FreshBloodWeakestPct>\d+</FreshBloodWeakestPct>',
        r'<FreshBloodWeakestPct>{value}</FreshBloodWeakestPct>',
        "int",
    ),
    "fresh_blood_weakest_generations": (
        r'<FreshBloodWeakestGenerations>\d+</FreshBloodWeakestGenerations>',
        r'<FreshBloodWeakestGenerations>{value}</FreshBloodWeakestGenerations>',
        "int",
    ),
    "filter_initial_population": (
        r'<FilterInitialPopulation>[^<]*</FilterInitialPopulation>',
        r'<FilterInitialPopulation>{value}</FilterInitialPopulation>',
        "boolean",
    ),
    "evo_fitness_restart_type": (
        r'<EvoFitnessRestartType>\d+</EvoFitnessRestartType>',
        r'<EvoFitnessRestartType>{value}</EvoFitnessRestartType>',
        "int",
    ),
    "evo_stagnation_restart_generations": (
        r'<EvoStagnationRestartGenerations>\d+</EvoStagnationRestartGenerations>',
        r'<EvoStagnationRestartGenerations>{value}</EvoStagnationRestartGenerations>',
        "int",
    ),

    # ── Rankings ──
    "max_strategies": (
        r'<MaxStrategies>\d+</MaxStrategies>',
        r'<MaxStrategies>{value}</MaxStrategies>',
        "int",
    ),
    "ranking_type": (
        r'<Ranking type="[^"]*"',
        r'<Ranking type="{value}"',
        "string",
    ),
    "ranking_avg_trades_min": (
        r'(<Column-Value column="AvgTradesPerMonth"[^>]*/>[\s\S]*?<Numeric-Value value=")[^"]*(")',
        r'\g<1>{value}\2',
        "int",
    ),
    "ranking_pf_min": (
        r'(<Column-Value column="ProfitFactor"[^>]*/>[\s\S]*?<Numeric-Value value=")[^"]*(")',
        r'\g<1>{value}\2',
        "float",
    ),
    "ranking_return_dd_min": (
        r'(<Column-Value column="ReturnDDRatio"[^>]*/>[\s\S]*?<Numeric-Value value=")[^"]*(")',
        r'\g<1>{value}\2',
        "float",
    ),
    "ranking_conditions_type": (
        r'<ConditionsType>\d+</ConditionsType>',
        r'<ConditionsType>{value}</ConditionsType>',
        "int",
    ),

    # ── MoneyManagement ──
    "mm_method": (
        r'<Method type="[^"]*" use="[^"]*"',
        r'<Method type="{value}" use="true"',
        "string",
    ),
    "mm_lot_size": (
        r'<Param key="Size" className="FixedSize">[^<]*</Param>',
        r'<Param key="Size" className="FixedSize">{value}</Param>',
        "float",
    ),
    "initial_capital": (
        r'<InitialCapital>\d+</InitialCapital>',
        r'<InitialCapital>{value}</InitialCapital>',
        "int",
    ),
    "mm_risk_pct": (
        r'<Param key="Risk" className="RiskFixedBalancePct">[^<]*</Param>',
        r'<Param key="Risk" className="RiskFixedBalancePct">{value}</Param>',
        "float",
    ),
    "mm_max_drawdown": (
        r'<RiskManagement maxDrawdown="\d+">',
        r'<RiskManagement maxDrawdown="{value}">',
        "int",
    ),

    # ── ATMs ──
    "atms_enable": (
        r'(<ATMs enable=")[^"]*(")',
        r'\g<1>{value}\g<2>',
        "boolean",
    ),
    "atms_scale_out_type": (
        r'(<ATMs[^>]*scaleOutType=")\d+(")',
        r'\g<1>{value}\2',
        "int",
    ),
    "atms_size_decimals": (
        r'(<ATMs[^>]*sizeDecimals=")\d+(")',
        r'\g<1>{value}\2',
        "int",
    ),
    "atms_min_size": (
        r'(<ATMs[^>]*minSize=")[^"]*(")',
        r'\g<1>{value}\2',
        "float",
    ),

    # ── PartsToImprove ──
    "entry_rules_symmetry": (
        r'(<EntryRules symmetry=")[^"]*(")',
        r'\g<1>{value}\g<2>',
        "boolean",
    ),
    "entry_long_improvement": (
        r'(<LongImprovement use=")[^"]*(")',
        r'\g<1>{value}\g<2>',
        "boolean",
    ),
    "entry_short_improvement": (
        r'(<ShortImprovement use=")[^"]*(")',
        r'\g<1>{value}\g<2>',
        "boolean",
    ),
    "exit_rules_symmetry": (
        r'(<ExitRules symmetry=")[^"]*(")',
        r'\g<1>{value}\g<2>',
        "boolean",
    ),
    "exit_long_improvement": (
        r'(<LongImprovement use=")[^"]*(")',
        r'\g<1>{value}\g<2>',
        "boolean",
    ),
    "exit_short_improvement": (
        r'(<ShortImprovement use=")[^"]*(")',
        r'\g<1>{value}\g<2>',
        "boolean",
    ),

    # ── CrossChecks internals ──
    "wf_period": (
        r'(<WalkForward type="1" period=")\d+(")',
        r'\g<1>{value}\2',
        "int",
    ),
    "wf_optimization": (
        r'(<WalkForward type="1" period="\d+" optimization=")\d+(")',
        r'\g<1>{value}\2',
        "int",
    ),
    "wf_param1": (
        r'(<Param1 value=")\d+(")',
        r'\g<1>{value}\2',
        "int",
    ),
    "wf_param2": (
        r'(<Param2 value=")\d+(")',
        r'\g<1>{value}\2',
        "int",
    ),
    "wf_optimize_periods": (
        r'(<OptimizePeriods>)[^<]*(</OptimizePeriods>)',
        r'\g<1>{value}\g<2>',
        "boolean",
    ),
    "wf_optimize_exit_types": (
        r'(<OptimizeExitTypes>)[^<]*(</OptimizeExitTypes>)',
        r'\g<1>{value}\g<2>',
        "boolean",
    ),
    "wf_max_tests": (
        r'(<MaxTests>)\d+(</MaxTests>)',
        r'\g<1>{value}\g<2>',
        "int",
    ),
    "wf_acceptance_threshold_pct": (
        r'(<Conditions thresholdPct=")\d+(")',
        r'\g<1>{value}\2',
        "int",
    ),
    "wf_acceptance_min_conditions": (
        r'(<MinConditions>)\d+(</MinConditions>)',
        r'\g<1>{value}\g<2>',
        "int",
    ),
    "wf_acceptance_min_markets": (
        r'(<MinMarkets>)\d+(</MinMarkets>)',
        r'\g<1>{value}\g<2>',
        "int",
    ),
    "wf_acceptance_pf_min": (
        r'(<Column-Value column="NetProfit"[^>]*resultType="WalkForwardOptimization"[^>]*minValue=")[^"]*(")',
        r'\g<1>{value}\2',
        "float",
    ),
    "rc_spread": (
        r'(<Chart symbol="[^"]*" timeframe="[^"]*" spread=")\d+(")',
        r'\g<1>{value}\2',
        "int",
    ),
    "rc_pf_min": (
        r'(<Column-Value column="ProfitFactor"[^>]*resultType="RetestOnAdditionalMarkets"[^>]*minValue=")[^"]*(")',
        r'\g<1>{value}\2',
        "float",
    ),
    "rc_min_conditions": (
        r'(<MinConditions>)\d+(</MinConditions>)',
        r'\g<1>{value}\g<2>',
        "int",
    ),
    "rc_min_markets": (
        r'(<MinMarkets>)\d+(</MinMarkets>)',
        r'\g<1>{value}\g<2>',
        "int",
    ),
    "main_test_values": (
        r'<MainTestValues[^>]*/>',
        r'<MainTestValues {main_test_values_xml} />',
        "dict",
    ),
}


def _format_build_config_value(value: Any, format_type: str) -> str:
    """Format a BuildConfig field value for XML output."""
    if format_type == "boolean":
        return "true" if value else "false"
    elif format_type == "int":
        return str(value)
    elif format_type == "float":
        return f"{value:.2f}"
    elif format_type == "string":
        return str(value)
    elif format_type == "dict":
        return str(value)
    else:
        return str(value)


def _build_main_test_values_xml(values: dict[str, bool]) -> str:
    """Build the MainTestValues attribute string from a dict."""
    parts = []
    for key, val in values.items():
        parts.append(f'{key}="{"true" if val else "false"}"')
    return " ".join(parts)


def _apply_build_config(template_xml: str, config: BuildConfig) -> str:
    """Apply BuildConfig overrides to the template XML.

    For each field in BuildConfig that is not None, applies the appropriate
    XML modification using the mapping defined in _BUILD_CONFIG_MAP.

    Args:
        template_xml: The raw template XML string.
        config: BuildConfig instance with override values.

    Returns:
        The modified XML string.
    """
    xml = template_xml

    for field_name, (pattern, replacement, format_type) in _BUILD_CONFIG_MAP.items():
        value = getattr(config, field_name, None)
        if value is None:
            continue

        if format_type == "dict" and field_name == "main_test_values":
            # Special handling for MainTestValues dict
            values_xml = _build_main_test_values_xml(value)
            xml = re.sub(pattern, f'<MainTestValues {values_xml} />', xml)
            continue

        formatted = _format_build_config_value(value, format_type)

        try:
            xml = re.sub(pattern, replacement.format(value=formatted), xml)
        except (re.error, KeyError, IndexError) as e:
            logger.warning("Failed to apply build config field '%s': %s", field_name, e)

    return xml


def create_project(
    sqx_install_path: str,
    campaign_id: str,
    *,
    symbol: str = "EURUSD",
    timeframe: str = "H1",
    date_from: str = "2020.1.1",
    date_to: str | None = None,
    generations: int = 80,
    population: int = 200,
    crossover: float = 0.8,
    mutation: float = 0.15,
    slippage: int = _JFOREX_SLIPPAGE,
    spread: int = _JFOREX_SPREAD,
    commission: float = _JFOREX_COMMISSION,
    rankings_min_profit_factor: float = 1.3,
    rankings_min_return_dd: float = 4.0,
    rankings_min_avg_trades: int = 2,
    walk_forward: bool = True,
    monte_carlo: bool = True,
    build_config: BuildConfig | None = None,
    broker_profile: BrokerProfile | None = None,
) -> str:
    """Create a campaign project directory from the template.

    NOTE: engine is always MetaTrader4 (the generation/backtesting engine).
    Dukascopy data works fine with it — the engine is NOT the data source.

    date_to defaults to the symbol's known max data date with margin.
    If the requested date_to exceeds available data, it is clamped silently.

    When build_config is provided, its fields override the template values.
    When build_config is None, the function behaves exactly as before
    (same re.sub calls for the fields that were previously supported).

    Returns the path to the created project.cfx.
    """
    sqx_path = Path(sqx_install_path).resolve()
    project_dir = sqx_path / "user" / "projects" / campaign_id
    dest_cfx = project_dir / "project.cfx"

    # Clamp date_to to available data for the symbol
    effective_date_to = _clamp_date_to(symbol, date_to) if date_to else _MAX_DATE_DEFAULT

    # Use broker_profile to override slippage/spread/commission defaults
    if broker_profile is not None:
        slippage = max(1, int(broker_profile.slippage.fixed_pips))
        spread = max(1, int(broker_profile.spread_config.base_spread))
        comm_type = broker_profile.commission.type.value if hasattr(broker_profile.commission.type, 'value') else broker_profile.commission.type
        commission = float(broker_profile.commission.value) if comm_type in ("fixed", "percent") else 0.0

    # Remove if exists
    if project_dir.exists():
        shutil.rmtree(project_dir)

    # Create databank directories (SQX expects these)
    databanks = [
        "Results", "Last generation", "Initial population",
        "Strategies to improve", "Existing portfolio",
    ]
    for db in databanks:
        (project_dir / "databanks" / db).mkdir(parents=True, exist_ok=True)

    # Read template
    template_path = _template_path()
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    with zipfile.ZipFile(template_path, "r") as z:
        config_xml = z.read("config.xml").decode("utf-8")
        task_xml = z.read("Build-Task1.xml").decode("utf-8")

    # Normalize line endings — template comes from Windows with \r\n,
    # mixing with \n replacements confuses SQX's XML parser.
    config_xml = config_xml.replace("\r\n", "\n")
    task_xml = task_xml.replace("\r\n", "\n")

    # ── config.xml: replace project name ──
    config_xml = re.sub(
        r'name="[^"]*"',
        f'name="{campaign_id}"',
        config_xml,
        count=1,
    )

    # ── Build-Task1.xml modifications ──

    # 1. Data section: symbol, timeframe, date range
    # Symbol naming: {SYMBOL}_{TIMEFRAME}_dukas for Dukascopy data
    chart_symbol = f"{symbol}_{timeframe.upper()}_dukas"

    chart_old = re.search(
        r'<Chart symbol="[^"]*" timeframe="[^"]*" spread="\d+"',
        task_xml,
    )
    if chart_old:
        task_xml = task_xml.replace(
            chart_old.group(),
            f'<Chart symbol="{chart_symbol}" timeframe="{timeframe}" spread="{spread}"',
        )

    # 2. Setup: date range, slippage, engine
    # NOTE: engine is ALWAYS MetaTrader4. "Dukascopy" is an invalid engine string.
    engine_val = _JFOREX_ENGINE
    setup_old = re.search(
        r'dateFrom="[^"]*" dateTo="[^"]*"[^>]*slippage="\d+"[^>]*engine="[^"]*"',
        task_xml,
    )
    if setup_old:
        task_xml = task_xml.replace(
            setup_old.group(),
            f'dateFrom="{date_from}" dateTo="{effective_date_to}" '
            f'testPrecision="1" session="No Session" '
            f'slippage="{slippage}" minDist="0" engine="{engine_val}"',
        )

    # 3. Commissions: kept as type="None" — this SQX version does NOT support
    # type="Money" in the Commissions XML element. The template default (None)
    # is preserved. Slippage and spread are already set on the Setup element.
    # Commission handling ($3.5/lot JForex Dukascopy) requires further research
    # into SQX's internal format or plugin-based commission models.

    # 4. Genetic settings
    task_xml = re.sub(
        r'<PopulationSize>\d+</PopulationSize>',
        f'<PopulationSize>{population}</PopulationSize>',
        task_xml,
    )
    task_xml = re.sub(
        r'<MaxGenerations>\d+</MaxGenerations>',
        f'<MaxGenerations>{generations}</MaxGenerations>',
        task_xml,
    )
    task_xml = re.sub(
        r'<CrossoverProbability>[0-9.]+</CrossoverProbability>',
        f'<CrossoverProbability>{crossover}</CrossoverProbability>',
        task_xml,
    )
    task_xml = re.sub(
        r'<MutationProbability>[0-9.]+</MutationProbability>',
        f'<MutationProbability>{mutation}</MutationProbability>',
        task_xml,
    )

    # 5. Rankings: enable and set acceptance criteria
    if build_config is None:
        # Backward-compatible: use existing re.sub calls
        task_xml = re.sub(
            r'<Rankings type="never">',
            '<Rankings type="always">',
            task_xml,
        )

        # Modify Conditions in Rankings
        # Find ProfitFactor condition and set threshold
        task_xml = re.sub(
            r'(<Column-Value column="ProfitFactor"[^>]*/>[\s\S]*?<Numeric-Value value=")[^"]*(")',
            f'\\g<1>{rankings_min_profit_factor}\\2',
            task_xml,
        )
        task_xml = re.sub(
            r'(<Column-Value column="AvgTradesPerMonth"[^>]*/>[\s\S]*?<Numeric-Value value=")[^"]*(")',
            f'\\g<1>{rankings_min_avg_trades}\\2',
            task_xml,
        )
        task_xml = re.sub(
            r'(<Column-Value column="ReturnDDRatio"[^>]*/>[\s\S]*?<Numeric-Value value=")[^"]*(")',
            f'\\g<1>{rankings_min_return_dd}\\2',
            task_xml,
        )
    else:
        # Config-driven: apply BuildConfig overrides
        task_xml = _apply_build_config(task_xml, build_config)

    # 6. CrossChecks: enable Walk-Forward + Monte Carlo (configurable)
    if walk_forward:
        task_xml = re.sub(
            r'<WalkForwardOptimization use="false">',
            '<WalkForwardOptimization use="true">',
            task_xml,
        )
    if monte_carlo:
        task_xml = re.sub(
            r'<MonteCarloRetest use="false">',
            '<MonteCarloRetest use="true">',
            task_xml,
        )
    # Set realistic walk-forward params
    task_xml = re.sub(
        r'<WalkForward type="1" period="\d+" optimization="\d+">',
        '<WalkForward type="1" period="12" optimization="6">',
        task_xml,
    )

    # 7. RetestOnAdditionalMarkets: optionally enable
    task_xml = re.sub(
        r'<RetestOnAdditionalMarkets use="false">',
        '<RetestOnAdditionalMarkets use="false">',  # keep disabled for speed
        task_xml,
    )

    # Write new project.cfx
    with zipfile.ZipFile(dest_cfx, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("config.xml", config_xml.encode("utf-8"))
        zf.writestr("Build-Task1.xml", task_xml.encode("utf-8"))

    logger.info(
        "Created project '%s' at %s (%s %s, %d gen, %d pop, date %s..%s)",
        campaign_id, dest_cfx, symbol, timeframe,
        generations, population, date_from, effective_date_to,
    )
    return str(dest_cfx)


def remove_project(sqx_install_path: str, campaign_id: str) -> bool:
    """Remove a campaign project directory."""
    project_dir = Path(sqx_install_path) / "user" / "projects" / campaign_id
    if project_dir.exists():
        shutil.rmtree(project_dir)
        logger.info("Removed project '%s'", campaign_id)
        return True
    return False
