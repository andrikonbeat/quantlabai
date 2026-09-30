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
from quantlab.cfx.models import CrossChecksConfig
from quantlab.data.symbol_registry import resolve_symbol

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


# ── Template default probe (parameter-justification-matrix REQ-1) ─────────────

# The bundled default template is a ZIP whose Build-Task1.xml holds the
# project defaults; parsed once per process.
_TEMPLATE_XML_CACHE: str | None = None


def _template_xml() -> str:
    """Return the default template's Build-Task1.xml (zip member), cached."""
    global _TEMPLATE_XML_CACHE
    if _TEMPLATE_XML_CACHE is None:
        with zipfile.ZipFile(_DEFAULT_TEMPLATE) as z:
            _TEMPLATE_XML_CACHE = z.read("Build-Task1.xml").decode(
                "utf-8", errors="replace"
            )
    return _TEMPLATE_XML_CACHE


def _extract_template_value(match: re.Match) -> str:
    """Extract the value text from a build-config regex match.

    The map patterns are shape-heterogeneous: some wrap the value between two
    captured groups (``(<ATMs enable=")[^"]*(")``), some are plain text nodes
    (``<MaxGenerations>100</MaxGenerations>``), some are attribute matches
    (``<Ranking type="ReturnDDRatio"``). Resolution order: captured-group
    span → text node → first attribute pair → whole match.
    """
    text = match.group(0)
    if match.lastindex is not None and match.lastindex >= 2:
        start = match.end(1) - match.start()
        stop = match.start(2) - match.start()
        if stop > start:
            return text[start:stop]
    node = re.search(r">([^<]*)<", text)
    if node:
        return node.group(1)
    attr = re.search(r'([\w]+)="([^"]*)"', text)
    if attr:
        return attr.group(2)
    return text


def _coerce_template_default(raw: str, format_type: str):
    """Coerce the raw template text to the field's Python type."""
    if format_type in ("dict", "blocks"):
        # No scalar default: these fields are composite structures.
        return None
    text = raw.strip()
    try:
        if format_type == "boolean":
            return text.lower() in ("true", "1", "yes")
        if format_type == "int":
            return int(text)
        if format_type == "float":
            return float(text)
    except ValueError:
        pass
    return text


_CROSSCHECKS_BLOCK = re.compile(r"<CrossChecks\b.*?</CrossChecks>", re.DOTALL)


# CrossChecks build-config fields the typed models already cover. design.md
# scopes typed access to modeled fields and keeps regex probing for the rest
# (<Param1>/<Param2>, <MaxTests>, acceptance settings and the <Chart> spread are
# still unmodeled), so this is a typed fast path rather than a replacement.
_TYPED_CROSSCHECKS_FIELDS = frozenset(
    {"wf_period", "wf_optimization", "wf_optimize_periods"}
)


def _typed_crosschecks_default(field_name: str, template_xml: str):
    """Read a template CrossChecks default through the typed model.

    Returns ``None`` when the field is not typed, the template carries no
    CrossChecks block, the block is not the AutomaticRetest dialect, or the
    specific sub-model is absent. Every one of those cases falls back to the
    existing regex probe in :func:`get_template_default`.
    """
    if field_name not in _TYPED_CROSSCHECKS_FIELDS:
        return None

    block = _CROSSCHECKS_BLOCK.search(template_xml)
    if block is None:
        return None

    config = CrossChecksConfig.from_xml(block.group(0))
    if config.dialect != "automatic_retest" or config.automatic_retest is None:
        return None

    wfo = config.automatic_retest.walk_forward_optimization
    if wfo is None:
        return None

    if field_name == "wf_period":
        return wfo.period
    if field_name == "wf_optimization":
        return wfo.optimization
    return "true" if wfo.optimize_periods else "false"


def get_template_default(field_name: str):
    """Return the SQX template default for a BuildConfig field, or ``None``.

    CrossChecks fields covered by the typed models are read from
    ``CrossChecksConfig``; every other field is probed with the field's
    build-config regex. Either way the captured value is coerced to the field's
    type. ``None`` means the field has no scalar template default (composite
    structures) or the template does not carry the parameter.

    Args:
        field_name: A BuildConfig field name.

    Returns:
        The coerced template default value, or ``None`` when unavailable.
    """
    entry = _BUILD_CONFIG_MAP.get(field_name)
    if entry is None:
        return None
    pattern, _replacement, format_type = entry
    template_xml = _template_xml()

    # Typed fast path: the WalkForwardOptimization fields the typed models
    # already cover. Returns None for every other field, so the tab-scoped
    # probe below still handles all of them.
    typed = _typed_crosschecks_default(field_name, template_xml)
    if typed is not None:
        # _BUILD_CONFIG_MAP records only the "crosscheck" marker for these
        # fields; the scalar type lives in the spec table, same as the probe
        # below. Coercing the typed value with the marker would hand back a
        # raw string (e.g. "true") where the probe returns a real bool.
        typed_type = format_type
        spec = _CROSSCHECK_FIELD_SPEC_BY_NAME.get(field_name)
        if spec is not None:
            typed_type = spec[3]
        return _coerce_template_default(str(typed), typed_type)

    haystack = template_xml
    if format_type == "crosscheck":
        # CrossChecks leaf names repeat across tabs, so the probe must read the
        # same scoped region the writer touches — otherwise, for example,
        # wi_by_hours_use would report the RetestOnAdditionalMarkets commission
        # method instead of the WhatIf one. The map records only the "crosscheck"
        # marker, so the scalar type comes from the spec table.
        spec = _CROSSCHECK_FIELD_SPEC_BY_NAME.get(field_name)
        if spec is None:
            return None
        scope = spec[1]
        format_type = spec[3]
        region = re.search(scope, haystack, re.DOTALL)
        if region is None:
            return None
        haystack = region.group(0)

    match = re.search(pattern, haystack)
    if match is None:
        return None
    return _coerce_template_default(_extract_template_value(match), format_type)


