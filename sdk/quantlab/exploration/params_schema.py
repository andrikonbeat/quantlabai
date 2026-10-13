"""Parameter schemas for SQX CustomProject task types (REQ-22, REQ-43/44).

Each task type in the SQX 144/2953 catalog has a fixed set of configurable
parameters. This module defines the canonical schema for each task type,
enabling deterministic mapping from ExplorationDecision → task params.

The schemas are derived from the verified 144/2953 CFX goldens and the
SQX 144/2953 parameter reference documentation. Each task type defines:

- Required parameters (must be present)
- Optional parameters (with defaults)
- Parameter types and constraints (ranges, enums)
- Parameter groups (Options, Data, SL/PT, WalkForward, etc.)

This module is the SINGLE SOURCE OF TRUTH for task parameter schemas.
The ParamMapper uses these schemas to validate and complete parameter sets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ParamType(str, Enum):
    """Parameter value types."""

    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"
    BOOLEAN = "boolean"
    ENUM = "enum"


@dataclass(frozen=True)
class ParamConstraint:
    """Constraints for a parameter value."""

    min_value: float | None = None
    max_value: float | None = None
    allowed_values: list[Any] | None = None
    pattern: str | None = None  # regex for strings


@dataclass(frozen=True)
class ParamSpec:
    """Specification for a single task parameter."""

    name: str
    param_type: ParamType
    required: bool = False
    default: Any = None
    constraint: ParamConstraint | None = None
    description: str = ""
    group: str = "Options"  # UI group: Options, Data, SL/PT, WalkForward, MonteCarlo, etc.

    def validate(self, value: Any) -> bool:
        """Validate a value against this parameter's constraints."""
        if value is None:
            return not self.required

        # Type check
        if self.param_type == ParamType.INTEGER:
            if not isinstance(value, int):
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    return False
        elif self.param_type == ParamType.FLOAT:
            if not isinstance(value, (int, float)):
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    return False
        elif self.param_type == ParamType.BOOLEAN:
            if not isinstance(value, bool):
                if isinstance(value, str):
                    value = value.lower() in ("true", "1", "yes", "on")
                else:
                    return False
        elif self.param_type == ParamType.ENUM:
            if self.constraint and self.constraint.allowed_values:
                if value not in self.constraint.allowed_values:
                    return False
        elif self.param_type == ParamType.STRING:
            if not isinstance(value, str):
                value = str(value)

        # Constraint check
        if self.constraint:
            if self.constraint.min_value is not None and value < self.constraint.min_value:
                return False
            if self.constraint.max_value is not None and value > self.constraint.max_value:
                return False
            if self.constraint.allowed_values and value not in self.constraint.allowed_values:
                return False
            if self.constraint.pattern and isinstance(value, str):
                import re
                if not re.match(self.constraint.pattern, value):
                    return False

        return True

    def coerce(self, value: Any) -> Any:
        """Coerce a value to the correct type, applying default if needed."""
        if value is None:
            return self.default

        if self.param_type == ParamType.INTEGER:
            return int(value)
        elif self.param_type == ParamType.FLOAT:
            return float(value)
        elif self.param_type == ParamType.BOOLEAN:
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes", "on")
            return bool(value)
        elif self.param_type == ParamType.STRING:
            return str(value)
        return value


# ── Parameter Groups (SQX UI Sections) ────────────────────────────────────

PARAM_GROUPS = (
    "Options",
    "Data",
    "SL/PT",
    "WalkForward",
    "MonteCarlo",
    "MonteCarloRetest",
    "WalkForwardOptimization",
    "RetestWithHigherPrecision",
    "MonteCarloRetest",
    "WalkForwardOptimization",
    "RetesterData",
    "Optimize",
    "Build",
    "Filtering",
    "Ranking",
    "Options",
)


# ── Task Type Enum (SQX 144/2953 Catalog) ────────────────────────────────


