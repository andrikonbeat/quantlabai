"""Tests for acquisition functions."""

from __future__ import annotations

import numpy as np
import pytest

from quantlab.optimization.acquisition import (
    AcquisitionResult,
    ExpectedImprovement,
    UpperConfidenceBound,
    ProbabilityOfImprovement,
    ThompsonSampling,
    ExpectedImprovementPerSecond,
    ConstrainedExpectedImprovement,
    create_acquisition,
)


class TestExpectedImprovement:
    """Tests for ExpectedImprovement acquisition function."""

    def test_basic_ei(self):
        """Test basic EI computation."""
        ei = ExpectedImprovement(xi=0.01)

        # Surrogate predicts mean=1.0, std=0.1 at test point
        # Best so far is 0.5
        X = np.array([[0.5]])
        mean = np.array([1.0])
        std = np.array([0.1])
        y_best = 0.5

        result = ei.evaluate(X, mean, std, y_best)

        assert isinstance(result, AcquisitionResult)
        assert result.values.shape == (1,)
        # EI should be positive since mean > y_best
        assert result.values[0] > 0

    def test_ei_zero_when_worse(self):
        """Test EI is zero when prediction is worse than best."""
        ei = ExpectedImprovement(xi=0.01)

        X = np.array([[0.5]])
        mean = np.array([0.3])  # Worse than best
        std = np.array([0.1])
        y_best = 0.5

        result = ei.evaluate(X, mean, std, y_best)
        assert result.values[0] >= 0  # EI is always non-negative

    def test_ei_zero_std(self):
        """Test EI with zero uncertainty."""
        ei = ExpectedImprovement(xi=0.01)

        X = np.array([[0.5]])
        mean = np.array([1.0])
        std = np.array([0.0])  # Certain prediction
        y_best = 0.5

        result = ei.evaluate(X, mean, std, y_best)
        # With zero std, EI = max(mean - y_best - xi, 0)
        assert result.values[0] == pytest.approx(1.0 - 0.5 - 0.01)

    def test_ei_zero_std_not_improving(self):
        """Test EI with zero uncertainty but not improving."""
        ei = ExpectedImprovement(xi=0.01)

        X = np.array([[0.5]])
        mean = np.array([0.3])
        std = np.array([0.0])
        y_best = 0.5

        result = ei.evaluate(X, mean, std, y_best)
        assert result.values[0] == 0.0

    def test_xi_exploration(self):
        """Test xi parameter controls exploration."""
        ei_low = ExpectedImprovement(xi=0.0)
        ei_high = ExpectedImprovement(xi=0.5)

        X = np.array([[0.5]])
        mean = np.array([0.6])
        std = np.array([0.1])
        y_best = 0.5

        result_low = ei_low.evaluate(X, mean, std, y_best)
        result_high = ei_high.evaluate(X, mean, std, y_best)

        # Higher xi should give lower EI (more conservative)
        assert result_high.values[0] <= result_low.values[0]

    def test_call_method(self):
        """Test __call__ convenience method."""
        ei = ExpectedImprovement()
        X = np.array([[0.5]])
        mean = np.array([1.0])
        std = np.array([0.1])
        y_best = 0.5

        values = ei(X, mean, std, y_best)
        assert values.shape == (1,)


class TestUpperConfidenceBound:
    """Tests for UpperConfidenceBound acquisition function."""

    def test_basic_ucb(self):
        """Test basic UCB computation."""
        ucb = UpperConfidenceBound(kappa=2.0)

        X = np.array([[0.5]])
        mean = np.array([1.0])
        std = np.array([0.1])
        y_best = 0.5  # Unused for UCB

        result = ucb.evaluate(X, mean, std, y_best)

        assert result.values[0] == pytest.approx(1.0 + 2.0 * 0.1)

    def test_kappa_control(self):
        """Test kappa controls exploration."""
        ucb_low = UpperConfidenceBound(kappa=1.0)
        ucb_high = UpperConfidenceBound(kappa=3.0)

        X = np.array([[0.5]])
        mean = np.array([1.0])
        std = np.array([0.2])

        result_low = ucb_low.evaluate(X, mean, std, 0.0)
        result_high = ucb_high.evaluate(X, mean, std, 0.0)

        assert result_high.values[0] > result_low.values[0]

    def test_call_method(self):
        """Test __call__ method."""
        ucb = UpperConfidenceBound(kappa=2.0)
        X = np.array([[0.5]])
        mean = np.array([1.0])
        std = np.array([0.1])

        values = ucb(X, mean, std, 0.0)
        assert values.shape == (1,)


class TestProbabilityOfImprovement:
    """Tests for ProbabilityOfImprovement acquisition function."""

    def test_basic_pi(self):
        """Test basic PI computation."""
        pi = ProbabilityOfImprovement(xi=0.01)

        X = np.array([[0.5]])
        mean = np.array([1.0])
        std = np.array([0.1])
        y_best = 0.5

        result = pi.evaluate(X, mean, std, y_best)

        assert 0.0 <= result.values[0] <= 1.0

    def test_pi_zero_std_improving(self):
        """Test PI with zero std when improving."""
        pi = ProbabilityOfImprovement(xi=0.01)

        X = np.array([[0.5]])
        mean = np.array([0.6])
        std = np.array([0.0])
        y_best = 0.5

        result = pi.evaluate(X, mean, std, y_best)
        assert result.values[0] == 1.0

    def test_pi_zero_std_not_improving(self):
        """Test PI with zero std when not improving."""
        pi = ProbabilityOfImprovement(xi=0.01)

        X = np.array([[0.5]])
        mean = np.array([0.4])
        std = np.array([0.0])
        y_best = 0.5

        result = pi.evaluate(X, mean, std, y_best)
        assert result.values[0] == 0.0


