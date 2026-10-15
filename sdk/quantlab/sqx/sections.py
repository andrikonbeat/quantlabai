"""Cross-checks and shared settings sections parser/emitter.

Mirrors the 145 engine's sections.py: parsers and emitters for each
shared settings section (cross-checks, money management, trading options,
costs, fitness, optimization, what-to-build).

XML shapes mirror the UI services under internal/plugins/Settings*/
and docs/custom-projects/task-settings/shared-sections.md.
Stdlib only.
"""

from __future__ import annotations

import copy
import re
from datetime import date
from typing import Any
from xml.etree import ElementTree as ET


# ── Cross-checks constants (mirror sections.pyc) ───────────────────────────

CROSS_CHECKS = frozenset({
    "monte_carlo_retest", "MonteCarloRetest", "mc_retest",
    "monte_carlo_manipulation", "MonteCarloManipulation", "mc_manipulation",
    "monte_carlo_trades", "additional_markets", "RetestOnAdditionalMarkets",
    "retest_on_additional_markets", "higher_precision", "RetestWithHigherPrecision",
    "retest_with_higher_precision", "walk_forward", "WalkForwardOptimization",
    "wfo", "walk_forward_optimization", "wf", "walk_forward_matrix",
    "WalkForwardMatrix", "wfm", "opt_profile_sys_param_permutation",
    "OptProfileSysParamPermutation", "opspp",
})

CROSS_CHECK_ALIASES = {
    "mc_retest": "MonteCarloRetest",
    "monte_carlo_retest": "MonteCarloRetest",
    "mc_manipulation": "MonteCarloManipulation",
    "monte_carlo_manipulation": "MonteCarloManipulation",
    "additional_markets": "RetestOnAdditionalMarkets",
    "retest_on_additional_markets": "RetestOnAdditionalMarkets",
    "higher_precision": "RetestWithHigherPrecision",
    "retest_with_higher_precision": "RetestWithHigherPrecision",
    "walk_forward": "WalkForwardOptimization",
    "walk_forward_optimization": "WalkForwardOptimization",
    "wfo": "WalkForwardOptimization",
    "walk_forward_matrix": "WalkForwardMatrix",
    "wfm": "WalkForwardMatrix",
    "opt_profile_sys_param_permutation": "OptProfileSysParamPermutation",
    "opspp": "OptProfileSysParamPermutation",
}

_CC_SECTION_KEYS = frozenset({
    "use", "date_from", "date_to", "test_precision", "session",
    "slippage", "min_dist", "engine", "symbol", "timeframe",
    "commission_method", "check", "min_conditions", "min_markets",
    "spread", "period", "optimization", "param1", "param2",
    "optimize_periods", "optimize_exit_types", "max_tests",
    "acceptance_threshold_pct", "acceptance_min_conditions",
    "acceptance_min_markets", "acceptance_pf_min", "profit_opt_pct",
    "avg_profit", "uniform_distr_changes", "stdev_avg_profit",
    "eval_profit_opt_check", "eval_avg_profit_check",
    "eval_uniform_distr_check", "eval_top_profit_check",
    "precision", "number_of_simulations",
    "history_data_use", "history_probability_up", "history_probability_down",
    "history_max_change_up", "history_max_change_down",
    "min_distance_use", "min_distance_min", "min_distance_max",
    "slippage_use", "slippage_min", "slippage_max",
    "spread_use", "spread_min", "spread_max",
    "starting_bar_use", "starting_bar_max_change",
    "strategy_params_use", "strategy_params_probability",
    "strategy_params_max_change", "strategy_params_symmetric",
    "param1_start", "param1_stop", "param1_step",
    "param2_start", "param2_stop", "param2_step",
    "threshold_pct", "rob_comb_rows", "rob_comb_cols", "rob_min_comb",
    "optim_periods", "optim_exit_types",
    "trades_order_use", "trades_order_method", "skip_trades_use",
    "skip_trades_probability",
    "by_days_use", "by_hours_use", "by_months_use",
    "exclude_pct_biggest_pl_use", "exclude_pct_lowest_pl_use",
    "exclude_short_trades_use", "exclude_biggest_pl_use",
    "exclude_lowest_pl_use", "exclude_overlapping_use",
    "remove_balance_transactions_use", "remove_pending_trades_use",
    "swap_use", "take_every_second_trade_use",
    "take_max_trades_per_day_use", "use_fixed_lots_use",
    "exclude_biggest_pl_trades", "exclude_lowest_pl_trades",
    "exclude_short_trades_pct", "exclude_short_trades_minutes",
    "take_max_trades_per_day_trades", "use_fixed_lots_size",
    "swap_long", "swap_short",
})