# SQX tab classification for BuildConfig fields — mirrors the dataclass
# section comments (the in-repo SQX tab taxonomy, REQ-1 reviewability).
_FIELD_TABS: dict[str, str] = {
    # ── Trading Session (BuildTradingOptions) ──
    "exit_at_end_of_day": "Trading Session",
    "eod_exit_time": "Trading Session",
    "exit_on_friday": "Trading Session",
    "friday_exit_time": "Trading Session",
    "limit_time_range": "Trading Session",
    "signal_time_range_from": "Trading Session",
    "signal_time_range_to": "Trading Session",
    "exit_at_end_of_range": "Trading Session",
    "max_trades_per_day": "Trading Session",
    "session": "Trading Session",
    "reserved_bars": "Trading Session",
    "store_chart_data": "Trading Session",
    # ── Rules Complexity ──
    "min_conditions": "Rules Complexity",
    "max_conditions": "Rules Complexity",
    "min_exit_conditions": "Rules Complexity",
    "max_exit_conditions": "Rules Complexity",
    "min_period": "Rules Complexity",
    "max_period": "Rules Complexity",
    "min_shift": "Rules Complexity",
    "max_shift": "Rules Complexity",
    # ── Market Sides ──
    "market_sides": "Market Sides",
    "entry_symmetry": "Market Sides",
    "exit_symmetry": "Market Sides",
    # ── SL/PT Options ──
    "sl_required": "SL/PT Options",
    "sl_fixed_pips": "SL/PT Options",
    "min_sl_pips": "SL/PT Options",
    "max_sl_pips": "SL/PT Options",
    "min_sl_money": "SL/PT Options",
    "max_sl_money": "SL/PT Options",
    "sl_atr": "SL/PT Options",
    "min_sl_atr_multiple": "SL/PT Options",
    "max_sl_atr_multiple": "SL/PT Options",
    "min_sl_atr_period": "SL/PT Options",
    "max_sl_atr_period": "SL/PT Options",
    "pt_required": "SL/PT Options",
    "pt_fixed_pips": "SL/PT Options",
    "min_pt_pips": "SL/PT Options",
    "max_pt_pips": "SL/PT Options",
    "min_pt_money": "SL/PT Options",
    "max_pt_money": "SL/PT Options",
    "pt_atr": "SL/PT Options",
    "min_pt_atr_multiple": "SL/PT Options",
    "max_pt_atr_multiple": "SL/PT Options",
    "min_pt_atr_period": "SL/PT Options",
    "max_pt_atr_period": "SL/PT Options",
    "limit_slpt_rrr": "SL/PT Options",
    "limit_slpt_rrr_from": "SL/PT Options",
    "limit_slpt_rrr_to": "SL/PT Options",
    "sl_value_type": "SL/PT Options",
    "pt_value_type": "SL/PT Options",
    "sl_indicator_based": "SL/PT Options",
    "pt_indicator_based": "SL/PT Options",
    "sl_percent": "SL/PT Options",
    "min_sl_percent": "SL/PT Options",
    "max_sl_percent": "SL/PT Options",
    "pt_percent": "SL/PT Options",
    "min_pt_percent": "SL/PT Options",
    "max_pt_percent": "SL/PT Options",
    # ── BuildMode (Genetic) ──
    "generations": "BuildMode (Genetic)",
    "population": "BuildMode (Genetic)",
    "islands": "BuildMode (Genetic)",
    "migration_modulo": "BuildMode (Genetic)",
    "migration_rate": "BuildMode (Genetic)",
    "init_generation_type": "BuildMode (Genetic)",
    "decimation_coef": "BuildMode (Genetic)",
    "evo_restart_on_finish": "BuildMode (Genetic)",
    "evo_restart_on_stagnation": "BuildMode (Genetic)",
    "evo_restart_stagnation_fitness_type": "BuildMode (Genetic)",
    "evo_restart_stagnation_generations": "BuildMode (Genetic)",
    "evo_in_sample_period_ratio": "BuildMode (Genetic)",
    "fresh_blood_replace_similar": "BuildMode (Genetic)",
    "fresh_blood_replace_weakest": "BuildMode (Genetic)",
    "fresh_blood_weakest_pct": "BuildMode (Genetic)",
    "fresh_blood_weakest_generations": "BuildMode (Genetic)",
    "filter_initial_population": "BuildMode (Genetic)",
    "evo_fitness_restart_type": "BuildMode (Genetic)",
    "evo_stagnation_restart_generations": "BuildMode (Genetic)",
    # ── Rankings ──
    "max_strategies": "Rankings",
    "ranking_type": "Rankings",
    "ranking_avg_trades_min": "Rankings",
    "ranking_pf_min": "Rankings",
    "ranking_return_dd_min": "Rankings",
    "ranking_conditions_type": "Rankings",
    # ── MoneyManagement ──
    "mm_method": "MoneyManagement",
    "mm_lot_size": "MoneyManagement",
    "initial_capital": "MoneyManagement",
    "mm_risk_pct": "MoneyManagement",
    "mm_max_drawdown": "MoneyManagement",
    # ── ATMs ──
    "atms_enable": "ATMs",
    "atms_scale_out_type": "ATMs",
    "atms_size_decimals": "ATMs",
    "atms_min_size": "ATMs",
    # ── PartsToImprove ──
    "entry_rules_symmetry": "PartsToImprove",
    "entry_long_improvement": "PartsToImprove",
    "entry_short_improvement": "PartsToImprove",
    "exit_rules_symmetry": "PartsToImprove",
    "exit_long_improvement": "PartsToImprove",
    "exit_short_improvement": "PartsToImprove",
    # ── CrossChecks ──
    "wf_period": "CrossChecks",
    "wf_optimization": "CrossChecks",
    "wf_param1": "CrossChecks",
    "wf_param2": "CrossChecks",
    "wf_optimize_periods": "CrossChecks",
    "wf_optimize_exit_types": "CrossChecks",
    "wf_max_tests": "CrossChecks",
    "wf_acceptance_threshold_pct": "CrossChecks",
    "wf_acceptance_min_conditions": "CrossChecks",
    "wf_acceptance_min_markets": "CrossChecks",
    "wf_acceptance_pf_min": "CrossChecks",
    "rc_spread": "CrossChecks",
    "rc_pf_min": "CrossChecks",
    "rc_min_conditions": "CrossChecks",
    "rc_min_markets": "CrossChecks",
    "main_test_values": "CrossChecks",
    # ── Blocks bridge (REQ-18 / REQ-03) ──
    "enabled_blocks": "Blocks bridge",
    "block_weights": "Blocks bridge",
}


