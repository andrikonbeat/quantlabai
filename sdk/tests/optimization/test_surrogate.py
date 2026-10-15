"""Tests for surrogate models."""

from __future__ import annotations

import numpy as np
import pytest

from quantlab.optimization.surrogate import (
    GaussianProcessSurrogate,
    RandomForestSurrogate,
    SurrogatePrediction,
    create_surrogate,
)


class TestGaussianProcessSurrogate:
    """Tests for GaussianProcessSurrogate."""

    def test_fit_and_predict(self):
        """Test basic fit and predict."""
        X = np.array([[0.0], [0.5], [1.0], [1.5], [2.0]])
        y = np.array([0.0, 0.5, 1.0, 1.5, 2.0])  # Simple linear

        gp = GaussianProcessSurrogate(random_state=42)
        gp.fit(X, y)

        X_test = np.array([[0.25], [0.75], [1.25]])
        pred = gp.predict(X_test)

        assert isinstance(pred, SurrogatePrediction)
        assert pred.mean.shape == (3,)
        assert pred.std.shape == (3,)
        assert np.all(pred.std > 0)

        # Check predictions are reasonable
        assert np.allclose(pred.mean, [0.25, 0.75, 1.25], atol=0.3)

    def test_fit_1d_input(self):
        """Test fit with 1D input (gets reshaped)."""
        X = np.array([0.0, 0.5, 1.0, 1.5, 2.0])
        y = np.array([0.0, 0.5, 1.0, 1.5, 2.0])

        gp = GaussianProcessSurrogate(random_state=42)
        gp.fit(X, y)

        pred = gp.predict(np.array([0.25, 0.75]))
        assert pred.mean.shape == (2,)

    def test_normalize_y(self):
        """Test y normalization."""
        X = np.array([[0.0], [1.0]])
        y = np.array([100.0, 200.0])  # Large values

        gp = GaussianProcessSurrogate(normalize_y=True, random_state=42)
        gp.fit(X, y)

        assert gp._y_mean == 150.0
        assert gp._y_std == 50.0

        pred = gp.predict(np.array([[0.5]]))
        # Should be around 150
        assert 100 < pred.mean[0] < 200

    def test_sample_functions(self):
        """Test sampling from posterior."""
        X = np.array([[0.0], [0.5], [1.0]])
        y = np.array([0.0, 0.5, 1.0])

        gp = GaussianProcessSurrogate(random_state=42)
        gp.fit(X, y)

        X_test = np.array([[0.25], [0.75]])
        samples = gp.sample_functions(X_test, n_samples=5)

        assert samples.shape == (5, 2)

    def test_predict_before_fit_raises(self):
        """Test that predict before fit raises error."""
        gp = GaussianProcessSurrogate()
        with pytest.raises(RuntimeError, match="must be fitted"):
            gp.predict(np.array([[0.5]]))


class TestRandomForestSurrogate:
    """Tests for RandomForestSurrogate."""

    def test_fit_and_predict(self):
        """Test basic fit and predict."""
        X = np.array([[0.0], [0.5], [1.0], [1.5], [2.0]])
        y = np.array([0.0, 0.5, 1.0, 1.5, 2.0])

        rf = RandomForestSurrogate(n_estimators=10, random_state=42)
        rf.fit(X, y)

        X_test = np.array([[0.25], [0.75], [1.25]])
        pred = rf.predict(X_test)

        assert isinstance(pred, SurrogatePrediction)
        assert pred.mean.shape == (3,)
        assert pred.std.shape == (3,)
        assert np.all(pred.std >= 0)

    def test_fit_1d_input(self):
        """Test fit with 1D input."""
        X = np.array([0.0, 0.5, 1.0, 1.5, 2.0])
        y = np.array([0.0, 0.5, 1.0, 1.5, 2.0])

        rf = RandomForestSurrogate(n_estimators=10, random_state=42)
        rf.fit(X, y)

        pred = rf.predict(np.array([0.25, 0.75]))
        assert pred.mean.shape == (2,)

    def test_sample_functions(self):
        """Test sampling functions."""
        X = np.array([[0.0], [0.5], [1.0]])
        y = np.array([0.0, 0.5, 1.0])

        rf = RandomForestSurrogate(n_estimators=10, random_state=42)
        rf.fit(X, y)

        X_test = np.array([[0.25], [0.75]])
        samples = rf.sample_functions(X_test, n_samples=5)

        assert samples.shape == (5, 2)

    def test_predict_before_fit_raises(self):
        """Test that predict before fit raises error."""
        rf = RandomForestSurrogate()
        with pytest.raises(RuntimeError, match="must be fitted"):
            rf.predict(np.array([[0.5]]))


class TestSurrogateFactory:
    """Tests for create_surrogate factory function."""

    def test_create_gp(self):
        gp = create_surrogate("gp", random_state=42)
        assert isinstance(gp, GaussianProcessSurrogate)

    def test_create_gp_aliases(self):
        for name in ["gp", "gaussian_process", "gaussianprocess"]:
            gp = create_surrogate(name, random_state=42)
            assert isinstance(gp, GaussianProcessSurrogate)

    def test_create_rf(self):
        rf = create_surrogate("rf", random_state=42)
        assert isinstance(rf, RandomForestSurrogate)

    def test_create_rf_aliases(self):
        for name in ["rf", "random_forest", "randomforest"]:
            rf = create_surrogate(name, random_state=42)
            assert isinstance(rf, RandomForestSurrogate)

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown surrogate model type"):
            create_surrogate("unknown")


class TestSurrogatePrediction:
    """Tests for SurrogatePrediction dataclass."""

    def test_creation(self):
        mean = np.array([1.0, 2.0, 3.0])
        std = np.array([0.1, 0.2, 0.3])
        pred = SurrogatePrediction(mean=mean, std=std)
        assert np.array_equal(pred.mean, mean)
        assert np.array_equal(pred.std, std)