MM_METHODS = frozenset({
    "FixedSize", "RiskFixedBalancePct", "RiskFixedPctOfAccount",
    "ATRRiskBasedSizing", "FixedAmount", "SimpleMartingaleMM",
    "StocksSizeByPrice", "CryptoSizeByPrice",
})


# ── Sample / direction / plType maps (shared-sections.md) ──────────────────

_SAMPLE_TYPE = {"full": "127", "is": "10", "oos": "20"}
_DIRECTION = {"both": "0", "long": "1", "short": "-1"}
_PL_TYPE = {"money": "10", "pct": "20", "pips": "30"}

# Column metadata: column -> (format, plType-default). class == column.
_COLUMN_FORMAT = {
    "ProfitFactor": "Decimal2",
    "NetProfit": "Decimal2PL",
    "NumberOfTrades": "Integer",
    "DrawdownPct": "Decimal2Pct",
    "ReturnDDRatio": "Decimal2",
    "AvgTradesPerMonth": "Integer",
    "SharpeRatio": "Decimal2",
    "Return": "Decimal2Pct",
    "MaxDrawdown": "Decimal2",
    "WinPct": "Decimal2Pct",
    "AvgTrade": "Decimal2PL",
    "Expectancy": "Decimal2PL",
    "ProfitPerMonth": "Decimal2PL",
}

_OPS = {">=", ">", "<=", "<", "==", "!="}


# ── Small helpers ──────────────────────────────────────────────────────────


def _resolve_cc_name(name: str) -> str:
    """Normalize cross-check name to canonical form."""
    return CROSS_CHECK_ALIASES.get(name.lower(), name)


def _check_keys(obj: dict, allowed: frozenset, path: str) -> None:
    extra = set(obj.keys()) - allowed
    if extra:
        raise ValueError(f"{path}: unknown key(s): {', '.join(sorted(extra))}")


def _bool_str(v: Any) -> str:
    if isinstance(v, str):
        return "true" if v.lower() in ("true", "1", "yes") else "false"
    return "true" if v else "false"


def _hhmm_to_seconds(v: Any) -> str:
    """'20:40' or 2040 or 74400 -> seconds-since-midnight string."""
    if isinstance(v, int):
        # Heuristic: > 2400 is already seconds; else HHMM int.
        if v > 2400:
            return str(v)
        h, m = divmod(v, 100)
        return str(h * 3600 + m * 60)
    s = str(v).strip()
    if ":" in s:
        h, m = s.split(":")[:2]
        return str(int(h) * 3600 + int(m) * 60)
    if s.isdigit():
        return _hhmm_to_seconds(int(s))
    return s


def _sq_date(v: str) -> str:
    """'2010-01-01' -> '2010.1.1' (yyyy.M.d)."""
    d = date.fromisoformat(v.replace(".", "-"))
    return f"{d.year}.{d.month}.{d.day}"


def _oos_range(date_from: str, date_to: str, oos_pct: int) -> tuple[str, str]:
    """Compute OOS date window: last oos_pct% of [from, to]."""
    a = date.fromisoformat(date_from.replace(".", "-"))
    b = date.fromisoformat(date_to.replace(".", "-"))
    total = (b - a).days
    oos_days = int(total * oos_pct / 100)
    start = b - __import__("datetime").timedelta(days=oos_days)
    return f"{start.year}.{start.month}.{start.day}", f"{b.year}.{b.month}.{b.day}"


def _get_or_create(parent: ET.Element, tag: str) -> ET.Element:
    el = parent.find(tag)
    if el is None:
        el = ET.SubElement(parent, tag)
    return el


# ── Parsers ────────────────────────────────────────────────────────────────


def parse_cross_checks(cc_dict: dict) -> dict:
    """Parse cross-checks dict into normalized internal format."""
    if not cc_dict:
        return {}
    normalized = {}
    for section_name, section_spec in cc_dict.items():
        if section_spec is None:
            continue
        if section_name == "all":
            normalized["all"] = section_spec
            continue
        canonical = _resolve_cc_name(section_name)
        if not isinstance(section_spec, dict):
            raise ValueError(f"Cross-check section '{section_name}' must be dict")
        _check_keys(section_spec, _CC_SECTION_KEYS, f"cross_checks.{section_name}")
        if "use" not in section_spec:
            # Default: explicit use required except when section disabled via False
            if section_spec is False:
                normalized[canonical] = {"use": False}
                continue
            raise ValueError(f"Cross-check section '{canonical}' missing 'use' key")
        normalized[canonical] = dict(section_spec)
    return normalized


