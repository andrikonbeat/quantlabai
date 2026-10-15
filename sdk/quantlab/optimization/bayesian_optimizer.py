"""Bayesian Optimizer core implementation.

Main entry point for Bayesian optimization with Gaussian Process surrogate
and Expected Improvement acquisition. Integrates with Knowledge Lake for
persistence and session continuity.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import numpy as np

from quantlab.optimization.acquisition import (
    AcquisitionFunction,
    ExpectedImprovement,
    create_acquisition,
)
from quantlab.optimization.convergence import (
    ConvergenceMonitor,
    ConvergenceReason,
    ConvergenceState,
    MaxIterationsCriterion,
    create_default_monitor,
)
from quantlab.optimization.space import create_default_sqx_space
from quantlab.optimization.history import HistoryBuffer, OptimizationStep
from quantlab.optimization.space import ParameterSpace, ParameterSpec, ParamType
from quantlab.optimization.surrogate import (
    GaussianProcessSurrogate,
    RandomForestSurrogate,
    SurrogateModel,
    SurrogatePrediction,
    create_surrogate,
)


@dataclass
class BayesianOptimizerConfig:
    """Configuration for BayesianOptimizer.

    Attributes:
        parameter_space: ParameterSpace defining the search space.
        surrogate_model: Surrogate model type ("gp" or "rf").
        acquisition_function: Acquisition function type ("ei", "ucb", "pi", "ts").
        acquisition_params: Additional parameters for acquisition function.
        convergence_monitor: ConvergenceMonitor for stopping criteria.
        random_state: Random seed for reproducibility.
        n_initial_points: Number of random initial points before BO starts.
        maximize: Whether to maximize (True) or minimize (False) the objective.
    """

    parameter_space: ParameterSpace
    surrogate_model: str = "gp"
    acquisition_function: str = "ei"
    acquisition_params: dict[str, Any] = field(default_factory=dict)
    convergence_monitor: ConvergenceMonitor | None = None
    random_state: int | None = None
    n_initial_points: int = 5
    maximize: bool = True


@dataclass
class OptimizationResult:
    """Result of a Bayesian optimization run.

    Attributes:
        best_parameters: Best parameter values found.
        best_value: Best objective value.
        n_evaluations: Total number of function evaluations.
        history: Full optimization history.
        convergence_state: Final convergence state.
        campaign_id: Campaign identifier.
        optimizer_id: Unique optimizer run identifier.
        started_at: ISO timestamp of start.
        completed_at: ISO timestamp of completion.
        total_time_seconds: Total optimization time.
    """

    best_parameters: dict[str, Any]
    best_value: float
    n_evaluations: int
    history: HistoryBuffer
    convergence_state: ConvergenceState
    campaign_id: str
    optimizer_id: str
    started_at: str
    completed_at: str
    total_time_seconds: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "best_parameters": self.best_parameters,
            "best_value": self.best_value,
            "n_evaluations": self.n_evaluations,
            "convergence": self.convergence_state.to_dict(),
            "campaign_id": self.campaign_id,
            "optimizer_id": self.optimizer_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_time_seconds": self.total_time_seconds,
        }


class BayesianOptimizer:
    """Bayesian Optimization engine with GP surrogate and EI acquisition.

    Performs sequential model-based optimization of expensive black-box
    functions. Supports session persistence via Knowledge Lake.

    Example:
        >>> space = create_default_sqx_space()
        >>> optimizer = BayesianOptimizer(space)
        >>> result = optimizer.optimize(objective_function, n_iterations=50)
        >>> print(result.best_parameters)
    """

    def __init__(
        self,
        config: BayesianOptimizerConfig,
        knowledge_lake_path: str | Path | None = None,
        campaign_id: str | None = None,
    ) -> None:
        """Initialize Bayesian optimizer.

        Args:
            config: BayesianOptimizerConfig with all settings.
            knowledge_lake_path: Path to Knowledge Lake for persistence.
            campaign_id: Campaign identifier for history persistence.
        """
        self.config = config
        self.space = config.parameter_space
        self.knowledge_lake_path = Path(knowledge_lake_path) if knowledge_lake_path else None

        if campaign_id is None:
            campaign_id = f"bayesopt_{uuid.uuid4().hex[:8]}"

        # Initialize surrogate model
        self.surrogate: SurrogateModel = create_surrogate(
            config.surrogate_model,
            random_state=config.random_state,
        )

        # Initialize acquisition function
        self.acquisition: AcquisitionFunction = create_acquisition(
            config.acquisition_function,
            **config.acquisition_params,
        )

        # Initialize convergence monitor
        self.convergence = config.convergence_monitor or create_default_monitor()

        # Initialize history buffer
        self.history = HistoryBuffer(
            campaign_id=campaign_id,
            knowledge_lake_path=knowledge_lake_path,
        )

        # Optimization state
        self._optimizer_id = str(uuid.uuid4())[:8]
        self._started_at: str | None = None
        self._objective_func: Callable[[dict[str, Any]], float] | None = None
        self._rng = np.random.RandomState(config.random_state)

    def suggest(self, n_suggestions: int = 1) -> list[dict[str, Any]]:
        """Suggest next parameter(s) to evaluate.

        Uses the acquisition function to find the most promising points.

        Args:
            n_suggestions: Number of suggestions to return.

        Returns:
            List of parameter dictionaries.
        """
        if len(self.history) == 0:
            # No history yet - return random initial points
            return [self.space.defaults() or self._sample_random_point() for _ in range(n_suggestions)]

        # Fit surrogate on current history
        X, y, _ = self.history.get_arrays()
        if len(X) > 0:
            # Adjust for maximization
            y_fit = y if self.config.maximize else -y
            self.surrogate.fit(X, y_fit)

        # Get best value so far
        best_value = self.history.get_best()[0]
        if best_value is None:
            best_value = -np.inf if self.config.maximize else np.inf

        # Generate candidates for acquisition optimization
        candidates = self._generate_candidates(n_candidates=max(1000, n_suggestions * 100))

        # Evaluate acquisition function
        X_cand = np.array([self.space.to_vector(c) for c in candidates])
        pred = self.surrogate.predict(X_cand)
        acq_values = self.acquisition(
            X_cand,
            pred.mean,
            pred.std,
            best_value,
        )

        # Select top candidates
        top_indices = np.argsort(acq_values)[::-1][:n_suggestions]
        suggestions = [candidates[i] for i in top_indices]

        return suggestions

    def _sample_random_point(self) -> dict[str, Any]:
        """Sample a random point from the parameter space."""
        point = {}
        for spec in self.space.parameters:
            point[spec.name] = spec.sample()
        return point

    def _generate_candidates(self, n_candidates: int) -> list[dict[str, Any]]:
        """Generate candidate points for acquisition optimization.

        Uses a combination of random sampling and local search around best.
        """
        candidates = []

        # Random sampling
        n_random = n_candidates // 2
        for _ in range(n_random):
            candidates.append(self._sample_random_point())

        # Local sampling around best point
        best_value, best_params = self.history.get_best()
        if best_params is not None:
            n_local = n_candidates - n_random
            for _ in range(n_local):
                # Perturb best point
                point = best_params.copy()
                for spec in self.space.parameters:
                    if spec.param_type == ParamType.CONTINUOUS:
                        low, high = spec.bounds
                        point[spec.name] = np.clip(
                            point[spec.name] + self._rng.normal(0, (high - low) * 0.1),
                            low, high
                        )
                    elif spec.param_type == ParamType.INTEGER:
                        low, high = spec.bounds
                        point[spec.name] = np.clip(
                            point[spec.name] + self._rng.randint(-3, 4),
                            int(low), int(high)
                        )
                    elif spec.param_type == ParamType.LOG_UNIFORM:
                        low, high = spec.bounds
                        log_val = np.log10(point[spec.name])
                        log_val = np.clip(
                            log_val + self._rng.normal(0, (high - low) * 0.1),
                            low, high
                        )
                        point[spec.name] = 10 ** log_val
                    # Categorical: keep as is or randomly change
                    elif spec.param_type == ParamType.CATEGORICAL:
                        if self._rng.random() < 0.1:
                            point[spec.name] = self._rng.choice(spec.bounds)

                candidates.append(point)

        return candidates

    def evaluate(self, parameters: dict[str, Any]) -> float:
        """Evaluate the objective function at given parameters.

        Args:
            parameters: Parameter dictionary to evaluate.

        Returns:
            Objective value.
        """
        if self._objective_func is None:
            raise RuntimeError("No objective function set. Call optimize() or set objective_func.")

        return self._objective_func(parameters)

    def step(self) -> tuple[dict[str, Any], float, float | None]:
        """Perform one optimization step: suggest, evaluate, update.

        Returns:
            Tuple of (parameters, objective_value, ei_value).
        """
        # Suggest next point
        suggestions = self.suggest(n_suggestions=1)
        if not suggestions:
            raise RuntimeError("No suggestions generated")

        params = suggestions[0]

        # Evaluate objective
        value = self.evaluate(params)

        # Compute EI for convergence monitoring
        ei_value = None
        if len(self.history) > 0:
            X, y, _ = self.history.get_arrays()
            if len(X) > 0:
                y_fit = y if self.config.maximize else -y
                self.surrogate.fit(X, y_fit)

                best_value = self.history.get_best()[0]
                if best_value is not None:
                    X_new = np.array([self.space.to_vector(params)])
                    pred = self.surrogate.predict(X_new)
                    ei_result = self.acquisition.evaluate(
                        X_new, pred.mean, pred.std, best_value
                    )
                    ei_value = float(ei_result.values[0])

        # Add to history
        self.history.add(
            parameters=params,
            objective_value=value if self.config.maximize else -value,
            metadata={"ei": ei_value, "optimizer_id": self._optimizer_id},
        )

        return params, value, ei_value

    def optimize(
        self,
        objective_func: Callable[[dict[str, Any]], float],
        n_iterations: int | None = None,
        callback: Callable[[dict[str, Any], float, ConvergenceState], None] | None = None,
    ) -> OptimizationResult:
        """Run Bayesian optimization.

        Args:
            objective_func: Function to optimize. Takes parameter dict, returns float.
            n_iterations: Maximum iterations (overrides convergence monitor if set).
            callback: Optional callback called after each iteration
                with (parameters, value, convergence_state).

        Returns:
            OptimizationResult with best parameters and full history.
        """
        self._objective_func = objective_func
        self._started_at = datetime.now(UTC).isoformat()
        start_time = time.time()

        # Override max iterations if specified
        if n_iterations is not None:
            # Find and update MaxIterationsCriterion
            for criterion in self.convergence.criteria:
                if isinstance(criterion, MaxIterationsCriterion):
                    criterion.max_iterations = n_iterations
                    break

        # Initial random evaluations if history is empty
        if len(self.history) < self.config.n_initial_points:
            n_initial = self.config.n_initial_points - len(self.history)
            for _ in range(n_initial):
                params = self._sample_random_point()
                value = self.evaluate(params)
                self.history.add(
                    parameters=params,
                    objective_value=value if self.config.maximize else -value,
                    metadata={"source": "initial_random", "optimizer_id": self._optimizer_id},
                )

        # Main optimization loop
        while not self.convergence.is_converged():
            params, value, ei_value = self.step()

            # Update convergence
            conv_state = self.convergence.step(
                current_value=value if self.config.maximize else -value,
                ei_value=ei_value,
            )

            # Callback
            if callback is not None:
                callback(params, value, conv_state)

            if conv_state.converged:
                break

        # Finalize
        completed_at = datetime.now(UTC).isoformat()
        total_time = time.time() - start_time

        best_value, best_params = self.history.get_best()
        if best_params is None:
            best_params = {}
            best_value = -np.inf if self.config.maximize else np.inf

        # Persist history
        self.history.persist()

        result = OptimizationResult(
            best_parameters=best_params,
            best_value=best_value if self.config.maximize else -best_value,
            n_evaluations=len(self.history),
            history=self.history,
            convergence_state=conv_state,
            campaign_id=self.history.campaign_id,
            optimizer_id=self._optimizer_id,
            started_at=self._started_at,
            completed_at=completed_at,
            total_time_seconds=total_time,
        )

        return result

    def load_history(self, campaign_id: str) -> int:
        """Load history from a previous campaign.

        Args:
            campaign_id: Campaign ID to load history from.

        Returns:
            Number of steps loaded.
        """
        self.history = HistoryBuffer(
            campaign_id=campaign_id,
            knowledge_lake_path=self.knowledge_lake_path,
        )
        return self.history.load()

    def get_next_suggestion(self) -> dict[str, Any] | None:
        """Get the next suggested parameters without evaluating.

        Useful for human-in-the-loop workflows.

        Returns:
            Next suggested parameters or None if no history.
        """
        suggestions = self.suggest(n_suggestions=1)
        return suggestions[0] if suggestions else None


def create_bayesian_optimizer(
    parameter_space: ParameterSpace | None = None,
    campaign_id: str | None = None,
    knowledge_lake_path: str | Path | None = None,
    surrogate_model: str = "gp",
    acquisition_function: str = "ei",
    max_iterations: int = 100,
    n_initial_points: int = 5,
    random_state: int | None = None,
    **kwargs,
) -> BayesianOptimizer:
    """Factory function to create a BayesianOptimizer with common defaults.

    Args:
        parameter_space: ParameterSpace (uses default SQX space if None).
        campaign_id: Campaign identifier (auto-generated if None).
        knowledge_lake_path: Path to Knowledge Lake.
        surrogate_model: "gp" or "rf".
        acquisition_function: "ei", "ucb", "pi", "ts".
        max_iterations: Maximum optimization iterations.
        n_initial_points: Number of random initial points.
        random_state: Random seed.
        **kwargs: Additional config parameters.

    Returns:
        Configured BayesianOptimizer instance.
    """
    if parameter_space is None:
        parameter_space = create_default_sqx_space()

    if campaign_id is None:
        campaign_id = f"bayesopt_{uuid.uuid4().hex[:8]}"

    convergence_monitor = create_default_monitor(
        max_iterations=max_iterations,
    )

    config = BayesianOptimizerConfig(
        parameter_space=parameter_space,
        surrogate_model=surrogate_model,
        acquisition_function=acquisition_function,
        convergence_monitor=convergence_monitor,
        random_state=random_state,
        n_initial_points=n_initial_points,
        **kwargs,
    )

    return BayesianOptimizer(config, knowledge_lake_path, campaign_id=campaign_id)


# Re-export for convenience
__all__ = [
    "BayesianOptimizer",
    "BayesianOptimizerConfig",
    "OptimizationResult",
    "create_bayesian_optimizer",
    "ParameterSpace",
    "ParameterSpec",
    "ParamType",
    "HistoryBuffer",
    "OptimizationStep",
    "SurrogateModel",
    "GaussianProcessSurrogate",
    "RandomForestSurrogate",
    "SurrogatePrediction",
    "AcquisitionFunction",
    "ExpectedImprovement",
    "UpperConfidenceBound",
    "ProbabilityOfImprovement",
    "ThompsonSampling",
    "ConvergenceMonitor",
    "ConvergenceState",
    "ConvergenceReason",
    "create_default_monitor",
]