class TaskType(str, Enum):
    """SQX CustomProject task types (verified 144/2953 catalog)."""

    BUILD = "Build"
    FILTERING = "Filtering"
    RETEST = "Retest"
    GOTO_TASK = "GoToTask"
    OPTIMIZE = "Optimize"
    AUTOMATIC_RETEST = "AutomaticRetest"
    AUTOMATIC_PORTFOLIO_BUILDER = "AutomaticPortfolioBuilder"
    CREATE_PORTFOLIO = "CreatePortfolio"
    CUSTOM_ANALYSIS = "CustomAnalysis"
    LOG_DATABANK_STATS = "LogDatabankStats"
    SAVE_TO_FILES = "SaveToFiles"
    LOAD_FROM_FILES = "LoadFromFiles"
    UPDATE_DATA = "UpdateData"
    WAIT_FOR = "WaitFor"
    # The 7 catalog types previously missing from the enum
    APPLY_MASS_CONFIG = "ApplyMassConfig"
    CALL_EXTERNAL_SCRIPT = "CallExternalScript"
    CLEAR_DATABANKS = "ClearDatabanks"
    DELETE_FILE = "DeleteFile"
    NEURAL_NETWORK_TRAINER = "NeuralNetworkTrainer"
    NOTIFICATION = "Notification"
    STOP_AND_START = "StopAndStart"


# ── Parameter Schemas per Task Type ───────────────────────────────────────

# Each task type maps to a dict of param_name -> ParamSpec
# These schemas are derived from the SQX 144/2953 CFX goldens and the
# SQX 144/2953 parameter reference documentation.