def parse_money_management(mm_dict: dict) -> dict:
    if not mm_dict:
        return {}
    method = mm_dict.get("method")
    if method and method not in MM_METHODS and method != "fixed_size":
        raise ValueError(f"Invalid MM method: {method}")
    return dict(mm_dict)


def parse_trading_options(to_dict: dict) -> dict:
    if not to_dict:
        return {}
    return dict(to_dict)


def parse_costs(costs_dict: dict) -> dict:
    if not costs_dict:
        return {}
    return dict(costs_dict)


def parse_fitness(fitness: Any) -> str | None:
    if fitness is None:
        return None
    return str(fitness)


def parse_what_to_build(wtb_dict: dict) -> dict:
    if not wtb_dict:
        return {}
    return dict(wtb_dict)


def parse_stop(stop_dict: dict) -> dict:
    """Parse stop section from spec dict.
    """
    if stop_dict is None:
        return {}
    # Check for 'type' key FIRST - empty dict is valid input but must have 'type'
    try:
        _ = stop_dict["type"]
    except KeyError:
        raise ValueError("Stop section missing 'type'")
    return dict(stop_dict)


def parse_range(range_dict: dict) -> dict:
    if not range_dict:
        return {}
    if "from" not in range_dict or "to" not in range_dict:
        raise ValueError("Range must have 'from' and 'to'")
    return dict(range_dict)


# ── Emitters ───────────────────────────────────────────────────────────────

# -- Data/Setup (engine, symbol, timeframe, range, costs) --

def emit_data_setup(
    settings: ET.Element,
    engine: str | None = None,
    symbol: str | None = None,
    timeframe: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    test_precision: int | None = None,
    session: str | None = None,
    slippage: int | None = None,
    min_dist: int | None = None,
    spread: int | None = None,
) -> None:
    """Emit main Setup attrs + Chart. Data/Setups/Setup is a hard requirement."""
    data = settings.find("Data")
    if data is None:
        data = ET.SubElement(settings, "Data")
    setups = data.find("Setups")
    if setups is None:
        setups = ET.SubElement(data, "Setups")
    setup = setups.find("Setup")
    if setup is None:
        setup = ET.SubElement(setups, "Setup")
    if date_from is not None:
        setup.set("dateFrom", _sq_date(date_from))
    if date_to is not None:
        setup.set("dateTo", _sq_date(date_to))
    if test_precision is not None:
        setup.set("testPrecision", str(test_precision))
    if session is not None:
        setup.set("session", str(session))
    if slippage is not None:
        setup.set("slippage", str(slippage))
    if min_dist is not None:
        setup.set("minDist", str(min_dist))
    if engine is not None:
        setup.set("engine", str(engine))
    chart = setup.find("Chart")
    if chart is None:
        chart = ET.SubElement(setup, "Chart")
    if symbol is not None:
        chart.set("symbol", str(symbol))
    if timeframe is not None:
        chart.set("timeframe", str(timeframe))
    if spread is not None:
        chart.set("spread", str(spread))


def emit_oos(settings: ET.Element, date_from: str, date_to: str, oos_pct: int) -> None:
    """Emit <OutOfSample><Range dateFrom dateTo type=oos/> (computed window)."""
    if not oos_pct:
        return
    data = settings.find("Data")
    if data is None:
        data = ET.SubElement(settings, "Data")
    oos = data.find("OutOfSample")
    if oos is None:
        oos = ET.SubElement(data, "OutOfSample")
    for old in list(oos.findall("Range")):
        oos.remove(old)
    start, end = _oos_range(date_from, date_to, int(oos_pct))
    r = ET.SubElement(oos, "Range")
    r.set("dateFrom", start)
    r.set("dateTo", end)
    r.set("type", "oos")


# -- Rankings: MaxStrategies / StopCondition / Conditions / Fitness --

def _column_value(column: str, sample: str, result_type: str = "main") -> ET.Element:
    fmt = _COLUMN_FORMAT.get(column, "Decimal2")
    cv = ET.Element("Column-Value")
    cv.set("column", column)
    cv.set("columnType", "0")
    cv.set("format", fmt)
    cv.set("resultType", result_type)
    cv.set("direction", "0")
    cv.set("sampleType", _SAMPLE_TYPE.get(sample, "127"))
    cv.set("plType", _PL_TYPE.get("money", "10"))
    cv.set("confidenceLevel", "50")
    cv.set("market", "1")
    cv.set("subresult", "30")
    cv.set("pctRatio", "0")
    cv.set("class", column)
    return cv