# ── CrossChecks tab-scoped mappings (crosschecks-parameter-catalog) ─────────
# CrossChecks reuses many leaf names across its 9 robustness tabs: <MaxTests>
# appears in three of them, <NumberOfSimulations> in two, and the Min/Max
# Monte-Carlo <Param> keys in three different methods. An unscoped re.sub would
# let one tab's field rewrite its siblings, so every catalog entry declares the
# XML region it owns — a ``scope`` regex (whole tab, tab <Settings>, tab
# <AcceptanceSettings>, or a single tab <Method type="...">) — plus a ``leaf``
# regex whose two capture groups bracket the value.
#
# Every scope + leaf must resolve against real CFX evidence; the test suite
# asserts that against the bundled template and a saved config, so an invented
# element or attribute fails the suite instead of reaching a project.
#
# Evidence: sdk/quantlab/sqx/templates/default-project.sqx-template
# (Build-Task1.xml, 8 tabs) and assets/SQX_144_2953_linux_20260601/user/
# settings/Configs/DJ CFD H1.cfx (config.xml, adds <SequentialOptimization>).
_CROSSCHECK_TAB = "CrossChecks"

_RC = "RetestOnAdditionalMarkets"
_WFO = "WalkForwardOptimization"
_HPR = "RetestWithHigherPrecision"
_MCR = "MonteCarloRetest"
_WFM = "WalkForwardMatrix"
_MCM = "MonteCarloManipulation"
_PSPP = "OptProfileSysParamPermutation"
_WI = "WhatIf"
_SO = "SequentialOptimization"


def _tab_scope(tab: str) -> str:
    """Whole-tab region; self-closing tabs (SequentialOptimization) included."""
    return rf"<{tab}\b[^>]*?/>|<{tab}\b[^>]*>.*?</{tab}>"


def _settings_scope(tab: str) -> str:
    """The tab's <Settings> region."""
    return rf"<{tab}\b[^>]*>.*?<Settings\b[^>]*>.*?</Settings>"


def _acceptance_scope(tab: str) -> str:
    """The tab's <AcceptanceSettings> region."""
    return rf"<{tab}\b[^>]*>.*?<AcceptanceSettings\b[^>]*>.*?</AcceptanceSettings>"


def _method_scope(_tab: str, method: str) -> str:
    """The ``<Method type="...">`` element of ``tab``, and nothing before it.

    The region deliberately starts at the method tag rather than at the tab tag.
    A tab-anchored region would also contain every earlier ``<Method>`` in that
    tab, and the leaf's first match would then belong to the wrong method — the
    three Monte-Carlo methods that each own a ``Min``/``Max`` pair are exactly
    that failure mode. Method type names are unique in the template, which
    ``test_every_method_type_is_unique_in_the_template`` asserts, so a future
    collision fails the suite instead of silently retargeting another tab.
    """
    return rf'<Method\b[^>]*type="{method}"[^>]*>.*?</Method>'


def _node(name: str) -> str:
    """Leaf regex for a ``<name>value</name>`` text node."""
    return rf"(<{name}>)[^<]*(</{name}>)"


def _attr(element: str, attr: str) -> str:
    """Leaf regex for one attribute of an element."""
    return rf'(<{element}[^>]*\b{attr}=")[^"]*(")'


def _param(key: str) -> str:
    """Leaf regex for a typed ``<Param key="...">`` node."""
    return rf'(<Param key="{key}" type="[A-Za-z]+">)[^<]*(</Param>)'