TASK_PARAM_SCHEMAS: dict[TaskType, dict[str, ParamSpec]] = {

    TaskType.BUILD: {
        # Options section
        "exit_at_end_of_day": ParamSpec(
            name="exit_at_end_of_day",
            param_type=ParamType.BOOLEAN,
            default=False,
            description="Exit all positions at end of trading day",
            group="Options",
        ),
        "eod_exit_time": ParamSpec(
            name="eod_exit_time",
            param_type=ParamType.INTEGER,
            default=1600,
            constraint=ParamConstraint(min_value=0, max_value=2359),
            description="End-of-day exit time (HHMM format)",
            group="Options",
        ),
        "exit_on_friday": ParamSpec(
            name="exit_on_friday",
            param_type=ParamType.BOOLEAN,
            default=True,
            description="Exit positions on Friday",
            group="Options",
        ),
        "friday_exit_time": ParamSpec(
            name="friday_exit_time",
            param_type=ParamType.INTEGER,
            default=1600,
            constraint=ParamConstraint(min_value=0, max_value=2359),
            description="Friday exit time (HHMM format)",
            group="Options",
        ),
        "limit_time_range": ParamSpec(
            name="limit_time_range",
            param_type=ParamType.BOOLEAN,
            default=False,
            description="Limit trading to specific time range",
            group="Options",
        ),
        "signal_time_range_from": ParamSpec(
            name="signal_time_range_from",
            param_type=ParamType.INTEGER,
            default=0,
            constraint=ParamConstraint(min_value=0, max_value=2359),
            description="Signal time range start (HHMM)",
            group="Options",
        ),
        "signal_time_range_to": ParamSpec(
            name="signal_time_range_to",
            param_type=ParamType.INTEGER,
            default=2359,
            constraint=ParamConstraint(min_value=0, max_value=2359),
            description="Signal time range end (HHMM)",
            group="Options",
        ),
        "exit_at_end_of_range": ParamSpec(
            name="exit_at_end_of_range",
            param_type=ParamType.BOOLEAN,
            default=False,
            description="Exit positions at end of time range",
            group="Options",
        ),
        "max_trades_per_day": ParamSpec(
            name="max_trades_per_day",
            param_type=ParamType.INTEGER,
            default=0,
            constraint=ParamConstraint(min_value=0, max_value=100),
            description="Maximum trades per day (0 = unlimited)",
            group="Options",
        ),
        "session": ParamSpec(
            name="session",
            param_type=ParamType.STRING,
            default="",
            description="Trading session filter",
            group="Options",
        ),
        "reserved_bars": ParamSpec(
            name="reserved_bars",
            param_type=ParamType.INTEGER,
            default=100,
            constraint=ParamConstraint(min_value=0, max_value=10000),
            description="Number of reserved bars for indicators",
            group="Options",
        ),
        "store_chart_data": ParamSpec(
            name="store_chart_data",
            param_type=ParamType.BOOLEAN,
            default=True,
            description="Store chart data for visual analysis",
            group="Options",
        ),

        # Rules Complexity
        "min_conditions": ParamSpec(
            name="min_conditions",
            param_type=ParamType.INTEGER,
            default=1,
            constraint=ParamConstraint(min_value=1, max_value=10),
            description="Minimum number of conditions per rule",
            group="Options",
        ),
        "max_conditions": ParamSpec(
            name="max_conditions",
            param_type=ParamType.INTEGER,
            default=10,
            constraint=ParamConstraint(min_value=1, max_value=10),
            description="Maximum number of conditions per rule",
            group="Options",
        ),
        "min_exit_conditions": ParamSpec(
            name="min_exit_conditions",
            param_type=ParamType.INTEGER,
            default=1,
            constraint=ParamConstraint(min_value=1, max_value=10),
            description="Minimum number of exit conditions",
            group="Options",
        ),
        "max_exit_conditions": ParamSpec(
            name="max_exit_conditions",
            param_type=ParamType.INTEGER,
            default=10,
            constraint=ParamConstraint(min_value=1, max_value=10),
            description="Maximum number of exit conditions",
            group="Options",
        ),
        "min_period": ParamSpec(
            name="min_period",
            param_type=ParamType.INTEGER,
            default=1,
            constraint=ParamConstraint(min_value=1, max_value=500),
            description="Minimum indicator period",
            group="Options",
        ),
        "max_period": ParamSpec(
            name="max_period",
            param_type=ParamType.INTEGER,
            default=500,
            constraint=ParamConstraint(min_value=1, max_value=500),
            description="Maximum indicator period",
            group="Options",
        ),
        "min_shift": ParamSpec(
            name="min_shift",
            param_type=ParamType.INTEGER,
            default=0,
            constraint=ParamConstraint(min_value=0, max_value=100),
            description="Minimum shift for indicators",
            group="Options",
        ),
        "max_shift": ParamSpec(
            name="max_shift",
            param_type=ParamType.INTEGER,
            default=100,
            constraint=ParamConstraint(min_value=0, max_value=100),
            description="Maximum shift for indicators",
            group="Options",
        ),

        # Market Sides
        "market_sides": ParamSpec(
            name="market_sides",
            param_type=ParamType.ENUM,
            default="both",
            constraint=ParamConstraint(allowed_values=["both", "long", "short"]),
            description="Market sides to trade",
            group="Options",
        ),
        "entry_symmetry": ParamSpec(
            name="entry_symmetry",
            param_type=ParamType.BOOLEAN,
            default=True,
            description="Symmetric entry rules for long/short",
            group="Options",
        ),
        "exit_symmetry": ParamSpec(
            name="exit_symmetry",
            param_type=ParamType.BOOLEAN,
            default=True,
            description="Symmetric exit rules for long/short",
            group="Options",
        ),

        # SL/PT Options
        "sl_required": ParamSpec(
            name="sl_required",
            param_type=ParamType.BOOLEAN,
            default=True,
            description="Stop loss required",
            group="SL/PT",
        ),
        "sl_fixed_pips": ParamSpec(
            name="sl_fixed_pips",
            param_type=ParamType.BOOLEAN,
            default=False,
            description="Fixed pip stop loss",
            group="SL/PT",
        ),
        "min_sl_pips": ParamSpec(
            name="min_sl_pips",
            param_type=ParamType.INTEGER,
            default=10,
            constraint=ParamConstraint(min_value=1, max_value=1000),
            description="Minimum stop loss in pips",
            group="SL/PT",
        ),
        "max_sl_pips": ParamSpec(
            name="max_sl_pips",
            param_type=ParamType.INTEGER,
            default=300,
            constraint=ParamConstraint(min_value=1, max_value=10000),
            description="Maximum stop loss in pips",
            group="SL/PT",
        ),
        "min_sl_money": ParamSpec(
            name="min_sl_money",
            param_type=ParamType.INTEGER,
            default=0,
            constraint=ParamConstraint(min_value=0, max_value=100000),
            description="Minimum stop loss in money",
            group="SL/PT",
        ),
        "max_sl_money": ParamSpec(
            name="max_sl_money",
            param_type=ParamType.INTEGER,
            default=0,
            constraint=ParamConstraint(min_value=0, max_value=100000),
            description="Maximum stop loss in money",
            group="SL/PT",
        ),
        "sl_atr": ParamSpec(
            name="sl_atr",
            param_type=ParamType.BOOLEAN,
            default=False,
            description="ATR-based stop loss",
            group="SL/PT",
        ),
        "min_sl_atr_multiple": ParamSpec(
            name="min_sl_atr_multiple",
            param_type=ParamType.FLOAT,
            default=1.0,
            constraint=ParamConstraint(min_value=0.1, max_value=10.0),
            description="Minimum SL ATR multiple",
            group="SL/PT",
        ),
        "max_sl_atr_multiple": ParamSpec(
            name="max_sl_atr_multiple",
            param_type=ParamType.FLOAT,
            default=10.0,
            constraint=ParamConstraint(min_value=0.1, max_value=50.0),
            description="Maximum SL ATR multiple",
            group="SL/PT",
        ),
        "min_sl_atr_period": ParamSpec(
            name="min_sl_atr_period",
            param_type=ParamType.INTEGER,
            default=14,
            constraint=ParamConstraint(min_value=1, max_value=100),
            description="Minimum SL ATR period",
            group="SL/PT",
        ),
        "max_sl_atr_period": ParamSpec(
            name="max_sl_atr_period",
            param_type=ParamType.INTEGER,
            default=14,
            constraint=ParamConstraint(min_value=1, max_value=100),
            description="Maximum SL ATR period",
            group="SL/PT",
        ),
        "pt_required": ParamSpec(
            name="pt_required",
            param_type=ParamType.BOOLEAN,
            default=True,
            description="Profit target required",
            group="SL/PT",
        ),
        "pt_fixed_pips": ParamSpec(
            name="pt_fixed_pips",
            param_type=ParamType.BOOLEAN,
            default=False,
            description="Fixed pip profit target",
            group="SL/PT",
        ),
        "min_pt_pips": ParamSpec(
            name="min_pt_pips",
            param_type=ParamType.INTEGER,
            default=10,
            constraint=ParamConstraint(min_value=1, max_value=10000),
            description="Minimum profit target in pips",
            group="SL/PT",
        ),
        "max_pt_pips": ParamSpec(
            name="max_pt_pips",
            param_type=ParamType.INTEGER,
            default=300,
            constraint=ParamConstraint(min_value=1, max_value=10000),
            description="Maximum profit target in pips",
            group="SL/PT",
        ),
        "min_pt_money": ParamSpec(
            name="min_pt_money",
            param_type=ParamType.INTEGER,
            default=0,
            constraint=ParamConstraint(min_value=0, max_value=100000),
            description="Minimum profit target in money",
            group="SL/PT",
        ),
        "max_pt_money": ParamSpec(
            name="max_pt_money",
            param_type=ParamType.INTEGER,
            default=0,
            constraint=ParamConstraint(min_value=0, max_value=100000),
            description="Maximum profit target in money",
            group="SL/PT",
        ),
        "pt_atr": ParamSpec(
            name="pt_atr",
            param_type=ParamType.BOOLEAN,
            default=False,
            description="ATR-based profit target",
            group="SL/PT",
        ),
        "min_pt_atr_multiple": ParamSpec(
            name="min_pt_atr_multiple",
            param_type=ParamType.FLOAT,
            default=1.0,
            constraint=ParamConstraint(min_value=0.1, max_value=10.0),
            description="Minimum PT ATR multiple",
            group="SL/PT",
        ),
        "max_pt_atr_multiple": ParamSpec(
            name="max_pt_atr_multiple",
            param_type=ParamType.FLOAT,
            default=10.0,
            constraint=ParamConstraint(min_value=0.1, max_value=50.0),
            description="Maximum PT ATR multiple",
            group="SL/PT",
        ),
        "min_pt_atr_period": ParamSpec(
            name="min_pt_atr_period",
            param_type=ParamType.INTEGER,
            default=14,
            constraint=ParamConstraint(min_value=1, max_value=100),
            description="Minimum PT ATR period",
            group="SL/PT",
        ),
        "max_pt_atr_period": ParamSpec(
            name="max_pt_atr_period",
            param_type=ParamType.INTEGER,
            default=14,
            constraint=ParamConstraint(min_value=1, max_value=100),
            description="Maximum PT ATR period",
            group="SL/PT",
        ),
        "limit_slpt_rrr": ParamSpec(
            name="limit_slpt_rrr",
            param_type=ParamType.BOOLEAN,
            default=False,
            description="Limit SL/PT risk-reward ratio",
            group="SL/PT",
        ),
        "limit_slpt_rrr_from": ParamSpec(
            name="limit_slpt_rrr_from",
            param_type=ParamType.FLOAT,
            default=1.0,
            constraint=ParamConstraint(min_value=0.1, max_value=100.0),
            description="Minimum risk-reward ratio",
            group="SL/PT",
        ),
        "limit_slpt_rrr_to": ParamSpec(
            name="limit_slpt_rrr_to",
            param_type=ParamType.FLOAT,
            default=10.0,
            constraint=ParamConstraint(min_value=0.1, max_value=100.0),
            description="Maximum risk-reward ratio",
            group="SL/PT",
        ),
        "sl_value_type": ParamSpec(
            name="sl_value_type",
            param_type=ParamType.ENUM,
            default="pips",
            constraint=ParamConstraint(allowed_values=["pips", "money", "atr", "percent"]),
            description="Stop loss value type",
            group="SL/PT",
        ),
        "pt_value_type": ParamSpec(
            name="pt_value_type",
            param_type=ParamType.ENUM,
            default="pips",
            constraint=ParamConstraint(allowed_values=["pips", "money", "atr", "percent"]),
            description="Profit target value type",
            group="SL/PT",
        ),
        "sl_indicator_based": ParamSpec(
            name="sl_indicator_based",
            param_type=ParamType.BOOLEAN,
            default=False,
            description="Indicator-based stop loss",
            group="SL/PT",
        ),
        "pt_indicator_based": ParamSpec(
            name="pt_indicator_based",
            param_type=ParamType.BOOLEAN,
            default=False,
            description="Indicator-based profit target",
            group="SL/PT",
        ),
        "sl_percent": ParamSpec(
            name="sl_percent",
            param_type=ParamType.BOOLEAN,
            default=False,
            description="Stop loss as percentage",
            group="SL/PT",
        ),
        "min_sl_percent": ParamSpec(
            name="min_sl_percent",
            param_type=ParamType.FLOAT,
            default=0.5,
            constraint=ParamConstraint(min_value=0.1, max_value=100.0),
            description="Minimum SL percentage",
            group="SL/PT",
        ),
    },

    TaskType.FILTERING: {
        "conditions": ParamSpec(
            name="conditions",
            param_type=ParamType.STRING,
            default="NetProfit > 1000",
            description="Filter conditions expression",
            group="Options",
        ),
    },

    TaskType.RETEST: {
        "monte_carlo_runs": ParamSpec(
            name="monte_carlo_runs",
            param_type=ParamType.INTEGER,
            default=500,
            constraint=ParamConstraint(min_value=0, max_value=10000),
            description="Number of Monte Carlo simulations",
            group="MonteCarlo",
        ),
        "walkforward_cycles": ParamSpec(
            name="walkforward_cycles",
            param_type=ParamType.INTEGER,
            default=5,
            constraint=ParamConstraint(min_value=1, max_value=100),
            description="Walk-forward cycles",
            group="WalkForward",
        ),
    },

    TaskType.GOTO_TASK: {
        "target": ParamSpec(
            name="target",
            param_type=ParamType.STRING,
            required=True,
            description="Target task name to jump to",
            group="Options",
        ),
        "condition": ParamSpec(
            name="condition",
            param_type=ParamType.STRING,
            default="",
            description="Condition expression for jump",
            group="Options",
        ),
    },

    TaskType.OPTIMIZE: {
        "walkforward_cycles": ParamSpec(
            name="walkforward_cycles",
            param_type=ParamType.INTEGER,
            default=10,
            constraint=ParamConstraint(min_value=1, max_value=100),
            description="Walk-forward cycles for optimization",
            group="WalkForwardOptimization",
        ),
        "optimize_params": ParamSpec(
            name="optimize_params",
            param_type=ParamType.STRING,
            default="maxOptimizations=100",
            description="Optimization parameters (comma-separated key=value)",
            group="Optimize",
        ),
    },

    TaskType.AUTOMATIC_RETEST: {
        # AutomaticRetest uses specialized cross-checks (RetestWithHigherPrecision,
        # MonteCarloRetest, WalkForwardOptimization) - configured via CrossChecks XML
        "retest_with_higher_precision": ParamSpec(
            name="retest_with_higher_precision",
            param_type=ParamType.BOOLEAN,
            default=False,
            description="Enable retest with higher precision",
            group="MonteCarloRetest",
        ),
        "precision": ParamSpec(
            name="precision",
            param_type=ParamType.INTEGER,
            default=4,
            constraint=ParamConstraint(min_value=1, max_value=10),
            description="Precision for higher precision retest",
            group="MonteCarloRetest",
        ),
        "spread": ParamSpec(
            name="spread",
            param_type=ParamType.INTEGER,
            default=2,
            constraint=ParamConstraint(min_value=0, max_value=100),
            description="Spread for higher precision retest",
            group="MonteCarloRetest",
        ),
    },

    TaskType.AUTOMATIC_PORTFOLIO_BUILDER: {
        "search_type": ParamSpec(
            name="search_type",
            param_type=ParamType.ENUM,
            default="bruteforce",
            constraint=ParamConstraint(allowed_values=["bruteforce", "genetic", "random"]),
            description="Portfolio search algorithm",
            group="Options",
        ),
        "min_strategies": ParamSpec(
            name="min_strategies",
            param_type=ParamType.INTEGER,
            default=2,
            constraint=ParamConstraint(min_value=1, max_value=50),
            description="Minimum strategies in portfolio",
            group="Options",
        ),
        "max_strategies": ParamSpec(
            name="max_strategies",
            param_type=ParamType.INTEGER,
            default=8,
            constraint=ParamConstraint(min_value=1, max_value=50),
            description="Maximum strategies in portfolio",
            group="Options",
        ),
    },

    TaskType.CREATE_PORTFOLIO: {
        # Minimal params - mostly uses portfolio from previous stage
        "portfolio_name": ParamSpec(
            name="portfolio_name",
            param_type=ParamType.STRING,
            default="Portfolio",
            description="Portfolio name",
            group="Options",
        ),
    },

    TaskType.CUSTOM_ANALYSIS: {
        "analysis_type": ParamSpec(
            name="analysis_type",
            param_type=ParamType.ENUM,
            default="full",
            constraint=ParamConstraint(allowed_values=["full", "quick", "custom"]),
            description="Analysis depth",
            group="Options",
        ),
    },

    TaskType.LOG_DATABANK_STATS: {
        "log_details": ParamSpec(
            name="log_details",
            param_type=ParamType.BOOLEAN,
            default=True,
            description="Log detailed databank statistics",
            group="Options",
        ),
    },

    TaskType.SAVE_TO_FILES: {
        "save_path": ParamSpec(
            name="save_path",
            param_type=ParamType.STRING,
            default="",
            description="Save directory path",
            group="Options",
        ),
    },

    TaskType.LOAD_FROM_FILES: {
        "load_path": ParamSpec(
            name="load_path",
            param_type=ParamType.STRING,
            default="",
            description="Load directory path",
            group="Options",
        ),
    },

    TaskType.UPDATE_DATA: {
        "update_mode": ParamSpec(
            name="update_mode",
            param_type=ParamType.ENUM,
            default="append",
            constraint=ParamConstraint(allowed_values=["append", "replace", "merge"]),
            description="Data update mode",
            group="Options",
        ),
    },

    TaskType.WAIT_FOR: {
        "wait_seconds": ParamSpec(
            name="wait_seconds",
            param_type=ParamType.INTEGER,
            default=60,
            constraint=ParamConstraint(min_value=1, max_value=86400),
            description="Wait time in seconds",
            group="Options",
        ),
    },

    # ── Catalog types completed by (T2 / Gap 2) ──────────────────────────
    # Parameters for CallExternalScript, ClearDatabanks, DeleteFile,
    # Notification and StopAndStart come from the real SQX 144/2953 install:
    # internal/plugins/<Task>/task.xml (default settings) and
    # simpleSettings/simpleSettings.html (the UI binding that names each
    # field). No parameter below is guessed from the catalog name.

    TaskType.APPLY_MASS_CONFIG: {
        # TODO(gap-2): no readable parameter source. task.xml ships an empty
        # <ApplyMassConfig/> and simpleSettings.html only hosts a custom
        # component; the settings live in TaskApplyMassConfig.jar. Do not
        # invent parameter names until that source can be read.
    },

    TaskType.CALL_EXTERNAL_SCRIPT: {
        "file": ParamSpec(
            name="file",
            param_type=ParamType.STRING,
            default="",
            description="Script or executable to run",
            group="Options",
        ),
        "params": ParamSpec(
            name="params",
            param_type=ParamType.STRING,
            default="",
            description="Arguments passed to the script",
            group="Options",
        ),
        "type": ParamSpec(
            name="type",
            param_type=ParamType.STRING,
            default="",
            description="Script type (UI field CallExternalScriptType)",
            group="Options",
        ),
        "waitfor": ParamSpec(
            name="waitfor",
            param_type=ParamType.BOOLEAN,
            default=False,
            description="Wait for the script to finish before continuing",
            group="Options",
        ),
        "hours": ParamSpec(
            name="hours",
            param_type=ParamType.INTEGER,
            default=0,
            constraint=ParamConstraint(min_value=0, max_value=999),
            description="Hours to wait for the script (used with waitfor)",
            group="Options",
        ),
        "minutes": ParamSpec(
            name="minutes",
            param_type=ParamType.INTEGER,
            default=0,
            constraint=ParamConstraint(min_value=0, max_value=59),
            description="Minutes to wait for the script (used with waitfor)",
            group="Options",
        ),
    },

    TaskType.CLEAR_DATABANKS: {
        "databank": ParamSpec(
            name="databank",
            param_type=ParamType.STRING,
            default="Results",
            description="Databank to clear (default settings clear Results)",
            group="Data",
        ),
    },

    TaskType.DELETE_FILE: {
        "file": ParamSpec(
            name="file",
            param_type=ParamType.STRING,
            default="",
            description="File to delete",
            group="Options",
        ),
    },

    TaskType.NEURAL_NETWORK_TRAINER: {
        # TODO(gap-2): no readable parameter source. The task ships no
        # task.xml settings beyond <Databanks/> and has no simpleSettings
        # directory; the training parameters live in
        # TaskNeuralNetworkTrainer.jar. Do not invent names.
    },

    TaskType.NOTIFICATION: {
        "type": ParamSpec(
            name="type",
            param_type=ParamType.STRING,
            default="email",
            description="Notification type (SQX default: email)",
            group="Options",
        ),
        "email": ParamSpec(
            name="email",
            param_type=ParamType.STRING,
            default="",
            description="Recipient email address",
            group="Options",
        ),
        "wait": ParamSpec(
            name="wait",
            param_type=ParamType.BOOLEAN,
            default=False,
            description="Wait for the notification before continuing",
            group="Options",
        ),
    },

    TaskType.STOP_AND_START: {
        "startAnother": ParamSpec(
            name="startAnother",
            param_type=ParamType.BOOLEAN,
            default=False,
            description="Start another project after stopping",
            group="Options",
        ),
        "projectName": ParamSpec(
            name="projectName",
            param_type=ParamType.STRING,
            default="",
            description="Custom project to start (from the available projects)",
            group="Options",
        ),
        "skipToFirstProject": ParamSpec(
            name="skipToFirstProject",
            param_type=ParamType.BOOLEAN,
            default=False,
            description="Restart from the first project in the list",
            group="Options",
        ),
    },
}