def emit_max_strategies(settings: ET.Element, n: int) -> None:
    rk = settings.find("Rankings")
    if rk is None:
        return
    ms = rk.find("MaxStrategies")
    if ms is None:
        ms = ET.SubElement(rk, "MaxStrategies")
    ms.text = str(n)


def emit_stop(settings: ET.Element, stop: dict) -> None:
    """StopCondition: passed-count | databank-full | time-limit | never."""
    rk = settings.find("Rankings")
    if rk is None:
        return
    sc = rk.find("StopCondition")
    if sc is None:
        sc = ET.SubElement(rk, "StopCondition")
    t = stop.get("type", "databank-full")
    if t == "passed-count":
        sc.set("type", "databank-full")
        sc.set("passedStrategies", str(stop.get("count", 100)))
    elif t == "never":
        sc.set("type", "never")
    elif t == "databank-full":
        sc.set("type", "databank-full")
        if "count" in stop:
            sc.set("passedStrategies", str(stop["count"]))
    elif t == "time-limit":
        sc.set("type", "time-limit")
        sc.set("days", str(stop.get("days", 0)))
        sc.set("hours", str(stop.get("hours", 0)))
        sc.set("minutes", str(stop.get("minutes", 0)))
    else:
        raise ValueError(f"Unknown stop type: {t}")


def emit_rankings(settings: ET.Element, rankings: list[dict]) -> None:
    """Rebuild Rankings/Conditions from spec list (clears template defaults)."""
    if not rankings:
        return
    rk = settings.find("Rankings")
    if rk is None:
        rk = ET.SubElement(settings, "Rankings")
    conds = rk.find("Conditions")
    if conds is None:
        conds = ET.SubElement(rk, "Conditions")
    for old in list(conds):
        conds.remove(old)
    for r in rankings:
        op = r.get("op", ">=")
        if op not in _OPS:
            raise ValueError(f"Invalid ranking op: {op}")
        sample = r.get("sample", "full")
        cond = ET.SubElement(conds, "Condition")
        cond.set("use", "true")
        left = ET.SubElement(cond, "Left-Side")
        left.set("valueType", "column")
        left.append(_column_value(r["column"], sample, "main"))
        comp = ET.SubElement(cond, "Comparator")
        comp.set("value", op)
        right = ET.SubElement(cond, "Right-Side")
        right.set("valueType", "numeric")
        nv = ET.SubElement(right, "Numeric-Value")
        nv.set("value", str(r["value"]))


def emit_fitness(settings: ET.Element, fitness: str | None) -> None:
    """FitnessCriteria/Settings/Ranking[@type]."""
    if not fitness:
        return
    rk = settings.find("Rankings")
    if rk is None:
        return
    fc = rk.find("FitnessCriteria")
    if fc is None:
        fc = ET.SubElement(rk, "FitnessCriteria")
    fcs = fc.find("Settings")
    if fcs is None:
        fcs = ET.SubElement(fc, "Settings")
    r = fcs.find("Ranking")
    if r is None:
        r = ET.SubElement(fcs, "Ranking")
    r.set("type", str(fitness))


# -- Money management --

_MM_PARAM_KEYS = {
    "FixedSize": ("Size",),
    "RiskFixedBalancePct": ("Risk", "Decimals", "LotsIfNoMM", "MaxLots"),
    "RiskFixedPctOfAccount": ("Risk", "StopLossInPips", "Decimals", "LotsIfNoMM", "MaxLots"),
    "ATRRiskBasedSizing": ("Risk", "ATRPeriod", "ATRMult", "Decimals", "LotsIfNoMM", "MaxLots"),
    "FixedAmount": ("RiskedMoney", "Decimals", "LotsIfNoMM", "MaxLots"),
    "SimpleMartingaleMM": ("LotsStart", "LotsMultiplier", "LotsReset", "Decimals", "SeparateByDirection"),
}

_MM_SPEC_TO_METHOD = {
    "fixed_size": "FixedSize",
}

_MM_SPEC_TO_PARAM = {
    "size": "Size",
    "risk_pct": "Risk",
    "lots_start": "LotsStart",
    "lots_multiplier": "LotsMultiplier",
    "risked_money": "RiskedMoney",
}


