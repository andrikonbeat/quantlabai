"""Parameter Mapper: ExplorationDecision → Task Parameters (REQ-22, REQ-43/44).

This module maps the high-level ExplorationDecision (13 fields) to the
granular per-task parameters required by each SQX CustomProject task type.
The mapping is DETERMINISTIC: same ExplorationDecision + template always
produces identical task parameters.

This is the CORE of the deterministic configuration pipeline (C2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from quantlab.exploration.models import ExplorationDecision, BrokerCostSnapshot
from quantlab.exploration.params_schema import (
    TaskType,
    get_task_schema,
    coerce_params,
    TaskType,
)


# ── Parameter Mapping Rules ────────────────────────────────────────────────

# Each mapping rule defines how an ExplorationDecision field maps to
# specific task parameters. Rules are applied in order.

@dataclass(frozen=True)
class MappingRule:
    """A single mapping rule: source field → target task params."""

    source_field: str                    # Field in ExplorationDecision
    target_tasks: list[TaskType]         # Task types this rule applies to
    target_param: str                    # Parameter name in task
    transform: str | None = None         # Optional transform function name
    condition: str | None = None         # Optional condition (eval context: exploration)


# Transform functions (registered by name)
TRANSFORM_REGISTRY: dict[str, callable] = {}


def register_transform(name: str):
    """Decorator to register a transform function."""
    def decorator(func):
        TRANSFORM_REGISTRY[name] = func
        return func
    return decorator


@register_transform("capital_to_risk_usd")
def capital_to_risk_usd(capital_usd: float, risk_pct: float = 1.0) -> float:
    """Convert capital to risk USD per trade."""
    return round(capital_usd * (risk_pct / 100.0), 2)


@register_transform("capital_to_max_lot")
def capital_to_max_lot(capital_usd: float, leverage: float = 30.0, min_lot: float = 0.01) -> float:
    """Calculate max lot size from capital and leverage."""
    max_lot = (capital_usd * leverage) / 100_000
    return max(min_lot, round(max_lot, 2))


@register_transform("capital_to_risk_pips")
def capital_to_risk_pips(capital_usd: float, risk_pct: float = 1.0, min_lot: float = 0.01, pip_value: float = 10.0) -> int:
    """Calculate stop loss pips needed to keep risk at risk_pct with min lot."""
    risk_usd = capital_usd * (risk_pct / 100.0)
    required_sl = risk_usd / (min_lot * pip_value)
    return max(10, int(required_sl))


@register_transform("market_to_symbol")
def market_to_symbol(market: str) -> str:
    """Convert market name to symbol (identity for forex)."""
    return market


@register_transform("timeframe_to_wf_cycles")
def timeframe_to_wf_cycles(timeframe: str) -> int:
    """Map timeframe to recommended walkforward cycles."""
    mapping = {
        "M1": 20,
        "M5": 15,
        "M15": 12,
        "M30": 10,
        "H1": 8,
        "H4": 6,
        "D1": 5,
        "W1": 3,
        "MN": 2,
    }
    return mapping.get(timeframe, 5)


# ── Mapping Rules (Ordered) ──────────────────────────────────────────────

MAPPING_RULES: list[tuple[str, list[str], str, str | None, str | None]] = [
    # (source_field, target_task_types, target_param, transform, condition)

    # === Capital → Risk/Money Management ===
    ("capital_usd", ["Build", "Optimize", "Retest", "AutomaticRetest"],
     "risk_per_trade_usd", "capital_to_risk_usd", None),

    ("capital_usd", ["Build", "Optimize", "Retest", "AutomaticRetest"],
     "max_lot_size", "capital_to_max_lot", None),

    # === Leverage ===
    ("leverage", ["Build", "Optimize"], "leverage", None, None),

    # === Market / Instruments ===
    ("market", ["Build", "Filtering", "Retest", "Optimize", "AutomaticRetest"],
     "symbol", "market_to_symbol", None),

    ("instruments", ["Build", "Optimize", "Retest", "AutomaticRetest"],
     "instruments", None, None),  # direct list copy

    # === Timeframe ===
    ("timeframe", ["Build", "Retest", "Optimize", "AutomaticRetest"],
     "timeframe", None, None),

    ("timeframe", ["Retest", "Optimize", "AutomaticRetest"],
     "walkforward_cycles", "timeframe_to_wf_cycles", None),

    # === Capital Limits ===
    ("capital_limits.max_drawdown_pct", ["Build", "Optimize", "Retest"],
     "max_drawdown_pct", None, None),

    ("capital_limits.risk_per_trade_pct", ["Build", "Optimize", "Retest"],
     "risk_per_trade_pct", None, None),

    ("capital_limits.max_concurrent_positions", ["Build", "Optimize"],
     "max_concurrent_positions", None, None),

    ("capital_limits.min_lot_size", ["Build", "Optimize"],
     "min_lot_size", None, None),

    ("capital_limits.max_lot_size", ["Build", "Optimize"],
     "max_lot_size", None, None),  # already set from capital_usd, but can override

    ("capital_limits.instruments", ["Build", "Optimize", "Retest"],
     "instruments", None, None),

    ("capital_limits.timeframe", ["Build", "Retest", "Optimize"],
     "timeframe", None, None),

    # === Operational Restrictions ===
    ("operational_restrictions.trading_hours_utc", ["Build"],
     "trading_hours_utc", None, None),

    ("operational_restrictions.forbidden_days", ["Build"],
     "forbidden_days", None, None),

    ("operational_restrictions.max_daily_trades", ["Build"],
     "max_daily_trades", None, None),

    ("operational_restrictions.news_filter", ["Build", "Filtering"],
     "news_filter", None, None),

    ("operational_restrictions.max_spread_pips", ["Build", "Filtering"],
     "max_spread_pips", None, None),

    # === Risk Management ===
    ("risk_management.stop_loss_pips", ["Build", "Retest", "Optimize"],
     "stop_loss_pips", None, None),

    ("risk_management.take_profit_pips", ["Build", "Retest", "Optimize"],
     "take_profit_pips", None, None),

    ("risk_management.rr_ratio", ["Build", "Optimize"],
     "rr_ratio", None, None),

    ("risk_management.max_portfolio_heat_pct", ["Build", "Optimize"],
     "max_portfolio_heat_pct", None, None),

    # === Money Management ===
    ("money_management.position_sizing_method", ["Build", "Optimize"],
     "position_sizing_method", None, None),

    ("money_management.fixed_fractional_pct", ["Build", "Optimize"],
     "fixed_fractional_pct", None, None),

    ("money_management.compounding", ["Build", "Optimize"],
     "compounding", None, None),

    # === Statistical Edge ===
    ("statistical_edge.expected_sharpe", ["Retest", "Optimize"],
     "expected_sharpe", None, None),

    ("statistical_edge.win_rate", ["Retest", "Optimize"],
     "win_rate", None, None),

    ("statistical_edge.profit_factor", ["Retest", "Optimize"],
     "profit_factor", None, None),

    ("statistical_edge.expectancy_per_trade", ["Retest", "Optimize"],
     "expectancy_per_trade", None, None),

    # === Hypothesis ===
    ("hypothesis", ["Retest", "Optimize", "AutomaticRetest"],
     "hypothesis", None, None),

    # === Broker Info ===
    ("broker_info.commission_per_lot", ["Build", "Optimize", "Retest"],
     "commission_per_lot", None, None),

    ("broker_info.slippage_pips", ["Build", "Retest", "Optimize"],
     "slippage_pips", None, None),

    ("broker_info.spread_pips", ["Build", "Filtering", "Retest", "Optimize"],
     "spread_pips", None, None),

    ("broker_info.swap_long", ["Build", "Retest"],
     "swap_long", None, None),

    ("broker_info.swap_short", ["Build", "Retest"],
     "swap_short", None, None),

    ("broker_info.triple_swap_day", ["Build", "Retest"],
     "triple_swap_day", None, None),

    # === Timeframe-specific defaults (when not in exploration) ===
    # These are fallback defaults applied when exploration doesn't specify
]

# Task-type-specific default overrides (applied after main mapping)
TASK_DEFAULTS: dict[str, dict[str, Any]] = {
    "Build": {
        "exit_at_end_of_day": False,
        "eod_exit_time": 1600,
        "exit_on_friday": True,
        "friday_exit_time": 1600,
        "limit_time_range": False,
        "signal_time_range_from": 0,
        "signal_time_range_to": 2359,
        "exit_at_end_of_range": False,
        "max_trades_per_day": 0,
        "session": "",
        "reserved_bars": 100,
        "store_chart_data": True,
        "min_conditions": 1,
        "max_conditions": 10,
        "min_exit_conditions": 1,
        "max_exit_conditions": 10,
        "min_period": 1,
        "max_period": 500,
        "min_shift": 0,
        "max_shift": 100,
        "market_sides": "both",
        "entry_symmetry": True,
        "exit_symmetry": True,
    },
    "Filtering": {
        "conditions": "NetProfit > 1000",
    },
    "Retest": {
        "monte_carlo_runs": 500,
        "walkforward_cycles": 5,
    },
    "GoToTask": {
        "target": "Filtering",
        "condition": "retest_failed",
    },
    "Optimize": {
        "walkforward_cycles": 10,
        "optimize_params": "maxOptimizations=100",
    },
    "AutomaticRetest": {
        "retest_with_higher_precision": False,
        "precision": 4,
        "spread": 2,
    },
    "AutomaticPortfolioBuilder": {
        "search_type": "bruteforce",
        "min_strategies": 2,
        "max_strategies": 8,
    },
    # CreatePortfolio, CustomAnalysis, LogDatabankStats, SaveToFiles,
    # LoadFromFiles, UpdateData and WaitFor are deliberately absent: their
    # defaults live in TASK_PARAM_SCHEMAS (quantlab.exploration.params_schema),
    # which is also what decides whether a mapped key survives
    # ``coerce_params``. A second copy here is what let the two vocabularies
    # drift apart (T13, odd/tasks/gap-remediation.md L19b): these entries
    # declared names such as ``portfolio_name`` and ``wait_seconds`` that no
    # serializer reads, so a caller could set them and the value never reached
    # the .cfx.
}


# ── Core Mapper Class ────────────────────────────────────────────────────


class ParamMapper:
    """Maps ExplorationDecision to per-task parameter dictionaries.

    This is the core deterministic mapper: same ExplorationDecision +
    same template → identical task parameters every time.
    """

    def __init__(
        self,
        template_name: str = "standard_research",
        custom_rules: list[tuple] | None = None,
    ):
        self.template_name = template_name
        self.custom_rules = custom_rules or []

        # Combine default mapping rules with any custom rules
        self.rules = MAPPING_RULES + (custom_rules or [])

    def map(
        self,
        exploration: Any,  # ExplorationDecision
        template_tasks: list[Any],  # list of CustomProjectTask from template
    ) -> dict[str, dict[str, Any]]:
        """Map ExplorationDecision to per-task parameter dictionaries.

        Args:
            exploration: The ExplorationDecision artifact
            template_tasks: List of CustomProjectTask from template

        Returns:
            Dict mapping task_name -> dict of parameter_name -> value
        """
        result = {}

        for task in template_tasks:
            task_type = task.type
            task_name = task.name

            # Start with task-type defaults
            params = TASK_DEFAULTS.get(task_type, {}).copy()

            # Apply exploration-derived parameters
            params.update(self._apply_rules(exploration, task_type, task))

            # Coerce to schema
            from quantlab.exploration.params_schema import get_task_schema, coerce_params
            from quantlab.exploration.params_schema import TaskType
            schema = get_task_schema(task.type)
            if schema:
                # Convert task.type string to TaskType enum
                task_type_enum = None
                for tt in TaskType:
                    if tt.value == task.type:
                        task_type_enum = tt
                        break
                if task_type_enum:
                    params = coerce_params(task_type_enum, params)

            result[task_name] = params

        return result

    def _apply_rules(
        self,
        exploration: Any,
        task_type: str,
        task: Any,
    ) -> dict[str, Any]:
        """Apply mapping rules for a specific task type."""
        params = {}

        # Iterate through mapping rules
        for rule in self.rules:
            source_field, target_tasks, target_param, transform, condition = rule

            # Check if rule applies to this task type
            task_type_enum = None
            from quantlab.exploration.params_schema import TaskType
            for tt in TaskType:
                if tt.value == task_type:
                    task_type_enum = tt
                    break

            if task_type_enum and task_type_enum not in rule[1]:
                continue

            # Check condition if present
            if condition and not self._eval_condition(condition, exploration):
                continue

            # Get source value
            source_value = self._get_nested_attr(exploration, source_field)
            if source_value is None:
                continue

            # Apply transform if specified
            if transform:
                from quantlab.exploration.param_mapper import TRANSFORM_REGISTRY
                transform_fn = TRANSFORM_REGISTRY.get(transform)
                if transform_fn:
                    # Extract needed args from exploration
                    target_value = self._call_transform(transform_fn, exploration, source_value)
                else:
                    target_value = source_value
            else:
                target_value = source_value

            # Set parameter
            target_param = rule[2]
            params[target_param] = target_value

        return params

    def _eval_condition(self, condition: str, exploration: Any) -> bool:
        """Safely evaluate a condition string against exploration object."""
        # Simple condition evaluator - extend as needed
        # For now, support simple attribute checks
        try:
            # Create safe namespace with exploration attributes
            namespace = {}
            if hasattr(exploration, '__dict__'):
                namespace.update(exploration.__dict__)
            elif hasattr(exploration, 'model_dump'):
                namespace.update(exploration.model_dump())

            return eval(condition, {"__builtins__": {}}, namespace)
        except Exception:
            return False

    def _get_nested_attr(self, obj: Any, path: str) -> Any:
        """Get nested attribute using dot notation (e.g., 'capital_limits.max_drawdown_pct')."""
        if not path:
            return None

        parts = path.split('.')
        current = obj

        for part in parts:
            if hasattr(current, part):
                current = getattr(current, part)
            elif isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None

        return current

    def _call_transform(self, transform_fn, exploration: Any, source_value: Any) -> Any:
        """Call a transform function with appropriate arguments extracted from exploration."""
        import inspect
        sig = inspect.signature(transform_fn)
        params = sig.parameters
        
        # Build kwargs from exploration attributes
        kwargs = {}
        exploration_dict = exploration.model_dump() if hasattr(exploration, 'model_dump') else exploration.__dict__
        
        for param_name, param in params.items():
            if param_name in exploration_dict:
                kwargs[param_name] = exploration_dict[param_name]
            elif param.default is not inspect.Parameter.empty:
                # Use default
                pass
            elif source_value is not None and param_name in ('value', 'source_value', 'capital_usd'):
                # Fallback to source_value for single-arg transforms
                kwargs[param_name] = source_value
        
        return transform_fn(**kwargs)


def create_param_mapper(
    template_name: str = "standard_research",
    custom_rules: list[tuple] | None = None,
) -> ParamMapper:
    """Factory function to create a ParamMapper instance."""
    return ParamMapper(template_name=template_name, custom_rules=custom_rules)