# ── Helper Functions ─────────────────────────────────────────────────────


def get_task_schema(task_type: TaskType) -> dict[str, ParamSpec]:
    """Get the parameter schema for a task type."""
    return TASK_PARAM_SCHEMAS.get(task_type, {})


def validate_task_params(task_type: TaskType, params: dict[str, Any]) -> list[str]:
    """Validate parameters against task schema. Returns list of errors."""
    schema = get_task_schema(task_type)
    errors = []

    for param_name, spec in schema.items():
        value = params.get(param_name)
        if spec.required and param_name not in params:
            errors.append(f"Required parameter '{param_name}' missing for {task_type.value}")
        elif param_name in params:
            if not spec.validate(params[param_name]):
                errors.append(
                    f"Parameter '{param_name}' failed validation for {task_type.value}: "
                    f"value={params[param_name]}"
                )

    # Check for unknown parameters
    for param_name in params:
        if param_name not in schema:
            errors.append(f"Unknown parameter '{param_name}' for {task_type.value}")

    return errors


def coerce_params(task_type: TaskType, params: dict[str, Any]) -> dict[str, Any]:
    """Coerce parameters to correct types using schema defaults."""
    schema = get_task_schema(task_type)
    coerced = {}

    for param_name, spec in schema.items():
        value = params.get(param_name, spec.default)
        coerced[param_name] = spec.coerce(value)

    # Include any extra params not in schema (pass through)
    for param_name, value in params.items():
        if param_name not in schema:
            coerced[param_name] = value

    return coerced