def emit_money_management(settings: ET.Element, mm: dict) -> None:
    """RiskMoneyManagement: Method[@type] use toggle + Params + InitialCapital + maxDrawdown."""
    if not mm:
        return
    rmm = settings.find("RiskMoneyManagement")
    if rmm is None:
        rmm = ET.SubElement(settings, "RiskMoneyManagement")
    money = rmm.find("MoneyManagement")
    if money is None:
        money = ET.SubElement(rmm, "MoneyManagement")

    method_name = mm.get("method", "fixed_size")
    method_type = _MM_SPEC_TO_METHOD.get(method_name, method_name)
    if method_type not in MM_METHODS and method_type not in (
        "RiskFixedPctOfAccount", "ATRRiskBasedSizing", "FixedAmount",
        "SimpleMartingaleMM", "StocksSizeByPrice",
    ):
        raise ValueError(f"Unknown MM method: {method_name}")

    # Toggle: requested method use=true, all others use=false
    for m in list(money.findall("Method")):
        m.set("use", "true" if m.get("type") == method_type else "false")
    target = None
    for m in money.findall("Method"):
        if m.get("type") == method_type:
            target = m
            break
    if target is None:
        target = ET.SubElement(money, "Method")
        target.set("type", method_type)
        target.set("use", "true")
        ET.SubElement(target, "Params")

    params = target.find("Params")
    if params is None:
        params = ET.SubElement(target, "Params")

    def set_param(key: str, value: Any) -> None:
        p = None
        for cand in params.findall("Param"):
            if cand.get("key") == key:
                p = cand
                break
        if p is None:
            p = ET.SubElement(params, "Param")
            p.set("key", key)
            p.set("className", method_type)
        p.text = str(value)

    for spec_key, value in mm.items():
        if value is None or spec_key in ("method", "initial_capital", "max_drawdown"):
            continue
        param_key = _MM_SPEC_TO_PARAM.get(spec_key, spec_key)
        set_param(param_key, value)

    if "initial_capital" in mm and mm["initial_capital"] is not None:
        ic = money.find("InitialCapital")
        if ic is None:
            ic = ET.SubElement(money, "InitialCapital")
        ic.text = str(mm["initial_capital"])

    if "max_drawdown" in mm and mm["max_drawdown"] is not None:
        rm = rmm.find("RiskManagement")
        if rm is None:
            rm = ET.SubElement(rmm, "RiskManagement")
        rm.set("maxDrawdown", str(mm["max_drawdown"]))


# -- Trading options --

_TO_PARAM_KEYS = {
    "exit_at_end_of_day": "ExitAtEndOfDay",
    "eod_exit_time": "EODExitTime",
    "exit_on_friday": "ExitOnFriday",
    "friday_exit_time": "FridayExitTime",
    "limit_time_range": "LimitTimeRange",
    "signal_time_range_from": "SignalTimeRangeFrom",
    "signal_time_range_to": "SignalTimeRangeTo",
    "exit_at_end_of_range": "ExitAtEndOfRange",
    "max_trades_per_day": "MaxTradesPerDay",
    "session": "Session",
    "reserved_bars": "ReservedBars",
    "store_chart_data": "StoreChartData",
    "min_sl": None, "max_sl": None, "min_pt": None, "max_pt": None,
}


def emit_trading_options(settings: ET.Element, to: dict) -> None:
    """Options/BuildTradingOptions/Params/Param[@key]."""
    if not to:
        return
    opts = settings.find("Options")
    if opts is None:
        opts = ET.SubElement(settings, "Options")
    bto = opts.find("BuildTradingOptions")
    if bto is None:
        bto = ET.SubElement(opts, "BuildTradingOptions")
    params = bto.find("Params")
    if params is None:
        params = ET.SubElement(bto, "Params")

    def set_param(key: str, value: Any) -> None:
        p = None
        for cand in params.findall("Param"):
            if cand.get("key") == key:
                p = cand
                break
        if p is None:
            p = ET.SubElement(params, "Param")
            p.set("key", key)
            p.set("className", key)
        if isinstance(value, bool):
            p.text = "true" if value else "false"
        else:
            p.text = str(value)

    # SL/PT range keys live in WhatToBuild/SLPTOptions, not in Params.
    slpt_range = {
        "min_sl": "MinSLInPips", "max_sl": "MaxSLInPips",
        "min_pt": "MinPTInPips", "max_pt": "MaxPTInPips",
    }
    slpt_vals = {}
    for spec_key, value in to.items():
        if value is None:
            continue
        if spec_key in slpt_range:
            slpt_vals[slpt_range[spec_key]] = value
            continue
        param_key = _TO_PARAM_KEYS.get(spec_key, spec_key)
        if param_key is None:
            continue  # handled by costs emitter
        if spec_key in ("friday_exit_time", "eod_exit_time"):
            value = _hhmm_to_seconds(value)
        set_param(param_key, value)

    if slpt_vals:
        w = settings.find("WhatToBuild")
        if w is None:
            w = ET.SubElement(settings, "WhatToBuild")
        slpt = w.find("SLPTOptions")
        if slpt is None:
            slpt = ET.SubElement(w, "SLPTOptions")
        for tag, value in slpt_vals.items():
            el = slpt.find(tag)
            if el is None:
                el = ET.SubElement(slpt, tag)
            el.text = str(value)