# (field, scope, leaf, format_type) — every field is a BuildConfig attribute.
_CROSSCHECK_FIELD_SPECS: tuple[tuple[str, str, str, str], ...] = (
    # ── RetestOnAdditionalMarkets ──
    ("rc_use", _tab_scope(_RC), _attr(_RC, "use"), "boolean"),
    ("rc_date_from", _settings_scope(_RC), _attr("Setup", "dateFrom"), "string"),
    ("rc_date_to", _settings_scope(_RC), _attr("Setup", "dateTo"), "string"),
    ("rc_test_precision", _settings_scope(_RC), _attr("Setup", "testPrecision"), "int"),
    ("rc_session", _settings_scope(_RC), _attr("Setup", "session"), "string"),
    ("rc_slippage", _settings_scope(_RC), _attr("Setup", "slippage"), "int"),
    ("rc_min_dist", _settings_scope(_RC), _attr("Setup", "minDist"), "int"),
    ("rc_engine", _settings_scope(_RC), _attr("Setup", "engine"), "string"),
    ("rc_symbol", _settings_scope(_RC), _attr("Chart", "symbol"), "string"),
    ("rc_timeframe", _settings_scope(_RC), _attr("Chart", "timeframe"), "string"),
    ("rc_commission_method", _settings_scope(_RC), _attr("Method", "type"), "string"),
    ("rc_check", _acceptance_scope(_RC), _node("Check"), "string"),
    ("rc_min_conditions", _acceptance_scope(_RC), _node("MinConditions"), "int"),
    ("rc_min_markets", _acceptance_scope(_RC), _node("MinMarkets"), "int"),
    # The project's main Setup also declares <Chart ... spread="...">, so the
    # additional-markets spread is addressed through RC's own Settings scope.
    ("rc_spread", _settings_scope(_RC), _attr("Chart", "spread"), "int"),
    # PF minimums live in the Condition tree's <Numeric-Value>, not on
    # Column-Value: SQX 144.2953 never writes a minValue attribute there
    # (verified across Build-Task1.xml and 123 sampled real project configs).
    # The leaf below therefore matches nothing and _apply_in_scope logs and
    # preserves the document — these fields are intentionally inert here, and
    # reaching the value requires CrossChecksConfig's Condition handling.
    (
        "rc_pf_min",
        _acceptance_scope(_RC),
        r'(<Column-Value\b[^>]*\bminValue=")[^"]*(")',
        "float",
    ),
    # ── WalkForwardOptimization ──
    ("wf_use", _tab_scope(_WFO), _attr(_WFO, "use"), "boolean"),
    # WFO's Settings block repeats WalkForward/@period, OptimizePeriods,
    # OptimizeExitTypes and MaxTests inside WalkForwardMatrix and
    # OptProfileSysParamPermutation, so each leaf is addressed through its own
    # tab scope. Verified against Build-Task1.xml.
    ("wf_period", _settings_scope(_WFO), _attr("WalkForward", "period"), "int"),
    (
        "wf_optimization",
        _settings_scope(_WFO),
        _attr("WalkForward", "optimization"),
        "int",
    ),
    ("wf_param1", _settings_scope(_WFO), _attr("Param1", "value"), "int"),
    ("wf_param2", _settings_scope(_WFO), _attr("Param2", "value"), "int"),
    ("wf_optimize_periods", _settings_scope(_WFO), _node("OptimizePeriods"), "boolean"),
    (
        "wf_optimize_exit_types",
        _settings_scope(_WFO),
        _node("OptimizeExitTypes"),
        "boolean",
    ),
    ("wf_max_tests", _settings_scope(_WFO), _node("MaxTests"), "int"),
    (
        "wf_acceptance_threshold_pct",
        _acceptance_scope(_WFO),
        _attr("Conditions", "thresholdPct"),
        "int",
    ),
    # WalkForwardOptimization declares no MinConditions/MinMarkets — only
    # RetestOnAdditionalMarkets does. These two fields therefore have no leaf to
    # own and stay no-ops on real XML; _apply_in_scope logs and preserves the
    # document. See TestCrosscheckAcceptanceCountsAreTabOwned.
    (
        "wf_acceptance_min_conditions",
        _acceptance_scope(_WFO),
        _node("MinConditions"),
        "int",
    ),
    (
        "wf_acceptance_min_markets",
        _acceptance_scope(_WFO),
        _node("MinMarkets"),
        "int",
    ),
    # Inert for the same reason as rc_pf_min: the WalkForwardOptimization PF
    # minimum is a <Numeric-Value> inside the Condition tree, and no real
    # config puts minValue on a Column-Value.
    (
        "wf_acceptance_pf_min",
        _acceptance_scope(_WFO),
        r'(<Column-Value\b[^>]*\bminValue=")[^"]*(")',
        "float",
    ),
    # ── RetestWithHigherPrecision ──
    ("hp_use", _tab_scope(_HPR), _attr(_HPR, "use"), "boolean"),
    ("hp_precision", _settings_scope(_HPR), _node("Precision"), "int"),
    ("hp_spread", _settings_scope(_HPR), _node("Spread"), "int"),
    # ── MonteCarloRetest ──
    ("mcr_use", _tab_scope(_MCR), _attr(_MCR, "use"), "boolean"),
    (
        "mcr_number_of_simulations",
        _settings_scope(_MCR),
        _node("NumberOfSimulations"),
        "int",
    ),
    (
        "mcr_history_data_use",
        _method_scope(_MCR, "RandomizeHistoryData"),
        _attr("Method", "use"),
        "boolean",
    ),
    (
        "mcr_history_probability_up",
        _method_scope(_MCR, "RandomizeHistoryData"),
        _param("ProbabilityUp"),
        "int",
    ),
    (
        "mcr_history_probability_down",
        _method_scope(_MCR, "RandomizeHistoryData"),
        _param("ProbabilityDown"),
        "int",
    ),
    (
        "mcr_history_max_change_up",
        _method_scope(_MCR, "RandomizeHistoryData"),
        _param("MaxChangeUp"),
        "int",
    ),
    (
        "mcr_history_max_change_down",
        _method_scope(_MCR, "RandomizeHistoryData"),
        _param("MaxChangeDown"),
        "int",
    ),
    (
        "mcr_min_distance_use",
        _method_scope(_MCR, "RandomizeMinDistance"),
        _attr("Method", "use"),
        "boolean",
    ),
    (
        "mcr_min_distance_min",
        _method_scope(_MCR, "RandomizeMinDistance"),
        _param("Min"),
        "float",
    ),
    (
        "mcr_min_distance_max",
        _method_scope(_MCR, "RandomizeMinDistance"),
        _param("Max"),
        "float",
    ),
    (
        "mcr_slippage_use",
        _method_scope(_MCR, "RandomizeSlippage"),
        _attr("Method", "use"),
        "boolean",
    ),
    (
        "mcr_slippage_min",
        _method_scope(_MCR, "RandomizeSlippage"),
        _param("Min"),
        "float",
    ),
    (
        "mcr_slippage_max",
        _method_scope(_MCR, "RandomizeSlippage"),
        _param("Max"),
        "float",
    ),
    (
        "mcr_spread_use",
        _method_scope(_MCR, "RandomizeSpread"),
        _attr("Method", "use"),
        "boolean",
    ),
    (
        "mcr_spread_min",
        _method_scope(_MCR, "RandomizeSpread"),
        _param("Min"),
        "float",
    ),
    (
        "mcr_spread_max",
        _method_scope(_MCR, "RandomizeSpread"),
        _param("Max"),
        "float",
    ),
    (
        "mcr_starting_bar_use",
        _method_scope(_MCR, "RandomizeStartingBar"),
        _attr("Method", "use"),
        "boolean",
    ),
    (
        "mcr_starting_bar_max_change",
        _method_scope(_MCR, "RandomizeStartingBar"),
        _param("MaxChange"),
        "int",
    ),
    (
        "mcr_strategy_params_use",
        _method_scope(_MCR, "RandomizeStrategyParameters"),
        _attr("Method", "use"),
        "boolean",
    ),
    (
        "mcr_strategy_params_probability",
        _method_scope(_MCR, "RandomizeStrategyParameters"),
        _param("Probability"),
        "int",
    ),
    (
        "mcr_strategy_params_max_change",
        _method_scope(_MCR, "RandomizeStrategyParameters"),
        _param("MaxChange"),
        "int",
    ),
    (
        "mcr_strategy_params_symmetric",
        _method_scope(_MCR, "RandomizeStrategyParameters"),
        _param("Symmetric"),
        "boolean",
    ),
    # ── WalkForwardMatrix ──
    ("wfm_use", _tab_scope(_WFM), _attr(_WFM, "use"), "boolean"),
    ("wfm_param1_start", _settings_scope(_WFM), _attr("Param1", "start"), "int"),
    ("wfm_param1_stop", _settings_scope(_WFM), _attr("Param1", "stop"), "int"),
    ("wfm_param1_step", _settings_scope(_WFM), _attr("Param1", "step"), "int"),
    ("wfm_param2_start", _settings_scope(_WFM), _attr("Param2", "start"), "int"),
    ("wfm_param2_stop", _settings_scope(_WFM), _attr("Param2", "stop"), "int"),
    ("wfm_param2_step", _settings_scope(_WFM), _attr("Param2", "step"), "int"),
    ("wfm_threshold_pct", _acceptance_scope(_WFM), _attr("Conditions", "thresholdPct"), "int"),
    ("wfm_rob_comb_rows", _acceptance_scope(_WFM), _attr("Conditions", "robCombRows"), "int"),
    ("wfm_rob_comb_cols", _acceptance_scope(_WFM), _attr("Conditions", "robCombCols"), "int"),
    ("wfm_rob_min_comb", _acceptance_scope(_WFM), _attr("Conditions", "robMinComb"), "int"),
    # WalkForwardMatrix's own Settings block — same five leaves WFO declares,
    # addressed through the matrix scope so the two tabs never share a value.
    ("wfm_period", _settings_scope(_WFM), _attr("WalkForward", "period"), "int"),
    (
        "wfm_optimization",
        _settings_scope(_WFM),
        _attr("WalkForward", "optimization"),
        "int",
    ),
    ("wfm_optimize_periods", _settings_scope(_WFM), _node("OptimizePeriods"), "boolean"),
    (
        "wfm_optimize_exit_types",
        _settings_scope(_WFM),
        _node("OptimizeExitTypes"),
        "boolean",
    ),
    ("wfm_max_tests", _settings_scope(_WFM), _node("MaxTests"), "int"),
    # ── MonteCarloManipulation ──
    ("mcm_use", _tab_scope(_MCM), _attr(_MCM, "use"), "boolean"),
    (
        "mcm_number_of_simulations",
        _settings_scope(_MCM),
        _node("NumberOfSimulations"),
        "int",
    ),
    (
        "mcm_trades_order_use",
        _method_scope(_MCM, "RandomizeTradesOrder"),
        _attr("Method", "use"),
        "boolean",
    ),
    (
        "mcm_trades_order_method",
        _method_scope(_MCM, "RandomizeTradesOrder"),
        _param("Method"),
        "string",
    ),
    (
        "mcm_skip_trades_use",
        _method_scope(_MCM, "RandomlySkipTrades"),
        _attr("Method", "use"),
        "boolean",
    ),
    (
        "mcm_skip_trades_probability",
        _method_scope(_MCM, "RandomlySkipTrades"),
        _param("Probability"),
        "int",
    ),
    # ── OptProfileSysParamPermutation ──
    ("opspp_use", _tab_scope(_PSPP), _attr(_PSPP, "use"), "boolean"),
    ("opspp_optim_periods", _settings_scope(_PSPP), _node("OptimPeriods"), "boolean"),
    ("opspp_optim_exit_types", _settings_scope(_PSPP), _node("OptimExitTypes"), "boolean"),
    ("opspp_max_tests", _settings_scope(_PSPP), _node("MaxTests"), "int"),
    ("opspp_profit_opt_pct", _acceptance_scope(_PSPP), _node("ProfitOptPct"), "int"),
    ("opspp_avg_profit", _acceptance_scope(_PSPP), _node("AvgProfit"), "int"),
    (
        "opspp_uniform_distr_changes",
        _acceptance_scope(_PSPP),
        _node("UniformDistrChanges"),
        "int",
    ),
    ("opspp_stdev_avg_profit", _acceptance_scope(_PSPP), _node("StdevAvgProfit"), "int"),
    (
        "opspp_eval_profit_opt_check",
        _acceptance_scope(_PSPP),
        _node("EvalProfitOptCheck"),
        "boolean",
    ),
    (
        "opspp_eval_avg_profit_check",
        _acceptance_scope(_PSPP),
        _node("EvalAvgProfitCheck"),
        "boolean",
    ),
    (
        "opspp_eval_uniform_distr_check",
        _acceptance_scope(_PSPP),
        _node("EvalUniformDistrCheck"),
        "boolean",
    ),
    (
        "opspp_eval_top_profit_check",
        _acceptance_scope(_PSPP),
        _node("EvalTopProfitCheck"),
        "boolean",
    ),
    # ── WhatIf ──
    ("wi_use", _tab_scope(_WI), _attr(_WI, "use"), "boolean"),
    (
        "wi_by_days_use",
        _method_scope(_WI, "ByDays"),
        _attr("Method", "use"),
        "boolean",
    ),
    (
        "wi_by_hours_use",
        _method_scope(_WI, "ByHours"),
        _attr("Method", "use"),
        "boolean",
    ),
    (
        "wi_by_months_use",
        _method_scope(_WI, "ByMonths"),
        _attr("Method", "use"),
        "boolean",
    ),
    (
        "wi_exclude_pct_biggest_pl_use",
        _method_scope(_WI, "ExcludePctTradesWithBiggestPl"),
        _attr("Method", "use"),
        "boolean",
    ),
    (
        "wi_exclude_pct_lowest_pl_use",
        _method_scope(_WI, "ExcludePctTradesWithLowestPl"),
        _attr("Method", "use"),
        "boolean",
    ),
    (
        "wi_exclude_short_trades_use",
        _method_scope(_WI, "ExcludeShortTrades"),
        _attr("Method", "use"),
        "boolean",
    ),
    (
        "wi_exclude_biggest_pl_use",
        _method_scope(_WI, "ExcludeTradesWithBiggestPl"),
        _attr("Method", "use"),
        "boolean",
    ),
    (
        "wi_exclude_lowest_pl_use",
        _method_scope(_WI, "ExcludeTradesWithLowestPl"),
        _attr("Method", "use"),
        "boolean",
    ),
    (
        "wi_exclude_overlapping_use",
        _method_scope(_WI, "ExludeOverlappingTrades"),
        _attr("Method", "use"),
        "boolean",
    ),
    (
        "wi_remove_balance_transactions_use",
        _method_scope(_WI, "RemoveBalanceTransactions"),
        _attr("Method", "use"),
        "boolean",
    ),
    (
        "wi_remove_pending_trades_use",
        _method_scope(_WI, "RemovePendingTrades"),
        _attr("Method", "use"),
        "boolean",
    ),
    ("wi_swap_use", _method_scope(_WI, "Swap"), _attr("Method", "use"), "boolean"),
    (
        "wi_take_every_second_trade_use",
        _method_scope(_WI, "TakeEverySecondTrade"),
        _attr("Method", "use"),
        "boolean",
    ),
    (
        "wi_take_max_trades_per_day_use",
        _method_scope(_WI, "TakeMaxTradesPerDay"),
        _attr("Method", "use"),
        "boolean",
    ),
    (
        "wi_use_fixed_lots_use",
        _method_scope(_WI, "UseFixedLots"),
        _attr("Method", "use"),
        "boolean",
    ),
    (
        "wi_exclude_biggest_pl_trades",
        _method_scope(_WI, "ExcludeTradesWithBiggestPl"),
        _param("Trades"),
        "int",
    ),
    (
        "wi_exclude_lowest_pl_trades",
        _method_scope(_WI, "ExcludeTradesWithLowestPl"),
        _param("Trades"),
        "int",
    ),
    (
        "wi_exclude_short_trades_pct",
        _method_scope(_WI, "ExcludeShortTrades"),
        _param("TradesPct"),
        "int",
    ),
    (
        "wi_exclude_short_trades_minutes",
        _method_scope(_WI, "ExcludeShortTrades"),
        _param("Minutes"),
        "int",
    ),
    (
        "wi_take_max_trades_per_day_trades",
        _method_scope(_WI, "TakeMaxTradesPerDay"),
        _param("Trades"),
        "int",
    ),
    ("wi_use_fixed_lots_size", _method_scope(_WI, "UseFixedLots"), _param("Size"), "float"),
    ("wi_swap_long", _method_scope(_WI, "Swap"), _param("swapLongInput"), "float"),
    ("wi_swap_short", _method_scope(_WI, "Swap"), _param("swapShortInput"), "float"),
    # ── SequentialOptimization (self-closing in real configs) ──
    ("so_use", _tab_scope(_SO), _attr(_SO, "use"), "boolean"),
)

