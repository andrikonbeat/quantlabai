"""Parameter space definition for Bayesian Optimization.

Defines the search space with bounds, types, and constraints for
parameters that the Bayesian optimizer will explore.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ParamType(Enum):
    """Parameter type enumeration."""

    CONTINUOUS = "continuous"
    INTEGER = "integer"
    CATEGORICAL = "categorical"
    LOG_UNIFORM = "log_uniform"


@dataclass(frozen=True)
class ParameterConstraint:
    """Constraint on a parameter.

    Attributes:
        name: Parameter name this constraint applies to.
        constraint_type: Type of constraint (e.g., "sum_lt", "ratio", "depends_on").
        params: Additional parameters for the constraint.
        message: Human-readable description.
    """

    name: str
    constraint_type: str
    params: dict[str, Any] = field(default_factory=dict)
    message: str = ""


@dataclass(frozen=True)
class ParameterSpec:
    """Specification for a single optimization parameter.

    Attributes:
        name: Unique parameter identifier.
        param_type: Type of parameter (continuous, integer, categorical, log_uniform).
        bounds: Tuple of (min, max) for continuous/integer/log_uniform.
            For categorical, this is the list of allowed values.
        default: Default value if not specified.
        description: Human-readable description.
        constraints: List of constraints involving this parameter.
    """

    name: str
    param_type: ParamType
    bounds: tuple[float, float] | list[Any]
    default: Any = None
    description: str = ""
    constraints: list[ParameterConstraint] = field(default_factory=list)

    def validate(self, value: Any) -> bool:
        """Validate a value against this parameter's specification."""
        if self.param_type == ParamType.CONTINUOUS:
            if not isinstance(value, (int, float)):
                return False
            low, high = self.bounds
            return low <= value <= high
        elif self.param_type == ParamType.INTEGER:
            if not isinstance(value, int):
                return False
            low, high = self.bounds
            return low <= value <= high
        elif self.param_type == ParamType.LOG_UNIFORM:
            if not isinstance(value, (int, float)) or value <= 0:
                return False
            import math
            low, high = self.bounds
            log_val = math.log10(value)
            return low <= log_val <= high
        elif self.param_type == ParamType.CATEGORICAL:
            return value in self.bounds
        return False

    def sample(self) -> Any:
        """Sample a random value from this parameter's distribution."""
        import random

        if self.param_type == ParamType.CONTINUOUS:
            low, high = self.bounds
            return random.uniform(low, high)
        elif self.param_type == ParamType.INTEGER:
            low, high = self.bounds
            return random.randint(int(low), int(high))
        elif self.param_type == ParamType.LOG_UNIFORM:
            low, high = self.bounds
            return 10 ** random.uniform(low, high)
        elif self.param_type == ParamType.CATEGORICAL:
            return random.choice(self.bounds)
        raise ValueError(f"Unknown param type: {self.param_type}")