# -- What-to-build --

def emit_what_to_build(settings: ET.Element, wtb: dict) -> None:
    """WhatToBuild: MarketSides, symmetries, RulesComplexity/Chart, SLPTOptions."""
    if not wtb:
        return
    w = settings.find("WhatToBuild")
    if w is None:
        w = ET.SubElement(settings, "WhatToBuild")

    if "market_sides" in wtb and wtb["market_sides"] is not None:
        ms = w.find("MarketSides")
        if ms is None:
            ms = ET.SubElement(w, "MarketSides")
        ms.set("type", str(wtb["market_sides"]))
        for sym_key, tag in (("entry_symmetry", "EntrySymmetry"),
                             ("exit_symmetry", "ExitSymmetry")):
            if sym_key in wtb and wtb[sym_key] is not None:
                el = ms.find(tag)
                if el is None:
                    el = ET.SubElement(ms, tag)
                el.text = _bool_str(wtb[sym_key])

    # RulesComplexity/Chart ranges
    rc_map = {
        "conditions": ("minConditions", "maxConditions"),
        "exit_conditions": ("minExitConditions", "maxExitConditions"),
        "period": ("minPeriod", "maxPeriod"),
        "shift": ("minShift", "maxShift"),
    }
    need_chart = any(k in wtb for k in rc_map)
    if need_chart:
        rc = w.find("RulesComplexity")
        if rc is None:
            rc = ET.SubElement(w, "RulesComplexity")
        chart = rc.find("Chart")
        if chart is None:
            chart = ET.SubElement(rc, "Chart")
        for spec_key, (mn, mx) in rc_map.items():
            if spec_key in wtb and wtb[spec_key] is not None:
                vals = wtb[spec_key]
                if isinstance(vals, (list, tuple)) and len(vals) == 2:
                    chart.set(mn, str(vals[0]))
                    chart.set(mx, str(vals[1]))
                else:
                    chart.set(mn, str(vals))

    # SLPTOptions children (element text)
    slpt = w.find("SLPTOptions")
    if slpt is None:
        slpt = ET.SubElement(w, "SLPTOptions")
    slpt_map = {
        "sl_required": "SLRequired", "sl_fixed_pips": "SLFixedPips",
        "sl_atr": "SLATR", "pt_required": "PTRequired",
        "pt_fixed_pips": "PTFixedPips", "pt_atr": "PTATR",
        "sl_indicator_based": "SLIndicatorBased",
        "pt_indicator_based": "PTIndicatorBased",
        "sl_percent": "SLPercent", "pt_percent": "PTPercent",
        "limit_slpt_rrr": "LimitSLPTRRR",
        "sl_value_type": "SLValueType", "pt_value_type": "PTValueType",
    }
    range_map = {
        "min_sl": "MinSLInPips", "max_sl": "MaxSLInPips",
        "min_pt": "MinPTInPips", "max_pt": "MaxPTInPips",
    }
    for spec_key, tag in slpt_map.items():
        if spec_key in wtb and wtb[spec_key] is not None:
            el = slpt.find(tag)
            if el is None:
                el = ET.SubElement(slpt, tag)
            v = wtb[spec_key]
            el.text = _bool_str(v) if isinstance(v, bool) else str(v)
    for spec_key, tag in range_map.items():
        if spec_key in wtb and wtb[spec_key] is not None:
            el = slpt.find(tag)
            if el is None:
                el = ET.SubElement(slpt, tag)
            el.text = str(wtb[spec_key])


# -- Cross-checks --