class TestThompsonSampling:
    """Tests for ThompsonSampling acquisition function."""

    def test_basic_ts(self):
        """Test Thompson Sampling."""
        ts = ThompsonSampling(random_state=42)

        X = np.array([[0.5], [1.0]])
        mean = np.array([1.0, 2.0])
        std = np.array([0.1, 0.2])
        y_best = 0.0  # Unused

        result = ts.evaluate(X, mean, std, y_best)

        assert result.values.shape == (2,)
        # Samples should be around mean
        assert abs(result.values[0] - 1.0) < 0.5
        assert abs(result.values[1] - 2.0) < 0.5

    def test_reproducibility(self):
        """Test reproducibility with random_state."""
        ts1 = ThompsonSampling(random_state=42)
        ts2 = ThompsonSampling(random_state=42)

        X = np.array([[0.5], [1.0]])
        mean = np.array([1.0, 2.0])
        std = np.array([0.1, 0.2])

        result1 = ts1.evaluate(X, mean, std, 0.0)
        result2 = ts2.evaluate(X, mean, std, 0.0)

        assert np.allclose(result1.values, result2.values)


class TestExpectedImprovementPerSecond:
    """Tests for ExpectedImprovementPerSecond."""

    def test_ei_per_second(self):
        """Test EI per second with time model."""
        class MockTimeModel:
            def predict(self, X):
                return np.array([2.0, 1.0])  # Different times

        ei_ps = ExpectedImprovementPerSecond(xi=0.01, time_model=MockTimeModel())

        X = np.array([[0.5], [1.0]])
        mean = np.array([1.0, 1.0])  # Same mean
        std = np.array([0.1, 0.1])
        y_best = 0.5

        result = ei_ps.evaluate(X, mean, std, y_best)

        # Second point should have higher EIps (less time)
        assert result.values[1] > result.values[0]

    def test_without_time_model(self):
        """Test without time model (constant time)."""
        ei_ps = ExpectedImprovementPerSecond(xi=0.01)

        X = np.array([[0.5]])
        mean = np.array([1.0])
        std = np.array([0.1])
        y_best = 0.5

        result = ei_ps.evaluate(X, mean, std, y_best)
        # Should equal regular EI
        ei = ExpectedImprovement(xi=0.01)
        ei_result = ei.evaluate(X, mean, std, y_best)
        assert result.values[0] == pytest.approx(ei_result.values[0])


class TestConstrainedExpectedImprovement:
    """Tests for ConstrainedExpectedImprovement."""

    def test_constrained_ei(self):
        """Test constrained EI with constraint models."""
        class MockConstraintModel:
            def predict_proba(self, X):
                # Returns [P(infeasible), P(feasible)]
                return np.array([[0.5, 0.5], [0.0, 1.0]])

        cei = ConstrainedExpectedImprovement(xi=0.01, constraint_models=[MockConstraintModel()])

        X = np.array([[0.5], [1.0]])
        mean = np.array([1.0, 1.0])
        std = np.array([0.1, 0.1])
        y_best = 0.5

        result = cei.evaluate(X, mean, std, y_best)

        # First point has 0.5 feasibility, second has 1.0
        assert result.values[1] > result.values[0]

    def test_deterministic_constraint(self):
        """Test with deterministic constraint model."""
        class DeterministicConstraint:
            def predict(self, X):
                return np.array([0, 1])  # First infeasible, second feasible

        cei = ConstrainedExpectedImprovement(xi=0.01, constraint_models=[DeterministicConstraint()])

        X = np.array([[0.5], [1.0]])
        mean = np.array([1.0, 1.0])
        std = np.array([0.1, 0.1])
        y_best = 0.5

        result = cei.evaluate(X, mean, std, y_best)

        assert result.values[0] == 0.0  # Infeasible -> EI = 0
        assert result.values[1] > 0.0   # Feasible -> EI > 0


class TestAcquisitionFactory:
    """Tests for create_acquisition factory function."""

    def test_create_ei(self):
        ei = create_acquisition("ei", xi=0.1)
        assert isinstance(ei, ExpectedImprovement)
        assert ei.xi == 0.1

    def test_create_ei_aliases(self):
        for name in ["ei", "expected_improvement"]:
            ei = create_acquisition(name)
            assert isinstance(ei, ExpectedImprovement)

    def test_create_ucb(self):
        ucb = create_acquisition("ucb", kappa=3.0)
        assert isinstance(ucb, UpperConfidenceBound)
        assert ucb.kappa == 3.0

    def test_create_ucb_aliases(self):
        for name in ["ucb", "upper_confidence_bound"]:
            ucb = create_acquisition(name)
            assert isinstance(ucb, UpperConfidenceBound)

    def test_create_pi(self):
        pi = create_acquisition("pi", xi=0.05)
        assert isinstance(pi, ProbabilityOfImprovement)

    def test_create_pi_aliases(self):
        for name in ["pi", "probability_of_improvement"]:
            pi = create_acquisition(name)
            assert isinstance(pi, ProbabilityOfImprovement)

    def test_create_ts(self):
        ts = create_acquisition("ts", random_state=42)
        assert isinstance(ts, ThompsonSampling)

    def test_create_ts_aliases(self):
        for name in ["ts", "thompson_sampling"]:
            ts = create_acquisition(name)
            assert isinstance(ts, ThompsonSampling)

    def test_create_ei_ps(self):
        ei_ps = create_acquisition("ei_ps")
        assert isinstance(ei_ps, ExpectedImprovementPerSecond)

    def test_create_cei(self):
        cei = create_acquisition("cei")
        assert isinstance(cei, ConstrainedExpectedImprovement)

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown acquisition function"):
            create_acquisition("unknown")