# Bracket the value between two capture groups: every scoped leaf uses it.
_CROSSCHECK_REPLACEMENT = r"\g<1>{value}\g<2>"
_CROSSCHECK_SCOPES: dict[str, str] = {
    field: scope for field, scope, _leaf, _ft in _CROSSCHECK_FIELD_SPECS
}
_CROSSCHECK_FIELD_SPEC_BY_NAME: dict[str, tuple[str, str, str, str]] = {
    field: (field, scope, leaf, ft)
    for field, scope, leaf, ft in _CROSSCHECK_FIELD_SPECS
}


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

    # ── CrossChecks full parameter catalog (crosschecks-parameter-catalog) ──
    # Every leaf below is declared in _CROSSCHECK_FIELD_SPECS together with the
    # XML scope it owns, so repeated names never leak between tabs.
    # ── RetestOnAdditionalMarkets ──
    rc_use: bool | None = None
    rc_date_from: str | None = None
    rc_date_to: str | None = None
    rc_test_precision: int | None = None
    rc_session: str | None = None
    rc_slippage: int | None = None
    rc_min_dist: int | None = None
    rc_engine: str | None = None
    rc_symbol: str | None = None
    rc_timeframe: str | None = None
    rc_commission_method: str | None = None
    rc_check: str | None = None
    # ── WalkForwardOptimization ──
    wf_use: bool | None = None
    # ── RetestWithHigherPrecision ──
    hp_use: bool | None = None
    hp_precision: int | None = None
    hp_spread: int | None = None
    # ── MonteCarloRetest ──
    mcr_use: bool | None = None
    mcr_number_of_simulations: int | None = None
    mcr_history_data_use: bool | None = None
    mcr_history_probability_up: int | None = None
    mcr_history_probability_down: int | None = None
    mcr_history_max_change_up: int | None = None
    mcr_history_max_change_down: int | None = None
    mcr_min_distance_use: bool | None = None
    mcr_min_distance_min: float | None = None
    mcr_min_distance_max: float | None = None
    mcr_slippage_use: bool | None = None
    mcr_slippage_min: float | None = None
    mcr_slippage_max: float | None = None
    mcr_spread_use: bool | None = None
    mcr_spread_min: float | None = None
    mcr_spread_max: float | None = None
    mcr_starting_bar_use: bool | None = None
    mcr_starting_bar_max_change: int | None = None
    mcr_strategy_params_use: bool | None = None
    mcr_strategy_params_probability: int | None = None
    mcr_strategy_params_max_change: int | None = None
    mcr_strategy_params_symmetric: bool | None = None
    # ── WalkForwardMatrix ──
    wfm_use: bool | None = None
    wfm_param1_start: int | None = None
    wfm_param1_stop: int | None = None
    wfm_param1_step: int | None = None
    wfm_param2_start: int | None = None
    wfm_param2_stop: int | None = None
    wfm_param2_step: int | None = None
    wfm_threshold_pct: int | None = None
    wfm_rob_comb_rows: int | None = None
    wfm_rob_comb_cols: int | None = None
    wfm_rob_min_comb: int | None = None
    # WalkForwardMatrix declares its own copy of the WFO Settings leaves
    # (Build-Task1.xml); without these they were only reachable by leaking WFO's
    # values across tabs.
    wfm_period: int | None = None
    wfm_optimization: int | None = None
    wfm_optimize_periods: bool | None = None
    wfm_optimize_exit_types: bool | None = None
    wfm_max_tests: int | None = None
    # ── MonteCarloManipulation ──
    mcm_use: bool | None = None
    mcm_number_of_simulations: int | None = None
    mcm_trades_order_use: bool | None = None
    mcm_trades_order_method: str | None = None
    mcm_skip_trades_use: bool | None = None
    mcm_skip_trades_probability: int | None = None
    # ── OptProfileSysParamPermutation ──
    opspp_use: bool | None = None
    opspp_optim_periods: bool | None = None
    opspp_optim_exit_types: bool | None = None
    opspp_max_tests: int | None = None
    opspp_profit_opt_pct: int | None = None
    opspp_avg_profit: int | None = None
    opspp_uniform_distr_changes: int | None = None
    opspp_stdev_avg_profit: int | None = None
    opspp_eval_profit_opt_check: bool | None = None
    opspp_eval_avg_profit_check: bool | None = None
    opspp_eval_uniform_distr_check: bool | None = None
    opspp_eval_top_profit_check: bool | None = None
    # ── WhatIf ──
    wi_use: bool | None = None
    wi_by_days_use: bool | None = None
    wi_by_hours_use: bool | None = None
    wi_by_months_use: bool | None = None
    wi_exclude_pct_biggest_pl_use: bool | None = None
    wi_exclude_pct_lowest_pl_use: bool | None = None
    wi_exclude_short_trades_use: bool | None = None
    wi_exclude_biggest_pl_use: bool | None = None
    wi_exclude_lowest_pl_use: bool | None = None
    wi_exclude_overlapping_use: bool | None = None
    wi_remove_balance_transactions_use: bool | None = None
    wi_remove_pending_trades_use: bool | None = None
    wi_swap_use: bool | None = None
    wi_take_every_second_trade_use: bool | None = None
    wi_take_max_trades_per_day_use: bool | None = None
    wi_use_fixed_lots_use: bool | None = None
    wi_exclude_biggest_pl_trades: int | None = None
    wi_exclude_lowest_pl_trades: int | None = None
    wi_exclude_short_trades_pct: int | None = None
    wi_exclude_short_trades_minutes: int | None = None
    wi_take_max_trades_per_day_trades: int | None = None
    wi_use_fixed_lots_size: float | None = None
    wi_swap_long: float | None = None
    wi_swap_short: float | None = None
    # ── SequentialOptimization ──
    so_use: bool | None = None

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

    "main_test_values": (
        r'<MainTestValues[^>]*/>',
        r'<MainTestValues {main_test_values_xml} />',
        "dict",
    ),
    # ── Blocks bridge (REQ-18 / REQ-03) ──
    # Special-cased in _apply_build_config: probes the template for each
    # enabled block key and emits weight/use attributes on matching elements.
    "enabled_blocks": (
        r'<Block key="[^"]*"',
        r'<Block key="[^"]*"',
        "blocks",
    ),
    # block_weights is consumed inside the "blocks" branch via
    # _apply_block_entries when processing enabled_blocks (see guard in
    # _apply_build_config); it must be mapped here so every BuildConfig field
    # is covered, but is never applied as an independent field.
    "block_weights": (
        r'<Block key="[^"]*"',
        r'<Block key="[^"]*"',
        "blocks",
    ),
}