def get_all_task_types() -> list[TaskType]:
    """Get all registered task types."""
    return list(TASK_PARAM_SCHEMAS.keys())


def get_param_groups(task_type: TaskType) -> list[str]:
    """Get unique parameter groups for a task type."""
    schema = get_task_schema(task_type)
    groups = set()
    for spec in schema.values():
        groups.add(spec.group)
    return sorted(groups)


# ── Validation Helpers for ExplorationDecision → Task Params ───────────────

EXPLORATION_TO_TASK_PARAMS: dict[str, list[str]] = {
    # ExplorationDecision field → list of task parameters it influences
    "capital_usd": ["min_lot_size", "max_lot_size", "risk_per_trade_usd"],
    "leverage": ["max_lot_size"],
    "timeframe": ["walkforward_cycles", "monte_carlo_runs"],
    "market": ["symbol", "pip_value", "min_lot_size"],
    "instruments": ["symbol", "min_lot_size"],
    "capital_limits": ["max_drawdown_pct", "risk_per_trade_usd", "max_concurrent_positions"],
    "risk_management": ["stop_loss_pips", "take_profit_pips", "rr_ratio", "max_portfolio_heat_pct"],
    "money_management": ["position_sizing_method", "fixed_fractional_pct"],
    "statistical_edge": ["expected_sharpe", "win_rate", "profit_factor"],
    "broker_info": ["commission_per_lot", "slippage_pips", "spread_pips", "swap_long", "swap_short"],
}


def map_exploration_to_task_params(
    exploration_decision: Any,
    task_type: TaskType,
) -> dict[str, Any]:
    """Map ExplorationDecision fields to task parameters for a specific task type."""
    # This is a simplified mapping - the full ParamMapper does more sophisticated mapping
    schema = get_task_schema(task_type)
    params = {}

    # For now, return empty - the full ParamMapper handles this
    return {}