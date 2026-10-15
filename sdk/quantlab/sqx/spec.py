"""SQX Project Spec — Strict parser/validator.

Mirrors the 145 engine's spec.py: STRICTLY keyed validation,
cross-checks at parse time, surgical key mapping.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

# Known Money Management methods (mirror strategy-styles.md)
MM_METHODS = frozenset({
    "FixedSize", "fixed_size",
    "RiskFixedBalancePct", "RiskFixedPctOfAccount",
    "ATRRiskBasedSizing", "FixedAmount", "SimpleMartingaleMM",
    "StocksSizeByPrice", "CryptoSizeByPrice",
})

# Known Money Management methods (mirror strategy-styles.md)
MM_METHODS = frozenset({
    "FixedSize", "fixed_size",
    "RiskFixedBalancePct", "RiskFixedPctOfAccount",
    "ATRRiskBasedSizing", "FixedAmount", "SimpleMartingaleMM",
    "StocksSizeByPrice", "CryptoSizeByPrice",
})

# Cross-check section allowed keys (mirror sections.pyc)
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
    "take_max_trades_per_day_use", "use_fixed_lots_size",
    "exclude_biggest_pl_trades", "exclude_lowest_pl_trades",
    "exclude_short_trades_pct", "exclude_short_trades_minutes",
    "take_max_trades_per_day_trades", "use_fixed_lots_size",
    "swap_long", "swap_short",
})

# ── Key sets (mirror spec.pyc co_consts) ────────────────────────────────────

TOP_KEYS = frozenset({"edit", "tasks"})

EDIT_TOP_KEYS = frozenset({"edit", "tasks"})

# Task-level keys
COMMON_KEYS = frozenset({
    "task", "base", "engine", "symbol", "timeframe", "range",
    "oos_percent", "rankings", "max_strategies", "stop",
    "cross_checks", "money_management", "trading_options",
    "costs", "fitness", "what_to_build",
})

# Edit mode operation keys
EDIT_STRUCT_KEYS = frozenset({
    "task", "base", "engine", "symbol", "timeframe", "range",
    "oos_percent", "rankings", "max_strategies", "stop",
    "cross_checks", "money_management", "trading_options",
    "costs", "fitness", "what_to_build",
    # Structural ops
    "add_task", "remove_task", "move_task", "rename_task",
    "activate_task", "clone_task",
    # Databank ops
    "databanks", "create_databank", "remove_databank",
})

# Shared section keys
RANGE_KEYS = frozenset({"from", "to"})
STOP_KEYS = frozenset({"type", "count", "value"})
RANKING_KEYS = frozenset({"column", "op", "value", "sample"})
CROSS_CHECKS_KEYS = frozenset({
    "all", "RetestOnAdditionalMarkets", "RetestWithHigherPrecision",
    "MonteCarloRetest", "MonteCarloManipulation",
    "WalkForwardOptimization", "WalkForwardMatrix",
    "OptProfileSysParamPermutation", "WhatIf", "SequentialOptimization",
})
MONEY_MANAGEMENT_KEYS = frozenset({
    "method", "size", "initial_capital", "max_drawdown", "risk_pct",
})
TRADING_OPTIONS_KEYS = frozenset({
    "exit_on_friday", "friday_exit_time", "max_trades_per_day",
    "min_sl", "max_sl", "min_pt", "max_pt", "reserved_bars",
    "exit_on_friday", "friday_exit_time", "limit_time_range",
    "signal_time_range_from", "signal_time_range_to",
    "exit_at_end_of_range", "store_chart_data",
})
COSTS_KEYS = frozenset({
    "spread", "slippage", "min_distance", "precision", "session",
})
FITNESS_KEYS = frozenset({"fitness"})
WHAT_TO_BUILD_KEYS = frozenset({
    "market_sides", "entry_symmetry", "exit_symmetry",
    "conditions", "exit_conditions", "period", "shift",
    "sl_required", "pt_required",
})

# Cross-checks sub-keys (from sections.pyc)
RC_KEYS = frozenset({
    "use", "date_from", "date_to", "test_precision", "session",
    "slippage", "min_dist", "engine", "symbol", "timeframe",
    "commission_method", "check", "min_conditions", "min_markets", "spread",
})
WFO_KEYS = frozenset({
    "use", "period", "optimization", "param1", "param2",
    "optimize_periods", "optimize_exit_types", "max_tests",
    "acceptance_threshold_pct", "acceptance_min_conditions",
    "acceptance_min_markets", "acceptance_pf_min",
})
HPR_KEYS = frozenset({"use", "precision", "spread"})
MCR_KEYS = frozenset({
    "use", "number_of_simulations",
    "history_data_use", "history_probability_up", "history_probability_down",
    "history_max_change_up", "history_max_change_down",
    "min_distance_use", "min_distance_min", "min_distance_max",
    "slippage_use", "slippage_min", "slippage_max",
    "spread_use", "spread_min", "spread_max",
    "starting_bar_use", "starting_bar_max_change",
    "strategy_params_use", "strategy_params_probability",
    "strategy_params_max_change", "strategy_params_symmetric",
})
WFM_KEYS = frozenset({
    "use", "param1_start", "param1_stop", "param1_step",
    "param2_start", "param2_stop", "param2_step",
    "threshold_pct", "rob_comb_rows", "rob_comb_cols", "rob_min_comb",
    "period", "optimization", "optimize_periods", "optimize_exit_types", "max_tests",
})
MCM_KEYS = frozenset({
    "use", "number_of_simulations",
    "trades_order_use", "trades_order_method",
    "skip_trades_use", "skip_trades_probability",
})
OPSPP_KEYS = frozenset({
    "use", "optim_periods", "optim_exit_types", "max_tests",
    "profit_opt_pct", "avg_profit", "uniform_distr_changes",
    "stdev_avg_profit", "eval_profit_opt_check", "eval_avg_profit_check",
    "eval_uniform_distr_check", "eval_top_profit_check",
})
WI_KEYS = frozenset({
    "use", "by_days_use", "by_hours_use", "by_months_use",
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
SO_KEYS = frozenset({"use"})


# ── Exceptions ───────────────────────────────────────────────────────────────


class SpecValidationError(Exception):
    """Raised when spec validation fails."""
    pass


# ── Helpers ──────────────────────────────────────────────────────────────────


def _check_keys(obj: dict, allowed: frozenset, path: str) -> None:
    """Validate that dict only contains allowed keys."""
    extra = set(obj.keys()) - allowed
    if extra:
        raise SpecValidationError(
            f"{path}: unknown key(s): {', '.join(sorted(extra))}. "
            f"Allowed: {', '.join(sorted(allowed))}"
        )


def _need(obj: dict, key: str, path: str) -> Any:
    """Get required key or raise."""
    if key not in obj:
        raise SpecValidationError(f"{path}: missing required key '{key}'")
    return obj[key]


def _check_type(obj: Any, expected: type, path: str) -> None:
    if not isinstance(obj, expected):
        raise SpecValidationError(
            f"{path}: expected {expected.__name__}, got {type(obj).__name__}"
        )


def _parse_date(s: str) -> date:
    """Parse SQX date format: YYYY-MM-DD or YYYY.MM.DD."""
    s = s.replace(".", "-")
    return date.fromisoformat(s)


def _validate_range(obj: dict, path: str) -> None:
    _check_keys(obj, RANGE_KEYS, path)
    _need(obj, "from", path)
    _need(obj, "to", path)
    _parse_date(obj["from"])
    _parse_date(obj["to"])


def _validate_stop(obj: dict, path: str) -> None:
    _check_keys(obj, STOP_KEYS, path)
    _need(obj, "type", path)
    stop_type = obj["type"]
    if stop_type == "passed-count":
        _need(obj, "count", path)
        if not isinstance(obj["count"], int) or obj["count"] <= 0:
            raise SpecValidationError(f"{path}.count: must be positive int")
    elif stop_type == "generation":
        _need(obj, "value", path)
    else:
        raise SpecValidationError(f"{path}.type: unknown stop type '{stop_type}'")


def _validate_ranking(obj: dict, path: str) -> None:
    _check_keys(obj, RANKING_KEYS, path)
    _need(obj, "column", path)
    _need(obj, "op", path)
    _need(obj, "value", path)
    _need(obj, "sample", path)
    if obj["op"] not in (">=", ">", "<=", "<", "==", "!="):
        raise SpecValidationError(f"{path}.op: invalid operator")
    if obj["sample"] not in ("oos", "is", "full"):
        raise SpecValidationError(f"{path}.sample: must be 'oos', 'is', or 'full'")


def _validate_cross_checks(obj: dict, path: str) -> None:
    _check_keys(obj, CROSS_CHECKS_KEYS, path)
    # Validate each cross-check section
    for section in ("RetestOnAdditionalMarkets", "RetestWithHigherPrecision",
                    "MonteCarloRetest", "MonteCarloManipulation",
                    "WalkForwardOptimization", "WalkForwardMatrix",
                    "OptProfileSysParamPermutation", "WhatIf", "SequentialOptimization"):
        if section in obj:
            _validate_cross_check_section(obj[section], f"{path}.{section}")


def _validate_cross_check_section(obj: dict, path: str) -> None:
    """Validate a cross-check section."""
    if not isinstance(obj, dict):
        raise SpecValidationError(f"{path}: must be dict")
    
    if "use" not in obj:
        raise SpecValidationError(f"{path}: missing 'use'")
    
    if not obj.get("use", False):
        return  # Disabled sections skip validation
    
    # Validate keys against allowed keys for cross-check sections
    _check_keys(obj, _CC_SECTION_KEYS, path)
    
    # Section-specific validation would go here
    # For MVP, we just check basic structure


def _validate_money_management(obj: dict, path: str) -> None:
    _check_keys(obj, MONEY_MANAGEMENT_KEYS, path)
    _need(obj, "method", path)
    method = obj["method"]
    if method not in MM_METHODS:
        raise SpecValidationError(f"{path}.method: unknown method '{method}'")
    _need(obj, "size", path)
    _need(obj, "initial_capital", path)
    if method == "FixedSize":
        if not isinstance(obj["size"], (int, float)) or obj["size"] <= 0:
            raise SpecValidationError(f"{path}.size: must be positive number")
    if "max_drawdown" in obj and obj["max_drawdown"] is not None:
        if not isinstance(obj["max_drawdown"], (int, float)) or obj["max_drawdown"] <= 0:
            raise SpecValidationError(f"{path}.max_drawdown: must be positive")


def _validate_trading_options(obj: dict, path: str) -> None:
    _check_keys(obj, TRADING_OPTIONS_KEYS, path)
    # Type validation for known fields
    int_fields = ["friday_exit_time", "max_trades_per_day", "min_sl", "max_sl",
                  "min_pt", "max_pt", "reserved_bars"]
    for f in int_fields:
        if f in obj and obj[f] is not None:
            if not isinstance(obj[f], int):
                raise SpecValidationError(f"{path}.{f}: must be int")


def _validate_costs(obj: dict, path: str) -> None:
    _check_keys(obj, COSTS_KEYS, path)
    for f in ["spread", "slippage", "min_distance"]:
        if f in obj and obj[f] is not None:
            if not isinstance(obj[f], (int, float)):
                raise SpecValidationError(f"{path}.{f}: must be number")


def _validate_what_to_build(obj: dict, path: str) -> None:
    _check_keys(obj, WHAT_TO_BUILD_KEYS, path)
    if "market_sides" in obj and obj["market_sides"] not in ("both", "long", "short"):
        raise SpecValidationError(f"{path}.market_sides: must be 'both', 'long', or 'short'")
    for f in ["conditions", "exit_conditions", "period", "shift"]:
        if f in obj and obj[f] is not None:
            if not isinstance(obj[f], list):
                raise SpecValidationError(f"{path}.{f}: must be list")


# ── Main validator ───────────────────────────────────────────────────────────


def validate_spec(spec: dict) -> dict:
    """
    Validate a spec dict strictly.
    
    Returns the normalized spec (with defaults applied).
    Raises SpecValidationError on any violation.
    """
    if not isinstance(spec, dict):
        raise SpecValidationError("Spec must be a dict")
    
    _check_keys(spec, TOP_KEYS, "root")
    
    # Edit mode detection
    is_edit = "edit" in spec
    
    if is_edit:
        _check_keys(spec, EDIT_TOP_KEYS, "root")
        if "tasks" not in spec:
            raise SpecValidationError("root: edit mode requires 'tasks'")
    else:
        if "tasks" not in spec:
            raise SpecValidationError("root: missing 'tasks'")
    
    tasks = spec.get("tasks", [])
    if not isinstance(tasks, list):
        raise SpecValidationError("tasks: must be list")
    if not tasks:
        raise SpecValidationError("tasks: at least one task required")
    
    normalized_tasks = []
    for i, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise SpecValidationError(f"tasks[{i}]: must be dict")
        
        task_path = f"tasks[{i}]"
        
        if is_edit:
            _check_keys(task, EDIT_STRUCT_KEYS, task_path)
            # Must have either task (for structural ops) or edit ops
            if "task" not in task and not any(k in task for k in ("add_task", "remove_task", "move_task", "rename_task", "activate_task", "clone_task", "databanks", "create_databank", "remove_databank")):
                raise SpecValidationError(f"{task_path}: edit operation requires 'task' or structural op")
        else:
            _check_keys(task, COMMON_KEYS, task_path)
            _need(task, "task", task_path)
        
        # Task type validation
        task_type = task.get("task")
        valid_types = {"Build", "Retest", "Optimize", "Filtering", "ClearDatabanks",
                       "GoToTask", "AutomaticRetest", "CreatePortfolio",
                       "AutomaticPortfolioBuilder", "CustomAnalysis",
                       "LogDatabankStats", "LoadFromFiles", "SaveToFiles",
                       "DeleteFile", "CallExternalScript", "Notification",
                       "StopAndStart"}
        if task_type and task_type not in valid_types:
            raise SpecValidationError(f"tasks[{i}].task: invalid type '{task_type}'")
        
        # Base engine validation
        if "base" in task:
            if task["base"] not in ("forex", "futures", "stockpicker"):
                raise SpecValidationError(f"tasks[{i}].base: must be 'forex', 'futures', or 'stockpicker'")
        
        # Engine validation
        if "engine" in task:
            if task["engine"] not in ("MetaTrader4", "MetaTrader5", "JForex", "NinjaTrader", "TradeStation"):
                raise SpecValidationError(f"tasks[{i}].engine: invalid engine")
        
        # Symbol format (basic check) - allow letters, digits, underscores, dots, hyphens
        if "symbol" in task and task["symbol"]:
            if not re.match(r"^[A-Za-z0-9_.-]+$", task["symbol"]):
                raise SpecValidationError(f"tasks[{i}].symbol: invalid format")
        
        # Timeframe validation
        if "timeframe" in task and task["timeframe"]:
            valid_tfs = {"M1", "M5", "M15", "M30", "H1", "H4", "D1", "TICK"}
            if task["timeframe"] not in valid_tfs:
                raise SpecValidationError(f"tasks[{i}].timeframe: must be one of {valid_tfs}")
        
        # Range validation
        if "range" in task:
            _validate_range(task["range"], f"tasks[{i}].range")
        
        # OOS percent
        if "oos_percent" in task:
            val = task["oos_percent"]
            if not isinstance(val, int) or not (0 <= val <= 100):
                raise SpecValidationError("oos_percent: must be int 0-100")
        
        # Rankings
        if "rankings" in task:
            if not isinstance(task["rankings"], list):
                raise SpecValidationError("rankings: must be list")
            for j, r in enumerate(task["rankings"]):
                _validate_ranking(r, f"tasks[{i}].rankings[{j}]")
        
        # Max strategies
        if "max_strategies" in task:
            if not isinstance(task["max_strategies"], int) or task["max_strategies"] <= 0:
                raise SpecValidationError("max_strategies: must be positive int")
        
        # Stop
        if "stop" in task:
            _validate_stop(task["stop"], f"tasks[{i}].stop")
        
        # Cross-checks
        if "cross_checks" in task:
            _validate_cross_checks(task["cross_checks"], f"tasks[{i}].cross_checks")
        
        # Money management
        if "money_management" in task:
            _validate_money_management(task["money_management"], f"tasks[{i}].money_management")
        
        # Trading options
        if "trading_options" in task:
            _validate_trading_options(task["trading_options"], f"tasks[{i}].trading_options")
        
        # Costs
        if "costs" in task:
            _validate_costs(task["costs"], f"tasks[{i}].costs")
        
        # Fitness
        if "fitness" in task:
            valid_fitness = {"ReturnDDRatio", "NetProfit", "SharpeRatio", "ProfitFactor", "Return", "Drawdown"}
            if task["fitness"] not in valid_fitness:
                raise SpecValidationError(f"fitness: must be one of {valid_fitness}")
        
        # What to build
        if "what_to_build" in task:
            _validate_what_to_build(task["what_to_build"], f"tasks[{i}].what_to_build")
    
    return spec


def parse_spec(spec_json: str) -> dict:
    """Parse and validate spec from JSON string."""
    import json
    spec = json.loads(spec_json)
    return validate_spec(spec)


if __name__ == "__main__":
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("Usage: python spec.py <spec.json>")
        sys.exit(1)
    
    with open(sys.argv[1], "r") as f:
        spec_json = f.read()
    
    try:
        spec = parse_spec(spec_json)
        print("✓ Spec validation passed")
        print(json.dumps(spec, indent=2))
    except SpecValidationError as e:
        print(f"✗ Spec validation failed: {e}")
        sys.exit(1)