# CrossChecks leaves are registered with format_type "crosscheck" instead of
# being expanded inline: the same pattern works for a dozen fields, and the
# scoping — the part that actually prevents cross-tab corruption — stays in one
# reviewable table. _apply_build_config looks the scope up in
# _CROSSCHECK_SCOPES and rewrites inside that region only.
_BUILD_CONFIG_MAP.update(
    {
        field: (leaf, _CROSSCHECK_REPLACEMENT, "crosscheck")
        for field, _scope, leaf, _ft in _CROSSCHECK_FIELD_SPECS
    }
)

_CROSSCHECK_TABS_BY_PREFIX: dict[str, str] = {
    "rc_": _RC,
    "wf_": _WFO,
    "hp_": _HPR,
    "mcr_": _MCR,
    "wfm_": _WFM,
    "mcm_": _MCM,
    "opspp_": _PSPP,
    "wi_": _WI,
    "so_": _SO,
}
for _field, _scope, _leaf, _ft in _CROSSCHECK_FIELD_SPECS:
    for _prefix, _tab in _CROSSCHECK_TABS_BY_PREFIX.items():
        if _field.startswith(_prefix):
            _FIELD_TABS[_field] = _tab
            break



def get_tab_for_field(field_name: str) -> str:
    """Map a BuildConfig field name to its SQX tab name.

    Args:
        field_name: The BuildConfig dataclass field name.

    Returns:
        The SQX tab name (e.g. "MoneyManagement", "Ranking", "What to build").
    """
    _TAB_MAP: dict[str, str] = {
        # MoneyManagement
        "sl_required": "MoneyManagement",
        "pt_required": "MoneyManagement",
        "sl_fixed_pips": "MoneyManagement",
        "min_sl_pips": "MoneyManagement",
        "max_sl_pips": "MoneyManagement",
        "min_sl_money": "MoneyManagement",
        "max_sl_money": "MoneyManagement",
        "sl_atr": "MoneyManagement",
        "min_sl_atr_multiple": "MoneyManagement",
        "max_sl_atr_multiple": "MoneyManagement",
        "min_sl_atr_period": "MoneyManagement",
        "max_sl_atr_period": "MoneyManagement",
        "pt_fixed_pips": "MoneyManagement",
        "min_pt_pips": "MoneyManagement",
        "max_pt_pips": "MoneyManagement",
        "min_pt_money": "MoneyManagement",
        "max_pt_money": "MoneyManagement",
        "pt_atr": "MoneyManagement",
        "min_pt_atr_multiple": "MoneyManagement",
        "max_pt_atr_multiple": "MoneyManagement",
        "min_pt_atr_period": "MoneyManagement",
        "max_pt_atr_period": "MoneyManagement",
        "limit_slpt_rrr": "MoneyManagement",
        "limit_slpt_rrr_from": "MoneyManagement",
        "limit_slpt_rrr_to": "MoneyManagement",
        "sl_value_type": "MoneyManagement",
        "pt_value_type": "MoneyManagement",
        "sl_indicator_based": "MoneyManagement",
        "pt_indicator_based": "MoneyManagement",
        "sl_percent": "MoneyManagement",
        "min_sl_percent": "MoneyManagement",
        "max_sl_percent": "MoneyManagement",
        "pt_percent": "MoneyManagement",
        "min_pt_percent": "MoneyManagement",
        "max_pt_percent": "MoneyManagement",
        # Ranking
        "ranking_type": "Ranking",
        "ranking_avg_trades_min": "Ranking",
        "ranking_pf_min": "Ranking",
        "ranking_return_dd_min": "Ranking",
        "ranking_conditions_type": "Ranking",
        "max_strategies": "Ranking",
        "rankings_enabled": "Ranking",
        # What to build
        "min_conditions": "What to build",
        "max_conditions": "What to build",
        "min_exit_conditions": "What to build",
        "max_exit_conditions": "What to build",
        "min_period": "What to build",
        "max_period": "What to build",
        "min_shift": "What to build",
        "max_shift": "What to build",
        "market_sides": "What to build",
        "entry_symmetry": "What to build",
        "exit_symmetry": "What to build",
        # Build options
        "generations": "Build options",
        "population": "Build options",
        "islands": "Build options",
        "migration_modulo": "Build options",
        "migration_rate": "Build options",
        "init_generation_type": "Build options",
        "decimation_coef": "Build options",
        "evo_restart_on_finish": "Build options",
        "evo_restart_on_stagnation": "Build options",
        "evo_restart_stagnation_fitness_type": "Build options",
        "evo_restart_stagnation_generations": "Build options",
        "evo_in_sample_period_ratio": "Build options",
        "fresh_blood_replace_similar": "Build options",
        "fresh_blood_replace_weakest": "Build options",
        "fresh_blood_weakest_pct": "Build options",
        "fresh_blood_weakest_generations": "Build options",
        "filter_initial_population": "Build options",
        "evo_fitness_restart_type": "Build options",
        "evo_stagnation_restart_generations": "Build options",
        # Trading hours
        "session": "Trading hours",
        "exit_at_end_of_day": "Trading hours",
        "eod_exit_time": "Trading hours",
        "exit_on_friday": "Trading hours",
        "friday_exit_time": "Trading hours",
        "limit_time_range": "Trading hours",
        "signal_time_range_from": "Trading hours",
        "signal_time_range_to": "Trading hours",
        "exit_at_end_of_range": "Trading hours",
        "max_trades_per_day": "Trading hours",
        "reserved_bars": "Trading hours",
        "store_chart_data": "Trading hours",
        # ATMs
        "atms_enable": "ATMs",
        "atms_scale_out_type": "ATMs",
        "atms_size_decimals": "ATMs",
        "atms_min_size": "ATMs",
        # Parts to improve
        "entry_rules_symmetry": "Parts to improve",
        "entry_long_improvement": "Parts to improve",
        "entry_short_improvement": "Parts to improve",
        "exit_rules_symmetry": "Parts to improve",
        "exit_long_improvement": "Parts to improve",
        "exit_short_improvement": "Parts to improve",
        # CrossChecks
        "wf_period": "CrossChecks",
        "wf_optimization": "CrossChecks",
        "wf_param1": "CrossChecks",
        "wf_param2": "CrossChecks",
        "wf_optimize_periods": "CrossChecks",
        "wf_optimize_exit_types": "CrossChecks",
        "wf_max_tests": "CrossChecks",
        "wf_acceptance_threshold_pct": "CrossChecks",
        "wf_acceptance_min_conditions": "CrossChecks",
        "wf_acceptance_min_markets": "CrossChecks",
        "wf_acceptance_pf_min": "CrossChecks",
        "rc_spread": "CrossChecks",
        "rc_pf_min": "CrossChecks",
        "rc_min_conditions": "CrossChecks",
        "rc_min_markets": "CrossChecks",
        "main_test_values": "CrossChecks",
        # Building blocks
        "enabled_blocks": "Blocks bridge",
        "block_weights": "Blocks bridge",
    }
    tab = _TAB_MAP.get(field_name)
    if tab is not None:
        return tab
    # CrossChecks leaves are classified by the prefix table so the 92-entry
    # catalog cannot drift from its tab mapping (tests assert this round-trip).
    for _prefix, _crosscheck_tab in _CROSSCHECK_TABS_BY_PREFIX.items():
        if field_name.startswith(_prefix):
            return _crosscheck_tab
    return "Other"


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