# Canonical section -> (Settings children spec, Acceptance spec)
# Settings value spec: list of (kind, path, leaf, conv) where kind in text/attr
_CC_SETTINGS_SPEC: dict[str, list[tuple[str, str, str]]] = {
    "RetestWithHigherPrecision": [
        ("text", "Settings/Precision", "Precision"),
        ("text", "Settings/Spread", "Spread"),
    ],
    "MonteCarloRetest": [
        ("text", "Settings/NumberOfSimulations", "NumberOfSimulations"),
    ],
    "MonteCarloManipulation": [
        ("text", "Settings/NumberOfSimulations", "NumberOfSimulations"),
    ],
    "WalkForwardOptimization": [
        ("attr", "Settings/WalkForward", "period"),
        ("attr", "Settings/WalkForward", "optimization"),
        ("text", "Settings/MaxTests", "MaxTests"),
    ],
    "WalkForwardMatrix": [
        ("attr", "Settings/WalkForward", "period"),
        ("attr", "Settings/WalkForward", "optimization"),
        ("text", "Settings/MaxTests", "MaxTests"),
    ],
    "OptProfileSysParamPermutation": [
        ("text", "Settings/MaxTests", "MaxTests"),
    ],
}

# spec-key -> (section, kind, path, leaf)
_CC_KEY_MAP: dict[str, tuple[str, str, str, str]] = {
    "precision": ("RetestWithHigherPrecision", "text", "Settings/Precision", "Precision"),
    "spread": ("RetestWithHigherPrecision", "text", "Settings/Spread", "Spread"),
}

_CC_USE_ONLY = frozenset({
    "RetestOnAdditionalMarkets", "RetestWithHigherPrecision",
    "MonteCarloRetest", "MonteCarloManipulation",
    "WalkForwardOptimization", "WalkForwardMatrix",
    "OptProfileSysParamPermutation", "WhatIf", "SequentialOptimization",
})


def _cc_section(settings: ET.Element, name: str) -> ET.Element | None:
    cc = settings.find("CrossChecks")
    if cc is None:
        return None
    return cc.find(name)


def _ensure_cc_section(settings: ET.Element, name: str) -> ET.Element:
    cc = settings.find("CrossChecks")
    if cc is None:
        cc = ET.SubElement(settings, "CrossChecks")
    sec = cc.find(name)
    if sec is None:
        sec = ET.SubElement(cc, name)
    return sec


def emit_cross_checks(settings: ET.Element, cross_checks: dict) -> None:
    """Emit CrossChecks sections: use toggles + Settings + AcceptanceSettings.

    Only touches sections named in the spec; everything else keeps the
    template default byte-for-byte (except neutralized foreign data, handled
    by the caller).
    """
    if not cross_checks:
        return
    parsed = parse_cross_checks(cross_checks)
    if parsed.get("all") is True:
        cc = settings.find("CrossChecks")
        if cc is not None:
            for sec in list(cc):
                if sec.tag in _CC_USE_ONLY:
                    sec.set("use", "true")
    for name, spec in parsed.items():
        if name == "all":
            continue
        if spec is False or (isinstance(spec, dict) and spec.get("use") is False):
            sec = _cc_section(settings, name)
            if sec is not None:
                sec.set("use", "false")
            continue
        if not isinstance(spec, dict):
            continue
        sec = _ensure_cc_section(settings, name)
        if "use" in spec:
            sec.set("use", _bool_str(spec["use"]))
        # Generic scalar keys: try Settings/<Key> text, then known paths
        for key, value in spec.items():
            if value is None or key == "use":
                continue
            if key == "conditions":
                _emit_cc_conditions(sec, name, value)
                continue
            _emit_cc_scalar(sec, name, key, value)


def _emit_cc_scalar(sec: ET.Element, name: str, key: str, value: Any) -> None:
    # 1. Known mapped paths
    mapped = _CC_KEY_MAP.get(key)
    if mapped and mapped[0] == name:
        _, kind, path, leaf = mapped
        _set_cc_value(sec, path, leaf, kind, value)
        return
    # 2. Settings/<Capitalized> text child
    cap = key[0].upper() + key[1:] if key else key
    st = sec.find("Settings")
    if st is None:
        st = ET.SubElement(sec, "Settings")
    child = st.find(cap)
    if child is not None:
        child.text = _bool_str(value) if isinstance(value, bool) else str(value)
        return
    # 3. WalkForward attrs (period/optimization/param1/param2)
    if key in ("period", "optimization", "param1", "param2"):
        wf = st.find("WalkForward")
        if wf is not None:
            if key in ("param1", "param2"):
                p = wf.find("Param1" if key == "param1" else "Param2")
                if p is None:
                    p = ET.SubElement(wf, "Param1" if key == "param1" else "Param2")
                p.set("value", str(value))
            else:
                wf.set(key, str(value))
            return
    # 4. AcceptanceSettings scalar
    acc = sec.find("AcceptanceSettings")
    if acc is None:
        acc = ET.SubElement(sec, "AcceptanceSettings")
    child = acc.find(cap)
    if child is not None:
        child.text = _bool_str(value) if isinstance(value, bool) else str(value)
        return
    # 5. Unknown key for this section: create under Settings (strict specs
    #    already validated the key name, so this is a template-shape gap)
    child = ET.SubElement(st, cap)
    child.text = _bool_str(value) if isinstance(value, bool) else str(value)