@dataclass
class ParameterSpace:
    """Defines the complete search space for Bayesian optimization.

    A parameter space is a collection of ParameterSpec objects that
    defines all tunable parameters, their bounds, types, and constraints.

    Example:
        >>> space = ParameterSpace([
        ...     ParameterSpec("learning_rate", ParamType.LOG_UNIFORM, (-4, -1)),
        ...     ParameterSpec("batch_size", ParamType.CATEGORICAL, [16, 32, 64, 128]),
        ...     ParameterSpec("dropout", ParamType.CONTINUOUS, (0.0, 0.5)),
        ... ])
    """

    parameters: list[ParameterSpec] = field(default_factory=list)
    constraints: list[ParameterConstraint] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._by_name = {p.name: p for p in self.parameters}

    def add(self, spec: ParameterSpec) -> ParameterSpace:
        """Add a parameter spec (fluent API)."""
        self.parameters.append(spec)
        self._by_name[spec.name] = spec
        return self

    def get(self, name: str) -> ParameterSpec | None:
        """Get parameter spec by name."""
        return self._by_name.get(name)

    def names(self) -> list[str]:
        """Return list of parameter names in order."""
        return [p.name for p in self.parameters]

    def bounds_array(self) -> list[tuple[float, float]]:
        """Return bounds as list of (min, max) tuples for continuous params.

        Used by surrogate models that expect numeric bounds.
        Categorical params are mapped to integer indices.
        """
        result = []
        for p in self.parameters:
            if p.param_type == ParamType.CATEGORICAL:
                result.append((0, len(p.bounds) - 1))
            else:
                low, high = p.bounds
                result.append((float(low), float(high)))
        return result

    def param_types(self) -> list[ParamType]:
        """Return list of parameter types in order."""
        return [p.param_type for p in self.parameters]

    def defaults(self) -> dict[str, Any]:
        """Return dict of parameter defaults."""
        return {p.name: p.default for p in self.parameters if p.default is not None}

    def validate_point(self, point: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate a full parameter point.

        Returns:
            Tuple of (is_valid, list_of_error_messages).
        """
        errors = []
        for name, value in point.items():
            spec = self.get(name)
            if spec is None:
                errors.append(f"Unknown parameter: {name}")
                continue
            if not spec.validate(value):
                errors.append(f"Parameter '{name}' value {value} out of bounds or invalid type")
        # Check global constraints
        for constraint in self.constraints:
            # Simplified constraint checking - can be extended
            pass
        return len(errors) == 0, errors

    def to_vector(self, point: dict[str, Any]) -> list[float]:
        """Convert a parameter point to a numeric vector for surrogate models.

        Categorical parameters are converted to integer indices.
        """
        vec = []
        for p in self.parameters:
            value = point.get(p.name, p.default)
            if p.param_type == ParamType.CATEGORICAL:
                try:
                    idx = p.bounds.index(value)
                    vec.append(float(idx))
                except ValueError:
                    vec.append(0.0)
            elif p.param_type == ParamType.LOG_UNIFORM:
                vec.append(float(value))
            else:
                vec.append(float(value))
        return vec

    def from_vector(self, vec: list[float]) -> dict[str, Any]:
        """Convert a numeric vector back to a parameter point dictionary."""
        point = {}
        for i, p in enumerate(self.parameters):
            if p.param_type == ParamType.CATEGORICAL:
                idx = int(round(vec[i]))
                idx = max(0, min(idx, len(p.bounds) - 1))
                point[p.name] = p.bounds[idx]
            elif p.param_type == ParamType.INTEGER:
                val = int(round(vec[i]))
                low, high = p.bounds
                point[p.name] = max(int(low), min(val, int(high)))
            elif p.param_type == ParamType.LOG_UNIFORM:
                val = vec[i]
                low, high = p.bounds
                # val is in linear space, bounds are in log10 space
                import math
                log_val = math.log10(max(val, 1e-12))
                log_val = max(low, min(log_val, high))
                point[p.name] = 10 ** log_val
            else:  # CONTINUOUS
                val = vec[i]
                low, high = p.bounds
                point[p.name] = max(low, min(val, high))
        return point

    @classmethod
    def from_exploration_decision(cls, decision) -> ParameterSpace:
        """Create a ParameterSpace from an ExplorationDecision artifact.

        Maps the 13-field exploration decision to a parameter space
        suitable for Bayesian optimization of SQX strategy parameters.
        """
        from quantlab.exploration.models import ExplorationDecision

        if not isinstance(decision, ExplorationDecision):
            raise TypeError("Expected ExplorationDecision")

        space = cls()

        # Map capital limits to risk parameters
        capital_limits = decision.capital_limits or {}
        space.add(ParameterSpec(
            name="risk_per_trade_pct",
            param_type=ParamType.CONTINUOUS,
            bounds=(0.5, 5.0),
            default=capital_limits.get("risk_per_trade_usd", 100) / decision.capital_usd * 100,
            description="Risk per trade as percentage of capital",
        ))

        space.add(ParameterSpec(
            name="max_drawdown_pct",
            param_type=ParamType.CONTINUOUS,
            bounds=(5.0, 30.0),
            default=capital_limits.get("max_drawdown_pct", 15.0),
            description="Maximum allowed drawdown percentage",
        ))

        # Map operational restrictions to time/session parameters
        op_restrictions = decision.operational_restrictions or {}
        space.add(ParameterSpec(
            name="trading_hours_start",
            param_type=ParamType.INTEGER,
            bounds=(0, 23),
            default=op_restrictions.get("trading_hours_start", 8),
            description="Trading session start hour (UTC)",
        ))

        space.add(ParameterSpec(
            name="trading_hours_end",
            param_type=ParamType.INTEGER,
            bounds=(0, 23),
            default=op_restrictions.get("trading_hours_end", 20),
            description="Trading session end hour (UTC)",
        ))

        # Map risk management to stop/trail parameters
        risk_mgmt = decision.risk_management or {}
        space.add(ParameterSpec(
            name="stop_loss_pips",
            param_type=ParamType.INTEGER,
            bounds=(10, 200),
            default=risk_mgmt.get("stop_loss_pips", 50),
            description="Stop loss in pips",
        ))

        space.add(ParameterSpec(
            name="take_profit_pips",
            param_type=ParamType.INTEGER,
            bounds=(10, 500),
            default=risk_mgmt.get("take_profit_pips", 100),
            description="Take profit in pips",
        ))

        space.add(ParameterSpec(
            name="trailing_stop_pips",
            param_type=ParamType.INTEGER,
            bounds=(0, 100),
            default=risk_mgmt.get("trailing_stop_pips", 0),
            description="Trailing stop in pips (0 = disabled)",
        ))

        # Map money management to position sizing
        money_mgmt = decision.money_management or {}
        space.add(ParameterSpec(
            name="position_sizing_method",
            param_type=ParamType.CATEGORICAL,
            bounds=["fixed_fractional", "kelly", "volatility_adjusted", "fixed_lot"],
            default=money_mgmt.get("position_sizing_method", "fixed_fractional"),
            description="Position sizing method",
        ))

        space.add(ParameterSpec(
            name="fixed_fractional_pct",
            param_type=ParamType.CONTINUOUS,
            bounds=(0.1, 10.0),
            default=money_mgmt.get("fixed_fractional_pct", 1.0),
            description="Fixed fractional percentage",
        ))

        # Statistical edge informs parameter bounds
        stat_edge = decision.statistical_edge or {}
        expected_sharpe = stat_edge.get("expected_sharpe", 1.0)
        # Wider bounds if edge is uncertain
        sharpe_factor = max(0.5, min(2.0, 1.0 / max(0.1, expected_sharpe)))

        space.add(ParameterSpec(
            name="max_concurrent_positions",
            param_type=ParamType.INTEGER,
            bounds=(1, max(5, int(10 * sharpe_factor))),
            default=capital_limits.get("max_concurrent_positions", 3),
            description="Maximum concurrent positions",
        ))

        # Indicator parameters (generic, can be extended per strategy)
        space.add(ParameterSpec(
            name="indicator_fast_period",
            param_type=ParamType.INTEGER,
            bounds=(2, 50),
            default=10,
            description="Fast indicator period (e.g., EMA fast)",
        ))

        space.add(ParameterSpec(
            name="indicator_slow_period",
            param_type=ParamType.INTEGER,
            bounds=(10, 200),
            default=30,
            description="Slow indicator period (e.g., EMA slow)",
        ))

        space.add(ParameterSpec(
            name="signal_threshold",
            param_type=ParamType.CONTINUOUS,
            bounds=(0.1, 3.0),
            default=1.0,
            description="Signal threshold multiplier",
        ))

        # Add constraint: fast < slow
        space.constraints.append(ParameterConstraint(
            name="indicator_periods",
            constraint_type="lt",
            params={"left": "indicator_fast_period", "right": "indicator_slow_period"},
            message="Fast period must be less than slow period",
        ))

        return space


def create_default_sqx_space() -> ParameterSpace:
    """Create a default SQX parameter space for strategy optimization.

    This provides a reasonable starting space for typical SQX strategy
    parameters when no ExplorationDecision is available.
    """
    space = ParameterSpace()

    # Risk parameters
    space.add(ParameterSpec("risk_per_trade_pct", ParamType.CONTINUOUS, (0.5, 5.0), default=1.0))
    space.add(ParameterSpec("max_drawdown_pct", ParamType.CONTINUOUS, (5.0, 30.0), default=15.0))
    space.add(ParameterSpec("max_concurrent_positions", ParamType.INTEGER, (1, 10), default=3))

    # Stop/Take profit
    space.add(ParameterSpec("stop_loss_pips", ParamType.INTEGER, (10, 200), default=50))
    space.add(ParameterSpec("take_profit_pips", ParamType.INTEGER, (10, 500), default=100))
    space.add(ParameterSpec("trailing_stop_pips", ParamType.INTEGER, (0, 100), default=0))

    # Position sizing
    space.add(ParameterSpec("position_sizing_method", ParamType.CATEGORICAL,
                           ["fixed_fractional", "kelly", "volatility_adjusted", "fixed_lot"],
                           default="fixed_fractional"))
    space.add(ParameterSpec("fixed_fractional_pct", ParamType.CONTINUOUS, (0.1, 10.0), default=1.0))

    # Indicator parameters
    space.add(ParameterSpec("indicator_fast_period", ParamType.INTEGER, (2, 50), default=10))
    space.add(ParameterSpec("indicator_slow_period", ParamType.INTEGER, (10, 200), default=30))
    space.add(ParameterSpec("signal_threshold", ParamType.CONTINUOUS, (0.1, 3.0), default=1.0))

    # Timeframe/session
    space.add(ParameterSpec("trading_hours_start", ParamType.INTEGER, (0, 23), default=8))
    space.add(ParameterSpec("trading_hours_end", ParamType.INTEGER, (0, 23), default=20))

    # Constraints
    space.constraints.append(ParameterConstraint(
        name="indicator_periods",
        constraint_type="lt",
        params={"left": "indicator_fast_period", "right": "indicator_slow_period"},
        message="Fast period must be less than slow period",
    ))

    space.constraints.append(ParameterConstraint(
        name="trading_hours",
        constraint_type="lt",
        params={"left": "trading_hours_start", "right": "trading_hours_end"},
        message="Trading start must be before end",
    ))

    return space