"""Acquisition functions for Bayesian Optimization.

Implements Expected Improvement (EI), Upper Confidence Bound (UCB),
and Probability of Improvement (PI) for guiding the search.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.stats import norm


@dataclass
class AcquisitionResult:
    """Result of acquisition function evaluation.

    Attributes:
        values: Acquisition function values at each point.
        gradients: Gradients (if available) of shape (n_points, n_features).
    """

    values: np.ndarray
    gradients: np.ndarray | None = None


class AcquisitionFunction(ABC):
    """Abstract base class for acquisition functions."""

    @abstractmethod
    def evaluate(
        self,
        X: np.ndarray,
        surrogate_mean: np.ndarray,
        surrogate_std: np.ndarray,
        y_best: float,
    ) -> AcquisitionResult:
        """Evaluate acquisition function at candidate points.

        Args:
            X: Candidate points of shape (n_points, n_features).
            surrogate_mean: Surrogate mean predictions at X.
            surrogate_std: Surrogate std predictions at X.
            y_best: Best observed value so far (for improvement-based methods).

        Returns:
            AcquisitionResult with values and optional gradients.
        """
        pass

    def __call__(
        self,
        X: np.ndarray,
        surrogate_mean: np.ndarray,
        surrogate_std: np.ndarray,
        y_best: float,
    ) -> np.ndarray:
        """Convenience call returning just values."""
        return self.evaluate(X, surrogate_mean, surrogate_std, y_best).values


class ExpectedImprovement(AcquisitionFunction):
    """Expected Improvement (EI) acquisition function.

    EI(x) = E[max(f(x) - f(x_best), 0)]
          = (μ(x) - f(x_best)) * Φ(Z) + σ(x) * φ(Z)
    where Z = (μ(x) - f(x_best)) / σ(x)
    """

    def __init__(self, xi: float = 0.01) -> None:
        """Initialize EI.

        Args:
            xi: Exploration-exploitation trade-off parameter.
                Higher xi encourages more exploration.
        """
        self.xi = xi

    def evaluate(
        self,
        X: np.ndarray,
        surrogate_mean: np.ndarray,
        surrogate_std: np.ndarray,
        y_best: float,
    ) -> AcquisitionResult:
        """Compute Expected Improvement."""
        # Avoid division by zero
        std = np.maximum(surrogate_std, 1e-12)

        # Improvement over best
        imp = surrogate_mean - y_best - self.xi

        # Standardized improvement
        Z = imp / std

        # CDF and PDF of standard normal
        cdf = norm.cdf(Z)
        pdf = norm.pdf(Z)

        # Expected Improvement
        ei = imp * cdf + std * pdf

        # For points with zero uncertainty, EI = 0 if not improving
        ei[std == 0] = 0.0

        return AcquisitionResult(values=ei)


class UpperConfidenceBound(AcquisitionFunction):
    """Upper Confidence Bound (UCB) acquisition function.

    UCB(x) = μ(x) + kappa * σ(x)

    Balances exploitation (mean) and exploration (uncertainty).
    """

    def __init__(self, kappa: float = 2.576) -> None:
        """Initialize UCB.

        Args:
            kappa: Exploration parameter.
                kappa=1.96 -> 95% confidence bound
                kappa=2.576 -> 99% confidence bound
                kappa=3.0 -> ~99.7% confidence bound
        """
        self.kappa = kappa

    def evaluate(
        self,
        X: np.ndarray,
        surrogate_mean: np.ndarray,
        surrogate_std: np.ndarray,
        y_best: float,  # unused for UCB but kept for interface compatibility
    ) -> AcquisitionResult:
        """Compute Upper Confidence Bound."""
        ucb = surrogate_mean + self.kappa * surrogate_std
        return AcquisitionResult(values=ucb)


class ProbabilityOfImprovement(AcquisitionFunction):
    """Probability of Improvement (PI) acquisition function.

    PI(x) = P(f(x) > f(x_best) + xi)
          = Φ((μ(x) - f(x_best) - xi) / σ(x))
    """

    def __init__(self, xi: float = 0.01) -> None:
        """Initialize PI.

        Args:
            xi: Exploration parameter (minimum improvement threshold).
        """
        self.xi = xi

    def evaluate(
        self,
        X: np.ndarray,
        surrogate_mean: np.ndarray,
        surrogate_std: np.ndarray,
        y_best: float,
    ) -> AcquisitionResult:
        """Compute Probability of Improvement."""
        std = np.maximum(surrogate_std, 1e-12)

        Z = (surrogate_mean - y_best - self.xi) / std
        pi = norm.cdf(Z)

        # For zero uncertainty, PI = 1 if mean > best + xi else 0
        pi[std == 0] = (surrogate_mean[std == 0] > y_best + self.xi).astype(float)

        return AcquisitionResult(values=pi)


class ExpectedImprovementPerSecond(ExpectedImprovement):
    """Expected Improvement per Second (EIps).

    EIps(x) = EI(x) / time(x)

    Accounts for evaluation cost when optimization budget is time-based.
    """

    def __init__(self, xi: float = 0.01, time_model: Any = None) -> None:
        """Initialize EIps.

        Args:
            xi: Exploration parameter (inherited from EI).
            time_model: Optional model predicting evaluation time.
                If None, assumes constant time.
        """
        super().__init__(xi)
        self.time_model = time_model

    def evaluate(
        self,
        X: np.ndarray,
        surrogate_mean: np.ndarray,
        surrogate_std: np.ndarray,
        y_best: float,
    ) -> AcquisitionResult:
        """Compute EI per second."""
        ei_result = super().evaluate(X, surrogate_mean, surrogate_std, y_best)
        ei = ei_result.values

        if self.time_model is not None:
            times = self.time_model.predict(X)
            times = np.maximum(times, 1e-6)
        else:
            times = np.ones_like(ei)

        ei_per_sec = ei / times
        return AcquisitionResult(values=ei_per_sec)


class ThompsonSampling(AcquisitionFunction):
    """Thompson Sampling acquisition function.

    Samples from the surrogate posterior and selects the point
    with the highest sampled value.
    """

    def __init__(self, random_state: int | None = None) -> None:
        """Initialize Thompson Sampling."""
        self.random_state = random_state
        self._rng = np.random.RandomState(random_state)

    def evaluate(
        self,
        X: np.ndarray,
        surrogate_mean: np.ndarray,
        surrogate_std: np.ndarray,
        y_best: float,  # unused but kept for interface
    ) -> AcquisitionResult:
        """Sample from posterior and return sampled values."""
        std = np.maximum(surrogate_std, 1e-12)
        # Sample from normal distribution
        samples = self._rng.normal(surrogate_mean, std)
        return AcquisitionResult(values=samples)


class ConstrainedExpectedImprovement(ExpectedImprovement):
    """Expected Improvement with feasibility constraints.

    EI_c(x) = EI(x) * P(feasible | x)

    Multiplies EI by probability of satisfying constraints.
    """

    def __init__(
        self,
        xi: float = 0.01,
        constraint_models: list[Any] | None = None,
    ) -> None:
        """Initialize constrained EI.

        Args:
            xi: Exploration parameter.
            constraint_models: List of probabilistic constraint models
                that implement predict_proba(X) -> P(feasible).
        """
        super().__init__(xi)
        self.constraint_models = constraint_models or []

    def evaluate(
        self,
        X: np.ndarray,
        surrogate_mean: np.ndarray,
        surrogate_std: np.ndarray,
        y_best: float,
    ) -> AcquisitionResult:
        """Compute constrained EI."""
        ei_result = super().evaluate(X, surrogate_mean, surrogate_std, y_best)
        ei = ei_result.values

        # Multiply by probability of feasibility
        p_feasible = np.ones_like(ei)
        for model in self.constraint_models:
            if hasattr(model, "predict_proba"):
                p_feasible *= model.predict_proba(X)[:, 1]  # Positive class prob
            elif hasattr(model, "predict"):
                # Deterministic constraint: 1 if feasible, 0 otherwise
                p_feasible *= model.predict(X)

        constrained_ei = ei * p_feasible
        return AcquisitionResult(values=constrained_ei)


def create_acquisition(
    name: str = "ei",
    **kwargs,
) -> AcquisitionFunction:
    """Factory function to create acquisition functions.

    Args:
        name: Acquisition function name ("ei", "ucb", "pi", "ts", "ei_ps", "cei").
        **kwargs: Additional arguments passed to the constructor.

    Returns:
        Configured AcquisitionFunction instance.
    """
    name = name.lower()
    if name in ("ei", "expected_improvement"):
        return ExpectedImprovement(**kwargs)
    elif name in ("ucb", "upper_confidence_bound"):
        return UpperConfidenceBound(**kwargs)
    elif name in ("pi", "probability_of_improvement"):
        return ProbabilityOfImprovement(**kwargs)
    elif name in ("ts", "thompson_sampling"):
        return ThompsonSampling(**kwargs)
    elif name in ("ei_ps", "expected_improvement_per_second"):
        return ExpectedImprovementPerSecond(**kwargs)
    elif name in ("cei", "constrained_expected_improvement"):
        return ConstrainedExpectedImprovement(**kwargs)
    else:
        raise ValueError(f"Unknown acquisition function: {name}")