"""Tests for BayesianOptimizer core."""

from __future__ import annotations

import numpy as np
import pytest

from quantlab.optimization.bayesian_optimizer import (
    BayesianOptimizer,
    BayesianOptimizerConfig,
    OptimizationResult,
    create_bayesian_optimizer,
)
from quantlab.optimization.space import ParameterSpace, ParameterSpec, ParamType, create_default_sqx_space
from quantlab.optimization.convergence import (
    create_default_monitor,
    MaxIterationsCriterion,
)
from quantlab.optimization.surrogate import create_surrogate
from quantlab.optimization.acquisition import create_acquisition


class TestBayesianOptimizerConfig:
    """Tests for BayesianOptimizerConfig."""

    def test_config_creation(self):
        space = create_default_sqx_space()
        config = BayesianOptimizerConfig(
            parameter_space=space,
            surrogate_model="gp",
            acquisition_function="ei",
            random_state=42,
        )
        assert config.parameter_space is space
        assert config.surrogate_model == "gp"
        assert config.acquisition_function == "ei"
        assert config.random_state == 42


class TestBayesianOptimizer:
    """Tests for BayesianOptimizer."""

    def _create_optimizer(self):
        """Create a test optimizer with simple quadratic objective."""
        space = ParameterSpace([
            ParameterSpec("x", ParamType.CONTINUOUS, (-5.0, 5.0)),
            ParameterSpec("y", ParamType.CONTINUOUS, (-5.0, 5.0)),
        ])

        config = BayesianOptimizerConfig(
            parameter_space=space,
            surrogate_model="gp",
            acquisition_function="ei",
            random_state=42,
            n_initial_points=3,
        )

        optimizer = BayesianOptimizer(config)
        return optimizer

    def test_initialization(self):
        optimizer = self._create_optimizer()
        assert optimizer.config is not None
        assert optimizer.surrogate is not None
        assert optimizer.acquisition is not None
        assert optimizer.convergence is not None
        assert optimizer.history is not None

    def test_suggest_no_history(self):
        optimizer = self._create_optimizer()
        suggestions = optimizer.suggest(n_suggestions=2)
        assert len(suggestions) == 2
        for s in suggestions:
            assert "x" in s
            assert "y" in s
            assert -5.0 <= s["x"] <= 5.0
            assert -5.0 <= s["y"] <= 5.0

    def test_suggest_with_history(self):
        optimizer = self._create_optimizer()
        # Add some history
        optimizer.history.add({"x": 0.0, "y": 0.0}, 0.0)
        optimizer.history.add({"x": 1.0, "y": 1.0}, -2.0)  # Negative because we maximize -f
        optimizer.history.add({"x": -1.0, "y": -1.0}, -2.0)

        suggestions = optimizer.suggest(n_suggestions=1)
        assert len(suggestions) == 1
        assert "x" in suggestions[0]
        assert "y" in suggestions[0]

    def test_step(self):
        optimizer = self._create_optimizer()

        # Define simple quadratic objective: f(x,y) = -(x^2 + y^2)
        # Maximum at (0,0) with value 0
        def objective(params):
            return -(params["x"]**2 + params["y"]**2)

        optimizer._objective_func = objective
        params, value, ei = optimizer.step()
        assert "x" in params
        assert "y" in params
        assert isinstance(value, float)
        # ei can be None on first steps
        if ei is not None:
            assert isinstance(ei, float)

    def test_optimize_simple_quadratic(self):
        """Test optimization on simple quadratic function."""
        optimizer = self._create_optimizer()

        def objective(params):
            return -(params["x"]**2 + params["y"]**2)

        result = optimizer.optimize(objective, n_iterations=10)

        assert isinstance(result, OptimizationResult)
        assert result.n_evaluations >= 10  # At least n_iterations
        assert result.best_parameters is not None
        assert "x" in result.best_parameters
        assert "y" in result.best_parameters
        # Best should be near (0,0)
        assert abs(result.best_parameters["x"]) < 1.0
        assert abs(result.best_parameters["y"]) < 1.0
        # Best value should be near 0
        assert result.best_value > -2.0  # Should find reasonably good values

    def test_optimize_with_callback(self):
        optimizer = self._create_optimizer()
        callback_calls = []

        def objective(params):
            return -(params["x"]**2 + params["y"]**2)

        def callback(params, value, conv_state):
            callback_calls.append((params, value, conv_state))

        result = optimizer.optimize(objective, n_iterations=5, callback=callback)

        assert len(callback_calls) == 5
        for params, value, conv_state in callback_calls:
            assert "x" in params
            assert isinstance(value, float)
            assert hasattr(conv_state, "iteration")

    def test_load_history(self):
        with pytest.TempDir() as tmpdir:
            optimizer = self._create_optimizer()

            # Add some history and persist
            optimizer.history.add({"x": 0.0, "y": 0.0}, 0.0)
            optimizer.history.add({"x": 1.0, "y": 1.0}, -2.0)
            optimizer.history.persist()

            campaign_id = optimizer.history.campaign_id

            # Create new optimizer and load
            optimizer2 = self._create_optimizer()
            loaded = optimizer2.load_history(campaign_id)

            assert loaded == 2
            assert len(optimizer2.history) == 2

    def test_get_next_suggestion(self):
        optimizer = self._create_optimizer()

        # No history
        suggestion = optimizer.get_next_suggestion()
        assert suggestion is not None
        assert "x" in suggestion

        # With history
        optimizer.history.add({"x": 0.0, "y": 0.0}, 0.0)
        suggestion = optimizer.get_next_suggestion()
        assert suggestion is not None


