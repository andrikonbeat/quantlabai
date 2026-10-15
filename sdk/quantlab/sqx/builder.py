"""Surgical XML builder for SQX task settings.

Mirrors the 145 engine's builder.py: curated keys + overrides → surgical
edits on the parsed default task XML tree. NEVER writes XML from memory.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from quantlab.sqx.templates import load_defaults
from quantlab.sqx.project_builder import _DEFAULT_TEMPLATE


# ── Curated key mappings (mirror sections.pyc) ──────────────────────────────

# These are the keys the engine knows how to apply surgically.
# Each maps to a finder function and a setter.

# ── Finder/Setters ───────────────────────────────────────────────────────────


def _find_param(settings: ET.Element, key: str) -> ET.Element | None:
    """Find <Param key="..."> by key attribute."""
    for param in settings.findall(".//Param[@key]"):
        if param.get("key") == key:
            return param
    return None


def _find_direct_child(settings: ET.Element, tag: str) -> ET.Element | None:
    """Find direct child element of Settings by tag."""
    return settings.find(tag)


def _find_nested(settings: ET.Element, path: str) -> ET.Element | None:
    """Find element by XPath-like path (e.g., 'CrossChecks/RetestOnAdditionalMarkets/Setup')."""
    return settings.find(path)


# ── Curated key registry ─────────────────────────────────────────────────────

# Each entry: (finder_name, setter_type, xml_path_or_param_key)
# finder_name: "param", "direct", "nested", "sl_pt", "cross_check"
# setter_type: "text", "attr", "bool_attr"

CURATED_KEYS: dict[str, tuple[str, str, str]] = {
    # ── Trading Session (BuildTradingOptions) ──
    "exit_at_end_of_day": ("param", "text", "ExitAtEndOfDay"),
    "eod_exit_time": ("param", "text", "EODExitTime"),
    "exit_on_friday": ("param", "text", "ExitOnFriday"),
    "friday_exit_time": ("param", "text", "FridayExitTime"),
    "limit_time_range": ("param", "text", "LimitTimeRange"),
    "signal_time_range_from": ("param", "text", "SignalTimeRangeFrom"),
    "signal_time_range_to": ("param", "text", "SignalTimeRangeTo"),
    "exit_at_end_of_range": ("param", "text", "ExitAtEndOfRange"),
    "max_trades_per_day": ("param", "text", "MaxTradesPerDay"),
    "session": ("param", "text", "Session"),
    "reserved_bars": ("param", "text", "ReservedBars"),
    "store_chart_data": ("param", "text", "StoreChartData"),

    # ── Rules Complexity (under Rankings) ──
    "min_conditions": ("nested", "attr", "Rankings/minConditions"),
    "max_conditions": ("nested", "attr", "Rankings/maxConditions"),
    "min_exit_conditions": ("nested", "attr", "Rankings/minExitConditions"),
    "max_exit_conditions": ("nested", "attr", "Rankings/maxExitConditions"),
    "min_period": ("nested", "attr", "Rankings/minPeriod"),
    "max_period": ("nested", "attr", "Rankings/maxPeriod"),
    "min_shift": ("nested", "attr", "Rankings/minShift"),
    "max_shift": ("nested", "attr", "Rankings/maxShift"),

    # ── Market Sides (under WhatToBuild) ──
    "market_sides": ("nested", "attr", "WhatToBuild/MarketSides@type"),
    "entry_symmetry": ("nested", "text", "WhatToBuild/EntrySymmetry"),
    "exit_symmetry": ("nested", "text", "WhatToBuild/ExitSymmetry"),

    # ── SL/PT Options (direct children of Settings) ──
    "sl_required": ("sl_pt", "text", "SLRequired"),
    "sl_fixed_pips": ("sl_pt", "text", "SLFixedPips"),
    "min_sl_pips": ("sl_pt", "text", "MinSLInPips"),
    "max_sl_pips": ("sl_pt", "text", "MaxSLInPips"),
    "min_sl_money": ("sl_pt", "text", "MinSLInMoney"),
    "max_sl_money": ("sl_pt", "text", "MaxSLInMoney"),
    "sl_atr": ("sl_pt", "text", "SLATR"),
    "min_sl_atr_multiple": ("sl_pt", "text", "MinSLATRMultiple"),
    "max_sl_atr_multiple": ("sl_pt", "text", "MaxSLATRMultiple"),
    "min_sl_atr_period": ("sl_pt", "text", "MinSLATRPeriod"),
    "max_sl_atr_period": ("sl_pt", "text", "MaxSLATRPeriod"),
    "pt_required": ("sl_pt", "text", "PTRequired"),
    "pt_fixed_pips": ("sl_pt", "text", "PTFixedPips"),
    "min_pt_pips": ("sl_pt", "text", "MinPTInPips"),
    "max_pt_pips": ("sl_pt", "text", "MaxPTInPips"),
    "min_pt_money": ("sl_pt", "text", "MinPTInMoney"),
    "max_pt_money": ("sl_pt", "text", "MaxPTInMoney"),
    "pt_atr": ("sl_pt", "text", "PTATR"),
    "min_pt_atr_multiple": ("sl_pt", "text", "MinPTATRMultiple"),
    "max_pt_atr_multiple": ("sl_pt", "text", "MaxPTATRMultiple"),
    "min_pt_atr_period": ("sl_pt", "text", "MinPTATRPeriod"),
    "max_pt_atr_period": ("sl_pt", "text", "MaxPTATRPeriod"),
    "limit_slpt_rrr": ("sl_pt", "text", "LimitSLPTRRR"),
    "limit_slpt_rrr_from": ("sl_pt", "text", "LimitSLPTRRRFrom"),
    "limit_slpt_rrr_to": ("sl_pt", "text", "LimitSLPTRRRTo"),
    "sl_value_type": ("sl_pt", "text", "SLValueType"),
    "pt_value_type": ("sl_pt", "text", "PTValueType"),
    "sl_indicator_based": ("sl_pt", "text", "SLIndicatorBased"),
    "pt_indicator_based": ("sl_pt", "text", "PTIndicatorBased"),
    "sl_percent": ("sl_pt", "text", "SLPercent"),
    "min_sl_percent": ("sl_pt", "text", "MinSLInPercent"),
    "max_sl_percent": ("sl_pt", "text", "MaxSLInPercent"),
    "pt_percent": ("sl_pt", "text", "PTPercent"),
    "min_pt_percent": ("sl_pt", "text", "MinPTInPercent"),
    "max_pt_percent": ("sl_pt", "text", "MaxPTInPercent"),

    # ── Rankings (Param keys) ──
    "max_strategies": ("param", "text", "MaxStrategies"),
    "ranking_type": ("param", "text", "RankingType"),
    "ranking_avg_trades_min": ("param", "text", "RankingAvgTradesMin"),
    "ranking_pf_min": ("param", "text", "RankingPFMin"),
    "ranking_return_dd_min": ("param", "text", "RankingReturnDDMin"),
    "ranking_conditions_type": ("param", "text", "RankingConditionsType"),

    # ── Money Management ──
    "mm_method": ("param", "text", "MMMethod"),
    "mm_lot_size": ("param", "text", "MMLotSize"),
    "initial_capital": ("param", "text", "InitialCapital"),
    "mm_risk_pct": ("param", "text", "MMRiskPct"),
    "mm_max_drawdown": ("param", "text", "MMMaxDrawdown"),

    # ── ATMs ──
    "atms_enable": ("param", "text", "ATMsEnable"),
    "atms_scale_out_type": ("param", "text", "ATMsScaleOutType"),
    "atms_size_decimals": ("param", "text", "ATMsSizeDecimals"),
    "atms_min_size": ("param", "text", "ATMsMinSize"),

    # ── PartsToImprove ──
    "entry_rules_symmetry": ("param", "text", "EntryRulesSymmetry"),
    "entry_long_improvement": ("param", "text", "EntryLongImprovement"),
    "entry_short_improvement": ("param", "text", "EntryShortImprovement"),
    "exit_rules_symmetry": ("param", "text", "ExitRulesSymmetry"),
    "exit_long_improvement": ("param", "text", "ExitLongImprovement"),
    "exit_short_improvement": ("param", "text", "ExitShortImprovement"),

    # ── CrossChecks main toggles (nested) ──
    "rc_use": ("cross_check", "attr", "RetestOnAdditionalMarkets/use"),
    "hp_use": ("cross_check", "attr", "RetestWithHigherPrecision/use"),
    "mcr_use": ("cross_check", "attr", "MonteCarloRetest/use"),
    "wfm_use": ("cross_check", "attr", "WalkForwardMatrix/use"),
    "mcm_use": ("cross_check", "attr", "MonteCarloManipulation/use"),
    "opspp_use": ("cross_check", "attr", "OptProfileSysParamPermutation/use"),
    "wf_use": ("cross_check", "attr", "WalkForwardOptimization/use"),
    "hp_use": ("cross_check", "attr", "RetestWithHigherPrecision/use"),
    "wi_use": ("cross_check", "attr", "WhatIf/use"),
    "so_use": ("cross_check", "attr", "SequentialOptimization/use"),
    "opspp_use": ("cross_check", "attr", "OptProfileSysParamPermutation/use"),
}

# Nested cross-check keys (require path navigation)
CROSS_CHECK_KEYS: dict[str, tuple[str, str]] = {
    # RetestOnAdditionalMarkets
    "rc_date_from": ("RetestOnAdditionalMarkets/Setup", "dateFrom", "attr"),
    "rc_date_to": ("RetestOnAdditionalMarkets/Setup", "dateTo", "attr"),
    "rc_test_precision": ("RetestOnAdditionalMarkets/Setup", "testPrecision", "attr"),
    "rc_session": ("RetestOnAdditionalMarkets/Setup", "session", "attr"),
    "rc_slippage": ("RetestOnAdditionalMarkets/Setup", "slippage", "attr"),
    "rc_min_dist": ("RetestOnAdditionalMarkets/Setup", "minDist", "attr"),
    "rc_engine": ("RetestOnAdditionalMarkets/Setup", "engine", "attr"),
    "rc_symbol": ("RetestOnAdditionalMarkets/Setup/Chart", "symbol", "attr"),
    "rc_timeframe": ("RetestOnAdditionalMarkets/Setup/Chart", "timeframe", "attr"),
    "rc_commission_method": ("RetestOnAdditionalMarkets/Setup/Commissions/Method", "type", "attr"),
    "rc_check": ("RetestOnAdditionalMarkets/AcceptanceSettings", "Check", "text"),
    "rc_min_conditions": ("RetestOnAdditionalMarkets/AcceptanceSettings", "MinConditions", "text"),
    "rc_min_markets": ("RetestOnAdditionalMarkets/AcceptanceSettings", "MinMarkets", "text"),
    "rc_spread": ("RetestOnAdditionalMarkets/Setup/Chart", "spread", "attr"),
    # WalkForwardOptimization
    "wf_period": ("WalkForwardOptimization/Setup/WalkForward", "period", "attr"),
    "wf_optimization": ("WalkForwardOptimization/Setup/WalkForward", "optimization", "attr"),
    "wf_param1": ("WalkForwardOptimization/Setup/WalkForward", "Param1", "attr"),
    "wf_param2": ("WalkForwardOptimization/Setup/WalkForward", "Param2", "attr"),
    "wf_optimize_periods": ("WalkForwardOptimization/Setup", "OptimizePeriods", "text"),
    "wf_optimize_exit_types": ("WalkForwardOptimization/Setup", "OptimizeExitTypes", "text"),
    "wf_max_tests": ("WalkForwardOptimization/Setup", "MaxTests", "text"),
    "wf_acceptance_threshold_pct": ("WalkForwardOptimization/AcceptanceSettings/Conditions", "thresholdPct", "attr"),
    # RetestWithHigherPrecision
    "hp_precision": ("RetestWithHigherPrecision/Setup", "Precision", "text"),
    "hp_spread": ("RetestWithHigherPrecision/Setup", "Spread", "text"),
    # MonteCarloRetest
    "mcr_number_of_simulations": ("MonteCarloRetest/Setup", "NumberOfSimulations", "text"),
    # WalkForwardMatrix
    "wfm_period": ("WalkForwardMatrix/Setup/WalkForward", "period", "attr"),
    "wfm_optimization": ("WalkForwardMatrix/Setup/WalkForward", "optimization", "attr"),
    "wfm_optimize_periods": ("WalkForwardMatrix/Setup", "OptimizePeriods", "text"),
    "wfm_optimize_exit_types": ("WalkForwardMatrix/Setup", "OptimizeExitTypes", "text"),
    "wfm_max_tests": ("WalkForwardMatrix/Setup", "MaxTests", "text"),
    # OptProfileSysParamPermutation
    "opspp_optim_periods": ("OptProfileSysParamPermutation/Setup", "OptimPeriods", "text"),
    "opspp_optim_exit_types": ("OptProfileSysParamPermutation/Setup", "OptimExitTypes", "text"),
    "opspp_max_tests": ("OptProfileSysParamPermutation/Setup", "MaxTests", "text"),
    "opspp_profit_opt_pct": ("OptProfileSysParamPermutation/AcceptanceSettings", "ProfitOptPct", "text"),
    "opspp_avg_profit": ("OptProfileSysParamPermutation/AcceptanceSettings", "AvgProfit", "text"),
    "opspp_uniform_distr_changes": ("OptProfileSysParamPermutation/AcceptanceSettings", "UniformDistrChanges", "text"),
    "opspp_stdev_avg_profit": ("OptProfileSysParamPermutation/AcceptanceSettings", "StdevAvgProfit", "text"),
    "opspp_eval_profit_opt_check": ("OptProfileSysParamPermutation/AcceptanceSettings", "EvalProfitOptCheck", "text"),
    "opspp_eval_avg_profit_check": ("OptProfileSysParamPermutation/AcceptanceSettings", "EvalAvgProfitCheck", "text"),
    "opspp_eval_uniform_distr_check": ("OptProfileSysParamPermutation/AcceptanceSettings", "EvalUniformDistrCheck", "text"),
    "opspp_eval_top_profit_check": ("OptProfileSysParamPermutation/AcceptanceSettings", "EvalTopProfitCheck", "text"),
    # WhatIf
    "wi_by_days_use": ("WhatIf/Method[@type='ByDays']", "use", "attr"),
    "wi_by_hours_use": ("WhatIf/Method[@type='ByHours']", "use", "attr"),
    "wi_by_months_use": ("WhatIf/Method[@type='ByMonths']", "use", "attr"),
}


# ── Core Application Functions ───────────────────────────────────────────────


def apply_curated_keys(settings: ET.Element, curated: dict[str, Any]) -> list[str]:
    """
    Apply curated keys as surgical edits to the Settings XML tree.
    
    Returns list of applied keys (for logging/debugging).
    """
    applied = []
    
    for key, value in curated.items():
        if value is None:
            continue
        
        if key in CURATED_KEYS:
            finder, setter_type, target = CURATED_KEYS[key]
            if _apply_curd(settings, finder, setter_type, target, value):
                applied.append(key)
        
        elif key in CROSS_CHECK_KEYS:
            path, leaf, op = CROSS_CHECK_KEYS[key]
            if _apply_cross_check(settings, path, leaf, op, value):
                applied.append(key)
    
    return applied


def _apply_curd(settings: ET.Element, finder: str, setter_type: str, target: str, value: Any) -> bool:
    """Apply a curated key using the registered finder."""
    if finder == "param":
        elem = settings.find(f".//Param[@key='{target}']")
        if elem is not None:
            elem.text = str(value)
            return True
    
    elif finder == "direct":
        # Try direct child
        child = settings.find(target)
        if child is not None:
            if setter_type == "text":
                child.text = str(value)
            elif setter_type == "attr":
                child.set("type", str(value))
            return True
    
    elif finder == "sl_pt":
        # SL/PT options are direct children of Settings
        for elem in settings.iter():
            if elem.tag == target:
                elem.text = str(value)
                return True
    
    elif finder == "nested":
        elem = settings.find(target)
        if elem is not None:
            if setter_type == "text":
                elem.text = str(value)
            elif setter_type == "attr":
                # attr name would be in target after last /
                attr = target.split("/")[-1] if "/" in target else "type"
                elem.set(attr, str(value))
            return True
    
    elif finder == "cross_check":
        # target format: "Section/use" or "Section/Setup/@attr"
        # Parse path and attribute
        if "/" in target:
            path, attr = target.rsplit("/", 1)
            elem = settings.find(path)
            if elem is not None:
                elem.set(attr, str(value))
                return True
    
    return False


def _apply_cross_check(settings: ET.Element, path: str, leaf: str, op: str, value: Any) -> bool:
    """Apply a cross-check nested key."""
    # path = "RetestOnAdditionalMarkets/Setup"
    # leaf = "dateFrom" (attr) or "Check" (text)
    # op = "attr" or "text"
    
    # Find the section element
    section_elem = settings.find(path)
    if section_elem is None:
        return False
    
    if op == "attr":
        # leaf is attribute name
        section_elem.set(leaf, str(value))
        return True
    elif op == "text":
        # Find child by tag
        child = section_elem.find(leaf)
        if child is not None:
            child.text = str(value)
            return True
    
    return False


# ── High-level apply function ────────────────────────────────────────────────


_SPECIAL_SECTIONS = frozenset({
    "cross_checks", "money_management", "trading_options", "costs",
    "rankings", "what_to_build", "stop", "range", "fitness",
    "max_strategies", "oos_percent",
})


def _apply_special_sections(settings: ET.Element, task_spec: dict) -> list[str]:
    """Delegate special sections to sections.py emitters."""
    from quantlab.sqx import sections as sec

    applied: list[str] = []

    def has(*keys: str) -> bool:
        return any(task_spec.get(k) is not None for k in keys)

    # Data/Setup: engine, symbol, timeframe, range, costs
    if has("engine", "symbol", "timeframe", "range") or "costs" in task_spec:
        costs = task_spec.get("costs") or {}
        rng = task_spec.get("range") or {}
        sec.emit_data_setup(
            settings,
            engine=task_spec.get("engine"),
            symbol=task_spec.get("symbol"),
            timeframe=task_spec.get("timeframe"),
            date_from=rng.get("from"),
            date_to=rng.get("to"),
            test_precision=costs.get("precision") if isinstance(costs.get("precision"), int) else None,
            session=costs.get("session"),
            slippage=costs.get("slippage"),
            min_dist=costs.get("min_distance"),
            spread=costs.get("spread"),
        )
        applied.append("data_setup")

    # OOS window
    if task_spec.get("oos_percent") and task_spec.get("range"):
        rng = task_spec["range"]
        sec.emit_oos(settings, rng.get("from"), rng.get("to"), task_spec["oos_percent"])
        applied.append("oos")

    # Stop
    if task_spec.get("stop"):
        sec.emit_stop(settings, task_spec["stop"])
        applied.append("stop")

    # Rankings
    if task_spec.get("rankings"):
        sec.emit_rankings(settings, task_spec["rankings"])
        applied.append("rankings")
    if task_spec.get("max_strategies") is not None:
        sec.emit_max_strategies(settings, task_spec["max_strategies"])
        applied.append("max_strategies")

    # Fitness
    if task_spec.get("fitness"):
        sec.emit_fitness(settings, task_spec["fitness"])
        applied.append("fitness")

    # Money management
    if task_spec.get("money_management"):
        sec.emit_money_management(settings, task_spec["money_management"])
        applied.append("money_management")

    # Trading options
    if task_spec.get("trading_options"):
        sec.emit_trading_options(settings, task_spec["trading_options"])
        applied.append("trading_options")

    # What-to-build
    if task_spec.get("what_to_build"):
        sec.emit_what_to_build(settings, task_spec["what_to_build"])
        applied.append("what_to_build")

    # Cross-checks
    if task_spec.get("cross_checks"):
        sec.emit_cross_checks(settings, task_spec["cross_checks"])
        applied.append("cross_checks")

    return applied


def apply_spec_to_task(settings: ET.Element, task_spec: dict) -> list[str]:
    """
    Apply a full task spec to a Settings XML tree.

    Returns list of applied keys.
    """
    curated = {
        k: v for k, v in task_spec.items()
        if v is not None and k not in _SPECIAL_SECTIONS
        and k not in ("task", "base")
    }
    applied = apply_curated_keys(settings, curated)
    applied.extend(_apply_special_sections(settings, task_spec))
    return applied


def _apply_task_spec(settings: ET.Element, task_spec: dict) -> list[str]:
    """Apply a full task spec to a Settings XML tree.

    Returns list of applied keys.
    """
    return apply_spec_to_task(settings, task_spec)


# ── High-level CFX generation ────────────────────────────────────────────────


def build_cfx_from_spec(spec_dict: dict, output_path: Path) -> None:
    """
    Generate a complete .cfx from spec dict.
    
    This is the main entry point: spec JSON → .cfx file.
    """
    from quantlab.sqx.project_builder import _DEFAULT_TEMPLATE
    import zipfile
    
    # Load template zip - read all data inside the context manager
    with zipfile.ZipFile(_DEFAULT_TEMPLATE, "r") as z:
        config_xml_data = z.read("config.xml")
        task1_xml_data = z.read("Build-Task1.xml")
    
    config_root = ET.fromstring(config_xml_data)
    task_root = ET.fromstring(task1_xml_data)
    
    spec = spec_dict
    
    # 1. Update config.xml
    if spec.get("edit"):
        config_root.set("name", spec["edit"])
    
    # Update task name in config.xml
    for task_elem in config_root.findall(".//Task"):
        if spec.get("tasks"):
            task_spec = spec["tasks"][0]
            if task_spec.get("task"):
                task_elem.set("name", task_spec["task"])
    
    # Parse task XML
    task_root = ET.fromstring(task1_xml_data)
    
    # Apply first task spec
    if spec.get("tasks"):
        task_spec = spec["tasks"][0]
        # The task_root IS the Settings element for Build-Task1.xml
        _apply_task_spec(task_root, task_spec)
    
    # Write output
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("config.xml", ET.tostring(config_root, encoding="unicode", xml_declaration=True))
        z.writestr("Build-Task1.xml", ET.tostring(task_root, encoding="unicode", xml_declaration=True))


# ── Helpers ──────────────────────────────────────────────────────────────────

def _set_value(elem: ET.Element, value: Any) -> None:
    """Set element text or attribute based on value type."""
    if isinstance(value, bool):
        elem.text = "true" if value else "false"
    else:
        elem.text = str(value)


if __name__ == "__main__":
    # Quick test
    from quantlab.sqx.templates import load_defaults
    settings = load_defaults("Build", "forex")
    print("Loaded Build/forex defaults:", len(list(settings.iter())), "elements")
    
    # Test applying a few keys
    test_curated = {
        "session": "London",
        "min_conditions": 2,
        "max_conditions": 5,
        "sl_required": True,
        "min_sl_pips": 20,
        "mm_method": "fixed_size",
        "initial_capital": 10000,
    }
    from quantlab.sqx.templates import load_defaults
    settings = load_defaults("Build", "forex")
    applied = apply_curated_keys(settings, test_curated)
    print("Applied:", applied)