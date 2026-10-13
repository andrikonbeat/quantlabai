"""Surrogate models for Bayesian Optimization.

Provides Gaussian Process and Random Forest surrogate models
for modeling the objective function.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class SurrogatePrediction:
    """Prediction from a surrogate model.

    Attributes:
        mean: Predicted mean values.
        std: Predicted standard deviations (uncertainty).
    """

    mean: np.ndarray
    std: np.ndarray


class SurrogateModel(ABC):
    """Abstract base class for surrogate models."""

    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """Fit the surrogate model to observed data.

        Args:
            X: Input features of shape (n_samples, n_features).
            y: Target values of shape (n_samples,).
        """
        pass

    @abstractmethod
    def predict(self, X: np.ndarray, return_std: bool = True) -> SurrogatePrediction:
        """Predict at new points.

        Args:
            X: Input features of shape (n_samples, n_features).
            return_std: Whether to return uncertainty estimates.

        Returns:
            SurrogatePrediction with mean and std.
        """
        pass

    @abstractmethod
    def sample_functions(self, X: np.ndarray, n_samples: int) -> np.ndarray:
        """Sample functions from the posterior.

        Used for Thompson sampling or uncertainty visualization.

        Args:
            X: Input features of shape (n_samples, n_features).
            n_samples: Number of function samples to draw.

        Returns:
            Array of shape (n_samples, n_points).
        """
        pass


class GaussianProcessSurrogate(SurrogateModel):
    """Gaussian Process surrogate model using scikit-learn.

    Uses a Matern kernel with Automatic Relevance Determination (ARD)
    for automatic length-scale learning per dimension.
    """

    def __init__(
        self,
        kernel: Any = None,
        alpha: float = 1e-6,
        normalize_y: bool = True,
        n_restarts_optimizer: int = 5,
        random_state: int | None = None,
    ) -> None:
        """Initialize GP surrogate.

        Args:
            kernel: GP kernel (uses Matern + WhiteKernel if None).
            alpha: Noise level (nugget) for numerical stability.
            normalize_y: Whether to normalize target values.
            n_restarts_optimizer: Number of kernel hyperparameter optimization restarts.
            random_state: Random seed for reproducibility.
        """
        self._kernel = kernel
        self._alpha = alpha
        self._normalize_y = normalize_y
        self._n_restarts = n_restarts_optimizer
        self._random_state = random_state
        self._gp = None
        self._fitted = False
        self._y_mean = 0.0
        self._y_std = 1.0

    def _build_kernel(self, n_features: int) -> Any:
        """Build default kernel if not provided."""
        try:
            from sklearn.gaussian_process.kernels import (
                Matern,
                WhiteKernel,
                ConstantKernel,
                RBF,
            )
        except ImportError as e:
            raise ImportError(
                "scikit-learn is required for GaussianProcessSurrogate. "
                "Install with: pip install scikit-learn"
            ) from e

        if self._kernel is not None:
            return self._kernel

        # Matern kernel with ARD (per-dimension length scales)
        # nu=2.5 gives twice differentiable functions
        matern = Matern(
            length_scale=[1.0] * n_features,
            length_scale_bounds=(1e-3, 1e3),
            nu=2.5,
        )

        # Constant kernel for amplitude
        const = ConstantKernel(
            constant_value=1.0,
            constant_value_bounds=(1e-3, 1e3),
        )

        # White kernel for noise
        white = WhiteKernel(
            noise_level=self._alpha,
            noise_level_bounds=(1e-10, 1e-1),
        )

        return const * matern + white

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """Fit the Gaussian Process to data."""
        try:
            from sklearn.gaussian_process import GaussianProcessRegressor
        except ImportError as e:
            raise ImportError(
                "scikit-learn is required for GaussianProcessSurrogate. "
                "Install with: pip install scikit-learn"
            ) from e

        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float).ravel()

        if X.ndim == 1:
            X = X.reshape(-1, 1)

        if self._normalize_y:
            self._y_mean = float(np.mean(y))
            self._y_std = float(np.std(y))
            if self._y_std < 1e-12:
                self._y_std = 1.0
            y_norm = (y - self._y_mean) / self._y_std
        else:
            self._y_mean = 0.0
            self._y_std = 1.0
            y_norm = y

        kernel = self._build_kernel(X.shape[1])

        self._gp = GaussianProcessRegressor(
            kernel=kernel,
            alpha=self._alpha,
            normalize_y=False,  # We handle normalization manually
            n_restarts_optimizer=self._n_restarts,
            random_state=self._random_state,
        )

        self._gp.fit(X, y_norm)
        self._fitted = True

    def predict(self, X: np.ndarray, return_std: bool = True) -> SurrogatePrediction:
        """Predict using the fitted GP."""
        if not self._fitted:
            raise RuntimeError("GaussianProcessSurrogate must be fitted before predict()")

        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X.reshape(-1, 1)

        if return_std:
            y_mean, y_std = self._gp.predict(X, return_std=True)
        else:
            y_mean = self._gp.predict(X, return_std=False)
            y_std = np.zeros_like(y_mean)

        # Denormalize
        y_mean = y_mean * self._y_std + self._y_mean
        y_std = y_std * self._y_std

        # Ensure non-negative std
        y_std = np.maximum(y_std, 1e-12)

        return SurrogatePrediction(mean=y_mean, std=y_std)

    def sample_functions(self, X: np.ndarray, n_samples: int) -> np.ndarray:
        """Sample from the GP posterior."""
        if not self._fitted:
            raise RuntimeError("GaussianProcessSurrogate must be fitted before sample_functions()")

        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X.reshape(1, -1)

        # Sample from GP posterior
        y_samples = self._gp.sample_y(X, n_samples=n_samples, random_state=self._random_state)
        # sample_y returns (n_points, n_samples), transpose to (n_samples, n_points)
        y_samples = y_samples.T * self._y_std + self._y_mean

        return y_samples


class RandomForestSurrogate(SurrogateModel):
    """Random Forest surrogate model.

    Uses an ensemble of decision trees with jackknife-after-bootstrap
    for uncertainty estimation. Good for mixed continuous/categorical spaces.
    """

    def __init__(
        self,
        n_estimators: int = 100,
        max_depth: int | None = None,
        min_samples_split: int = 2,
        min_samples_leaf: int = 1,
        random_state: int | None = None,
    ) -> None:
        """Initialize Random Forest surrogate.

        Args:
            n_estimators: Number of trees in the forest.
            max_depth: Maximum depth of trees.
            min_samples_split: Minimum samples to split a node.
            min_samples_leaf: Minimum samples in a leaf.
            random_state: Random seed.
        """
        self._n_estimators = n_estimators
        self._max_depth = max_depth
        self._min_samples_split = min_samples_split
        self._min_samples_leaf = min_samples_leaf
        self._random_state = random_state
        self._rf = None
        self._fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """Fit the Random Forest to data."""
        try:
            from sklearn.ensemble import RandomForestRegressor
        except ImportError as e:
            raise ImportError(
                "scikit-learn is required for RandomForestSurrogate. "
                "Install with: pip install scikit-learn"
            ) from e

        X = np.asarray(X, dtype=float)
        y = np.asarray(y, dtype=float).ravel()

        if X.ndim == 1:
            X = X.reshape(-1, 1)

        self._rf = RandomForestRegressor(
            n_estimators=self._n_estimators,
            max_depth=self._max_depth,
            min_samples_split=self._min_samples_split,
            min_samples_leaf=self._min_samples_leaf,
            random_state=self._random_state,
            n_jobs=-1,
        )

        self._rf.fit(X, y)
        self._fitted = True

    def predict(self, X: np.ndarray, return_std: bool = True) -> SurrogatePrediction:
        """Predict using the fitted Random Forest.

        Uses jackknife-after-bootstrap for uncertainty estimation.
        """
        if not self._fitted:
            raise RuntimeError("RandomForestSurrogate must be fitted before predict()")

        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X.reshape(-1, 1)

        # Get predictions from all trees
        tree_preds = np.array([tree.predict(X) for tree in self._rf.estimators_])
        # tree_preds shape: (n_trees, n_points)

        y_mean = np.mean(tree_preds, axis=0)

        if return_std:
            # Jackknife-after-bootstrap variance estimate
            y_std = np.std(tree_preds, axis=0, ddof=1)
            # Ensure minimum uncertainty
            y_std = np.maximum(y_std, 1e-6)
        else:
            y_std = np.zeros_like(y_mean)

        return SurrogatePrediction(mean=y_mean, std=y_std)

    def sample_functions(self, X: np.ndarray, n_samples: int) -> np.ndarray:
        """Sample functions by randomly selecting trees."""
        if not self._fitted:
            raise RuntimeError("RandomForestSurrogate must be fitted before sample_functions()")

        X = np.asarray(X, dtype=float)
        if X.ndim == 1:
            X = X.reshape(-1, 1)

        n_trees = len(self._rf.estimators_)
        # Sample trees with replacement
        tree_indices = np.random.choice(n_trees, size=n_samples, replace=True)

        samples = np.array([
            self._rf.estimators_[idx].predict(X)
            for idx in tree_indices
        ])

        return samples


def create_surrogate(model_type: str = "gp", **kwargs) -> SurrogateModel:
    """Factory function to create surrogate models.

    Args:
        model_type: "gp" for GaussianProcess, "rf" for RandomForest.
        **kwargs: Additional arguments passed to the surrogate constructor.

    Returns:
        Configured SurrogateModel instance.
    """
    if model_type.lower() in ("gp", "gaussian_process", "gaussianprocess"):
        return GaussianProcessSurrogate(**kwargs)
    elif model_type.lower() in ("rf", "random_forest", "randomforest"):
        return RandomForestSurrogate(**kwargs)
    else:
        raise ValueError(f"Unknown surrogate model type: {model_type}")