class TestOptimizationResult:
    """Tests for OptimizationResult."""

    def test_to_dict(self):
        space = ParameterSpace([ParameterSpec("x", ParamType.CONTINUOUS, (0, 1))])
        config = BayesianOptimizerConfig(parameter_space=space)
        optimizer = BayesianOptimizer(config)
        optimizer.history.add({"x": 0.5}, 1.0)

        from quantlab.optimization.convergence import ConvergenceState, ConvergenceReason
        conv_state = ConvergenceState(
            converged=True,
            reason=ConvergenceReason.MAX_ITERATIONS,
            iteration=10,
            best_value=1.0,
            best_iteration=5,
        )

        result = OptimizationResult(
            best_parameters={"x": 0.5},
            best_value=1.0,
            n_evaluations=10,
            history=optimizer.history,
            convergence_state=conv_state,
            campaign_id="test_campaign",
            optimizer_id="opt_123",
            started_at="2024-01-01T00:00:00",
            completed_at="2024-01-01T00:01:00",
            total_time_seconds=60.0,
        )

        d = result.to_dict()
        assert d["best_parameters"] == {"x": 0.5}
        assert d["best_value"] == 1.0
        assert d["n_evaluations"] == 10
        assert d["convergence"]["reason"] == "max_iterations"
        assert d["campaign_id"] == "test_campaign"
        assert d["optimizer_id"] == "opt_123"
        assert d["total_time_seconds"] == 60.0


class TestCreateBayesianOptimizer:
    """Tests for create_bayesian_optimizer factory."""

    def test_create_with_defaults(self):
        optimizer = create_bayesian_optimizer(max_iterations=20)
        assert optimizer is not None
        # max_iterations is in convergence monitor
        for criterion in optimizer.convergence.criteria:
            if isinstance(criterion, MaxIterationsCriterion):
                assert criterion.max_iterations == 20
                break
        # Should have created a default space
        assert len(optimizer.space.parameters) > 0

    def test_create_with_custom_space(self):
        space = ParameterSpace([
            ParameterSpec("x", ParamType.CONTINUOUS, (0, 1)),
        ])
        optimizer = create_bayesian_optimizer(parameter_space=space, max_iterations=30)
        assert optimizer.space is space
        for criterion in optimizer.convergence.criteria:
            if isinstance(criterion, MaxIterationsCriterion):
                assert criterion.max_iterations == 30
                break

    def test_create_with_campaign_id(self):
        optimizer = create_bayesian_optimizer(campaign_id="my_campaign")
        assert optimizer.history.campaign_id == "my_campaign"


class TestBayesianOptimizerIntegration:
    """Integration tests for BayesianOptimizer with different configurations."""

    def test_rf_surrogate(self):
        space = ParameterSpace([ParameterSpec("x", ParamType.CONTINUOUS, (0, 1))])
        config = BayesianOptimizerConfig(
            parameter_space=space,
            surrogate_model="rf",
            acquisition_function="ei",
            random_state=42,
        )
        optimizer = BayesianOptimizer(config)

        def objective(params):
            return -(params["x"] - 0.5)**2  # Max at x=0.5

        result = optimizer.optimize(objective, n_iterations=5)
        assert result.best_parameters is not None
        assert 0 <= result.best_parameters["x"] <= 1

    def test_ucb_acquisition(self):
        space = ParameterSpace([ParameterSpec("x", ParamType.CONTINUOUS, (0, 1))])
        config = BayesianOptimizerConfig(
            parameter_space=space,
            surrogate_model="gp",
            acquisition_function="ucb",
            acquisition_params={"kappa": 2.0},
            random_state=42,
        )
        optimizer = BayesianOptimizer(config)

        def objective(params):
            return -(params["x"] - 0.5)**2

        result = optimizer.optimize(objective, n_iterations=5)
        assert result.best_parameters is not None

    def test_pi_acquisition(self):
        space = ParameterSpace([ParameterSpec("x", ParamType.CONTINUOUS, (0, 1))])
        config = BayesianOptimizerConfig(
            parameter_space=space,
            surrogate_model="gp",
            acquisition_function="pi",
            random_state=42,
        )
        optimizer = BayesianOptimizer(config)

        def objective(params):
            return -(params["x"] - 0.5)**2

        result = optimizer.optimize(objective, n_iterations=5)
        assert result.best_parameters is not None

    def test_ts_acquisition(self):
        space = ParameterSpace([ParameterSpec("x", ParamType.CONTINUOUS, (0, 1))])
        config = BayesianOptimizerConfig(
            parameter_space=space,
            surrogate_model="gp",
            acquisition_function="ts",
            random_state=42,
        )
        optimizer = BayesianOptimizer(config)

        def objective(params):
            return -(params["x"] - 0.5)**2

        result = optimizer.optimize(objective, n_iterations=5)
        assert result.best_parameters is not None


# Mock TempDir for test_load_history
class pytest:
    class TempDir:
        def __enter__(self):
            import tempfile
            self.tmpdir = tempfile.mkdtemp()
            return self.tmpdir

        def __exit__(self, *args):
            import shutil
            shutil.rmtree(self.tmpdir, ignore_errors=True)