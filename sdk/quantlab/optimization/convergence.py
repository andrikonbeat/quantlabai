"""Convergence criteria for Bayesian Optimization.

Defines stopping conditions for the optimization loop including
EI threshold, patience, maximum iterations, and custom criteria.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np


class ConvergenceReason(Enum):
    """Reason for optimization convergence/stopping."""

    MAX_ITERATIONS = "max_iterations"
    EI_THRESHOLD = "ei_threshold"
    PATIENCE_EXHAUSTED = "patience_exhausted"
    TARGET_REACHED = "target_reached"
    TIME_BUDGET = "time_budget"
    MANUAL_STOP = "manual_stop"
    DIVERGED = "diverged"
    NO_IMPROVEMENT = "no_improvement"


@dataclass
class ConvergenceState:
    """Current state of convergence monitoring.

    Attributes:
        converged: Whether optimization has converged.
        reason: Reason for convergence if converged.
        iteration: Current iteration number.
        best_value: Best objective value observed.
        best_iteration: Iteration where best value was found.
        patience_counter: Iterations since last improvement.
        ei_values: Recent EI values for threshold checking.
        message: Human-readable status message.
    """

    converged: bool = False
    reason: ConvergenceReason | None = None
    iteration: int = 0
    best_value: float = -np.inf
    best_iteration: int = -1
    patience_counter: int = 0
    ei_values: list[float] = None  # type: ignore[assignment]
    message: str = "Optimization running"

    def __post_init__(self) -> None:
        if self.ei_values is None:
            self.ei_values = []

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "converged": self.converged,
            "reason": self.reason.value if self.reason else None,
            "iteration": self.iteration,
            "best_value": self.best_value,
            "best_iteration": self.best_iteration,
            "patience_counter": self.patience_counter,
            "recent_ei_mean": float(np.mean(self.ei_values)) if self.ei_values else 0.0,
            "message": self.message,
        }


class ConvergenceCriterion(ABC):
    """Abstract base class for convergence criteria."""

    @abstractmethod
    def check(
        self,
        state: ConvergenceState,
        current_value: float,
        ei_value: float | None = None,
    ) -> ConvergenceState:
        """Check convergence and update state.

        Args:
            state: Current convergence state.
            current_value: Current objective value.
            ei_value: Current Expected Improvement value (if available).

        Returns:
            Updated ConvergenceState.
        """
        pass

    @abstractmethod
    def describe(self) -> str:
        """Return human-readable description of this criterion."""
        pass


class MaxIterationsCriterion(ConvergenceCriterion):
    """Stop after maximum number of iterations."""

    def __init__(self, max_iterations: int) -> None:
        """Initialize max iterations criterion.

        Args:
            max_iterations: Maximum number of optimization iterations.
        """
        self.max_iterations = max_iterations

    def check(
        self,
        state: ConvergenceState,
        current_value: float,
        ei_value: float | None = None,
    ) -> ConvergenceState:
        state.iteration += 1
        if state.iteration >= self.max_iterations:
            state.converged = True
            state.reason = ConvergenceReason.MAX_ITERATIONS
            state.message = f"Maximum iterations ({self.max_iterations}) reached"
        return state

    def describe(self) -> str:
        return f"Max iterations: {self.max_iterations}"


class EIThresholdCriterion(ConvergenceCriterion):
    """Stop when Expected Improvement falls below threshold.

    When EI is consistently low, the optimizer is no longer
    finding meaningful improvements.
    """

    def __init__(
        self,
        threshold: float = 1e-4,
        window: int = 5,
        min_iterations: int = 10,
    ) -> None:
        """Initialize EI threshold criterion.

        Args:
            threshold: EI threshold below which to stop.
            window: Number of recent iterations to average EI over.
            min_iterations: Minimum iterations before this criterion activates.
        """
        self.threshold = threshold
        self.window = window
        self.min_iterations = min_iterations

    def check(
        self,
        state: ConvergenceState,
        current_value: float,
        ei_value: float | None = None,
    ) -> ConvergenceState:
        if ei_value is not None:
            state.ei_values.append(ei_value)
            # Keep only recent window
            if len(state.ei_values) > self.window:
                state.ei_values = state.ei_values[-self.window:]

        if state.iteration >= self.min_iterations and len(state.ei_values) >= self.window:
            avg_ei = float(np.mean(state.ei_values))
            if avg_ei < self.threshold:
                state.converged = True
                state.reason = ConvergenceReason.EI_THRESHOLD
                state.message = f"Average EI ({avg_ei:.2e}) below threshold ({self.threshold:.2e}) over {self.window} iterations"

        return state

    def describe(self) -> str:
        return f"EI threshold: {self.threshold} (window={self.window}, min_iter={self.min_iterations})"


class PatienceCriterion(ConvergenceCriterion):
    """Stop when no improvement for N consecutive iterations.

    Classic early stopping based on patience.
    """

    def __init__(self, patience: int = 20, min_improvement: float = 1e-6) -> None:
        """Initialize patience criterion.

        Args:
            patience: Number of iterations to wait for improvement.
            min_improvement: Minimum relative improvement to reset patience.
        """
        self.patience = patience
        self.min_improvement = min_improvement

    def check(
        self,
        state: ConvergenceState,
        current_value: float,
        ei_value: float | None = None,
    ) -> ConvergenceState:
        if current_value > state.best_value + self.min_improvement:
            state.best_value = current_value
            state.best_iteration = state.iteration
            state.patience_counter = 0
        else:
            state.patience_counter += 1

        if state.patience_counter >= self.patience:
            state.converged = True
            state.reason = ConvergenceReason.PATIENCE_EXHAUSTED
            state.message = f"No improvement for {self.patience} iterations (best: {state.best_value:.4f} at iter {state.best_iteration})"

        return state

    def describe(self) -> str:
        return f"Patience: {self.patience} iterations (min improvement: {self.min_improvement})"


class TargetValueCriterion(ConvergenceCriterion):
    """Stop when objective reaches a target value."""

    def __init__(self, target_value: float) -> None:
        """Initialize target value criterion.

        Args:
            target_value: Objective value at which to stop.
        """
        self.target_value = target_value

    def check(
        self,
        state: ConvergenceState,
        current_value: float,
        ei_value: float | None = None,
    ) -> ConvergenceState:
        if current_value >= self.target_value:
            state.converged = True
            state.reason = ConvergenceReason.TARGET_REACHED
            state.message = f"Target value {self.target_value} reached (current: {current_value:.4f})"
        return state

    def describe(self) -> str:
        return f"Target value: {self.target_value}"


class DivergenceCriterion(ConvergenceCriterion):
    """Stop if optimization appears to be diverging.

    Detects if recent values are significantly worse than best,
    suggesting numerical issues or inappropriate search space.
    """

    def __init__(
        self,
        divergence_threshold: float = 10.0,
        window: int = 10,
    ) -> None:
        """Initialize divergence criterion.

        Args:
            divergence_threshold: Factor by which recent values can be worse than best.
            window: Number of recent iterations to check.
        """
        self.divergence_threshold = divergence_threshold
        self.window = window
        self._recent_values: list[float] = []

    def check(
        self,
        state: ConvergenceState,
        current_value: float,
        ei_value: float | None = None,
    ) -> ConvergenceState:
        self._recent_values.append(current_value)
        if len(self._recent_values) > self.window:
            self._recent_values = self._recent_values[-self.window:]

        if state.best_value > -np.inf and len(self._recent_values) >= self.window:
            avg_recent = float(np.mean(self._recent_values))
            if avg_recent < state.best_value / self.divergence_threshold:
                state.converged = True
                state.reason = ConvergenceReason.DIVERGED
                state.message = (
                    f"Divergence detected: recent avg ({avg_recent:.4f}) "
                    f"is {self.divergence_threshold}x worse than best ({state.best_value:.4f})"
                )

        return state

    def describe(self) -> str:
        return f"Divergence detection: threshold={self.divergence_threshold}x, window={self.window}"


class CompositeConvergenceCriterion(ConvergenceCriterion):
    """Composite criterion that combines multiple criteria (OR logic).

    Optimization stops when ANY sub-criterion triggers.
    """

    def __init__(self, criteria: list[ConvergenceCriterion]) -> None:
        """Initialize composite criterion.

        Args:
            criteria: List of convergence criteria to combine.
        """
        self.criteria = criteria

    def check(
        self,
        state: ConvergenceState,
        current_value: float,
        ei_value: float | None = None,
    ) -> ConvergenceState:
        for criterion in self.criteria:
            state = criterion.check(state, current_value, ei_value)
            if state.converged:
                break
        return state

    def describe(self) -> str:
        return " OR ".join(c.describe() for c in self.criteria)


class ConvergenceMonitor:
    """Monitors convergence during Bayesian optimization.

    Combines multiple convergence criteria and tracks state
    throughout the optimization run.
    """

    def __init__(
        self,
        criteria: list[ConvergenceCriterion] | None = None,
        max_iterations: int = 100,
        ei_threshold: float = 1e-4,
        patience: int = 20,
        target_value: float | None = None,
    ) -> None:
        """Initialize convergence monitor.

        Args:
            criteria: Custom list of criteria (overrides individual params if provided).
            max_iterations: Maximum iterations (used if criteria not provided).
            ei_threshold: EI threshold (used if criteria not provided).
            patience: Patience for no-improvement (used if criteria not provided).
            target_value: Target objective value (used if criteria not provided).
        """
        if criteria is not None:
            self.criteria = criteria
        else:
            self.criteria = [
                MaxIterationsCriterion(max_iterations),
                EIThresholdCriterion(ei_threshold),
                PatienceCriterion(patience),
            ]
            if target_value is not None:
                self.criteria.append(TargetValueCriterion(target_value))

        self.state = ConvergenceState()
        self.history: list[ConvergenceState] = []

    def step(
        self,
        current_value: float,
        ei_value: float | None = None,
    ) -> ConvergenceState:
        """Process one optimization step.

        Args:
            current_value: Current objective value.
            ei_value: Current EI value (if available).

        Returns:
            Updated ConvergenceState.
        """
        # Update best value tracking
        if current_value > self.state.best_value:
            self.state.best_value = current_value
            self.state.best_iteration = self.state.iteration

        # Check all criteria
        for criterion in self.criteria:
            self.state = criterion.check(self.state, current_value, ei_value)
            if self.state.converged:
                break

        # Record state snapshot
        self.history.append(ConvergenceState(
            converged=self.state.converged,
            reason=self.state.reason,
            iteration=self.state.iteration,
            best_value=self.state.best_value,
            best_iteration=self.state.best_iteration,
            patience_counter=self.state.patience_counter,
            ei_values=self.state.ei_values.copy() if self.state.ei_values else [],
            message=self.state.message,
        ))

        return self.state

    def is_converged(self) -> bool:
        """Check if optimization has converged."""
        return self.state.converged

    def get_reason(self) -> ConvergenceReason | None:
        """Get convergence reason."""
        return self.state.reason

    def get_state(self) -> ConvergenceState:
        """Get current convergence state."""
        return self.state

    def describe(self) -> str:
        """Get human-readable description of all criteria."""
        return "; ".join(c.describe() for c in self.criteria)


def create_default_monitor(
    max_iterations: int = 100,
    ei_threshold: float = 1e-4,
    patience: int = 20,
    target_value: float | None = None,
) -> ConvergenceMonitor:
    """Create a default convergence monitor with standard criteria.

    Args:
        max_iterations: Maximum iterations.
        ei_threshold: EI threshold for stopping.
        patience: Patience for no-improvement stopping.
        target_value: Optional target value to stop at.

    Returns:
        Configured ConvergenceMonitor.
    """
    return ConvergenceMonitor(
        max_iterations=max_iterations,
        ei_threshold=ei_threshold,
        patience=patience,
        target_value=target_value,
    )