def _set_cc_value(sec: ET.Element, path: str, leaf: str, kind: str, value: Any) -> None:
    parts = path.split("/")
    parent = sec
    for p in parts:
        nxt = parent.find(p)
        if nxt is None:
            nxt = ET.SubElement(parent, p)
        parent = nxt
    if kind == "text":
        leaf_el = parent.find(leaf)
        if leaf_el is None:
            leaf_el = ET.SubElement(parent, leaf)
        leaf_el.text = _bool_str(value) if isinstance(value, bool) else str(value)
    else:  # attr
        parent.set(leaf, _bool_str(value) if isinstance(value, bool) else str(value))


def _emit_cc_conditions(sec: ET.Element, name: str, conditions: list[dict]) -> None:
    """Rebuild AcceptanceSettings/Conditions from spec list.

    Supports two shapes:
    - full: {column, op, value|pct_of_main, sample?, direction?}
    - pct shorthand: {column, op, pct_of_main}
    """
    acc = sec.find("AcceptanceSettings")
    if acc is None:
        acc = ET.SubElement(sec, "AcceptanceSettings")
    conds = acc.find("Conditions")
    if conds is None:
        conds = ET.SubElement(acc, "Conditions")
        conds.set("CrossCheck", name)
    for old in list(conds):
        conds.remove(old)
    for c in conditions:
        op = c.get("op", ">=")
        if op not in _OPS:
            raise ValueError(f"Invalid CC condition op: {op}")
        cond = ET.SubElement(conds, "Condition")
        cond.set("use", "true")
        left = ET.SubElement(cond, "Left-Side")
        left.set("valueType", "column")
        left.append(_column_value(c["column"], c.get("sample", "full"), name))
        comp = ET.SubElement(cond, "Comparator")
        comp.set("value", op)
        right = ET.SubElement(cond, "Right-Side")
        if "pct_of_main" in c:
            right.set("valueType", "column")
            rcv = _column_value(c["column"], "full", "main")
            rcv.set("pctRatio", str(c["pct_of_main"]))
            right.append(rcv)
        else:
            right.set("valueType", "numeric")
            nv = ET.SubElement(right, "Numeric-Value")
            nv.set("value", str(c.get("value")))
            if "confidence" in c:
                nv.set("confidence", str(c["confidence"]))


# ── Extractors (XML → dict) ────────────────────────────────────────────────


def extract_cross_checks(settings: ET.Element) -> dict:
    """Extract cross-checks from Settings XML into normalized dict."""
    result = {}
    cc_elem = settings.find("CrossChecks")
    if cc_elem is None:
        return result
    for section_elem in cc_elem:
        name = section_elem.tag
        spec: dict[str, Any] = {"use": section_elem.get("use") == "true"}
        st = section_elem.find("Settings")
        if st is not None:
            for child in st:
                if len(child) == 0 and (child.text or "").strip():
                    spec[child.tag[0].lower() + child.tag[1:]] = (child.text or "").strip()
        result[name] = spec
    return result


# ── Shared sections (money management, trading options, costs, fitness) ─────


def parse_money_management(mm_dict: dict) -> dict:
    if not mm_dict:
        return {}
    method = mm_dict.get("method")
    if method and method not in MM_METHODS and method != "fixed_size":
        raise ValueError(f"Invalid MM method: {method}")
    return dict(mm_dict)


def parse_trading_options(to_dict: dict) -> dict:
    if not to_dict:
        return {}
    return dict(to_dict)


def parse_costs(costs_dict: dict) -> dict:
    if not costs_dict:
        return {}
    return dict(costs_dict)


def parse_fitness(fitness: Any) -> str | None:
    if fitness is None:
        return None
    return str(fitness)


def parse_what_to_build(wtb_dict: dict) -> dict:
    if not wtb_dict:
        return {}
    return dict(wtb_dict)