def _apply_block_entries(
    template_xml: str, enabled: list[str], weights: dict[str, float]
) -> str:
    """Emit enabled-block entries into the template XML (REQ-03).

    Probes the template for each enabled block key; if any probe fails, logs a
    warning and returns the XML unchanged (no partial edits).

    Args:
        template_xml: The raw template XML string.
        enabled: Building-block names to enable in the template.
        weights: Per-block weight overrides (missing names default to 1.0).

    Returns:
        The modified XML string, or the original when a probe fails.
    """
    for name in enabled:
        if not re.search(rf'<Block key="{re.escape(name)}"', template_xml):
            logger.warning(
                "Blocks bridge: template has no <Block key=\"%s\"> — leaving XML unchanged",
                name,
            )
            return template_xml

    xml = template_xml
    for name in enabled:
        weight = weights.get(name, 1.0)
        xml = re.sub(
            rf'(<Block key="{re.escape(name)}"[^>]*?weight=")[^"]*(")',
            rf'\g<1>{weight:g}\g<2>',
            xml,
            count=1,
        )
        xml = re.sub(
            rf'(<Block key="{re.escape(name)}"[^>]*?use=")false(")',
            r'\g<1>true\g<2>',
            xml,
            count=1,
        )
    return xml


def _apply_in_scope(
    xml: str, field_name: str, scope: str, leaf: str, replacement: str
) -> str:
    """Rewrite ``leaf`` only inside the region ``scope`` matches.

    A missing scope or a leaf that does not match inside its own region means
    the field targets XML this build does not have. Rather than silently
    corrupting a sibling tab — or rewriting every occurrence in the document —
    the original XML is preserved and the situation is logged.
    """
    region = re.search(scope, xml, re.DOTALL)
    if region is None:
        logger.warning(
            "BuildConfig field '%s': no matching XML region for its tab scope — "
            "leaving XML unchanged. The field likely does not exist in this SQX build.",
            field_name,
        )
        return xml

    patched = re.sub(leaf, replacement, region.group(0), flags=re.DOTALL)
    if patched == region.group(0):
        logger.warning(
            "BuildConfig field '%s': pattern found no match inside its own tab scope — "
            "leaving XML unchanged.",
            field_name,
        )
    return xml[: region.start()] + patched + xml[region.end() :]


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
        if field_name == "block_weights":
            # Consumed inside the "blocks" branch via _apply_block_entries when
            # processing enabled_blocks; skip to avoid double application.
            continue

        value = getattr(config, field_name, None)
        if value is None:
            continue

        if format_type == "dict" and field_name == "main_test_values":
            # Special handling for MainTestValues dict
            values_xml = _build_main_test_values_xml(value)
            xml = re.sub(pattern, f'<MainTestValues {values_xml} />', xml)
            continue

        if format_type == "blocks":
            # Blocks bridge (REQ-03): emit block entries via template probe.
            xml = _apply_block_entries(xml, value, config.block_weights or {})
            continue

        if format_type == "crosscheck":
            # The map records the "crosscheck" marker, not the scalar type, so
            # the real type comes from the spec table. Formatting with the
            # marker would emit Python's True/False instead of SQX's true/false.
            spec = _CROSSCHECK_FIELD_SPEC_BY_NAME[field_name]
            formatted = _format_build_config_value(value, spec[3])
            xml = _apply_in_scope(
                xml,
                field_name,
                spec[1],
                pattern,
                replacement.format(value=formatted),
            )
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

    # 1. Data section: symbol, timeframe, date range.
    # The data registry names symbols by their M1 ROOT (EURUSD_M1_dukas) —
    # H1/D1 are derived .dat files inside that root dir, never standalone
    # symbols. The chart must reference the root symbol so the build finds
    # data; the timeframe attribute selects the derived bars (H1).
    try:
        chart_symbol = resolve_symbol(symbol, "M1", "dukascopy")
    except ValueError:
        # Symbol not expressible in the registry naming (e.g. non-FX or
        # lowercase); fall back to the M1-root convention so the build
        # still targets an existing data directory.
        chart_symbol = f"{symbol.upper()}_M1_dukas"

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
