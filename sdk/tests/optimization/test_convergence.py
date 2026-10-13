"""Tests for convergence monitoring."""

from __future__ import annotations

import numpy as np
import pytest

from quantlab.optimization.convergence import (
    ConvergenceMonitor,
    ConvergenceReason,
    ConvergenceState,
    MaxIterationsCriterion,
    EIThresholdCriterion,
    PatienceCriterion,
    TargetValueCriterion,
    DivergenceCriterion,
    CompositeConvergenceCriterion,
    create_default_monitor,
)


class TestConvergenceState:
    """Tests for ConvergenceState."""

    def test_default_state(self):
        state = ConvergenceState()
        assert state.converged is False
        assert state.reason is None
        assert state.iteration == 0
        assert state.best_value == -np.inf
        assert state.best_iteration == -1
        assert state.patience_counter == 0
        assert state.ei_values == []

    def test_to_dict(self):
        state = ConvergenceState(
            converged=True,
            reason=ConvergenceReason.MAX_ITERATIONS,
            iteration=100,
            best_value=1.5,
            best_iteration=50,
            patience_counter=10,
            ei_values=[1e-5, 1e-6],
            message="Done",
        )
        d = state.to_dict()
        assert d["converged"] is True
        assert d["reason"] == "max_iterations"
        assert d["iteration"] == 100
        assert d["best_value"] == 1.5
        assert d["recent_ei_mean"] == pytest.approx(5.5e-6)


class TestMaxIterationsCriterion:
    """Tests for MaxIterationsCriterion."""

    def test_max_iterations(self):
        criterion = MaxIterationsCriterion(max_iterations=10)
        state = ConvergenceState()

        # First 9 calls should not converge (iteration 1-9)
        for i in range(9):
            state = criterion.check(state, 1.0)
            assert state.converged is False
            assert state.iteration == i + 1

        # 10th call should converge (iteration 10)
        state = criterion.check(state, 1.0)
        assert state.converged is True
        assert state.reason == ConvergenceReason.MAX_ITERATIONS
        assert state.iteration == 10
        assert "10" in state.message

    def test_describe(self):
        criterion = MaxIterationsCriterion(max_iterations=50)
        assert "50" in criterion.describe()


class TestEIThresholdCriterion:
    """Tests for EIThresholdCriterion."""

    def test_ei_threshold(self):
        criterion = EIThresholdCriterion(threshold=1e-4, window=3, min_iterations=6)
        state = ConvergenceState()

        # Before min_iterations, should not converge even with low EI
        for i in range(5):
            state.iteration = i + 1
            state = criterion.check(state, 1.0, ei_value=1e-6)
        assert state.converged is False

        # After min_iterations, low EI should trigger convergence
        for i in range(3):
            state.iteration = 6 + i + 1
            state = criterion.check(state, 1.0, ei_value=1e-6)

        assert state.converged is True
        assert state.reason == ConvergenceReason.EI_THRESHOLD

    def test_high_ei_no_convergence(self):
        criterion = EIThresholdCriterion(threshold=1e-4, window=3, min_iterations=5)
        state = ConvergenceState()

        for i in range(10):
            state = criterion.check(state, 1.0, ei_value=1.0)  # High EI

        assert state.converged is False

    def test_describe(self):
        criterion = EIThresholdCriterion(threshold=1e-3, window=5, min_iterations=10)
        desc = criterion.describe()
        assert "1e-03" in desc or "0.001" in desc
        assert "5" in desc
        assert "10" in desc


class TestPatienceCriterion:
    """Tests for PatienceCriterion."""

    def test_patience_exhausted(self):
        criterion = PatienceCriterion(patience=3, min_improvement=0.01)
        state = ConvergenceState()

        # First improvement
        state = criterion.check(state, 1.0)
        assert state.best_value == 1.0
        assert state.patience_counter == 0

        # Second improvement
        state = criterion.check(state, 1.5)
        assert state.best_value == 1.5
        assert state.patience_counter == 0

        # No improvement
        state = criterion.check(state, 1.4)
        assert state.patience_counter == 1

        state = criterion.check(state, 1.3)
        assert state.patience_counter == 2

        state = criterion.check(state, 1.2)
        assert state.patience_counter == 3
        assert state.converged is True
        assert state.reason == ConvergenceReason.PATIENCE_EXHAUSTED

    def test_min_improvement(self):
        criterion = PatienceCriterion(patience=2, min_improvement=0.1)
        state = ConvergenceState()

        state = criterion.check(state, 1.0)  # best = 1.0
        state = criterion.check(state, 1.05)  # improvement < 0.1
        assert state.patience_counter == 1

        state = criterion.check(state, 1.08)  # improvement < 0.1
        assert state.patience_counter == 2
        assert state.converged is True

    def test_describe(self):
        criterion = PatienceCriterion(patience=20, min_improvement=1e-6)
        desc = criterion.describe()
        assert "20" in desc
        assert "1e-06" in desc or "0.000001" in desc


class TestTargetValueCriterion:
    """Tests for TargetValueCriterion."""

    def test_target_reached(self):
        criterion = TargetValueCriterion(target_value=2.0)
        state = ConvergenceState()

        state = criterion.check(state, 1.0)
        assert state.converged is False

        state = criterion.check(state, 2.0)
        assert state.converged is True
        assert state.reason == ConvergenceReason.TARGET_REACHED
        assert "2.0" in state.message

    def test_target_exceeded(self):
        criterion = TargetValueCriterion(target_value=2.0)
        state = ConvergenceState()

        state = criterion.check(state, 2.5)
        assert state.converged is True


class TestDivergenceCriterion:
    """Tests for DivergenceCriterion."""

    def test_divergence_detected(self):
        criterion = DivergenceCriterion(divergence_threshold=10.0, window=3)
        state = ConvergenceState()

        # First few values establish best
        state.best_value = 100.0
        state = criterion.check(state, 100.0)
        state = criterion.check(state, 90.0)
        state = criterion.check(state, 80.0)

        # Now values are much worse
        state = criterion.check(state, 5.0)  # 20x worse
        state = criterion.check(state, 4.0)
        state = criterion.check(state, 3.0)

        assert state.converged is True
        assert state.reason == ConvergenceReason.DIVERGED

    def test_no_divergence(self):
        criterion = DivergenceCriterion(divergence_threshold=10.0, window=3)
        state = ConvergenceState()

        for val in [1.0, 1.1, 1.2, 1.1, 1.3]:
            state = criterion.check(state, val)

        assert state.converged is False


class TestCompositeConvergenceCriterion:
    """Tests for CompositeConvergenceCriterion."""

    def test_or_logic(self):
        c1 = MaxIterationsCriterion(max_iterations=5)
        c2 = TargetValueCriterion(target_value=10.0)
        composite = CompositeConvergenceCriterion([c1, c2])
        state = ConvergenceState()

        # Neither triggers yet
        state = composite.check(state, 1.0)
        assert state.converged is False
        assert state.iteration == 1

        # Target reached triggers first
        state = composite.check(state, 10.0)
        assert state.converged is True
        assert state.reason == ConvergenceReason.TARGET_REACHED


class TestConvergenceMonitor:
    """Tests for ConvergenceMonitor."""

    def test_default_monitor(self):
        monitor = create_default_monitor(
            max_iterations=10,
            ei_threshold=1e-4,
            patience=5,
        )

        # Run a few iterations
        for i in range(3):
            state = monitor.step(current_value=1.0 + i * 0.1, ei_value=0.1)
            assert state.converged is False

        # Check history
        assert len(monitor.history) == 3

    def test_max_iterations_convergence(self):
        monitor = create_default_monitor(max_iterations=3, patience=100)
        state = None

        for i in range(4):
            state = monitor.step(current_value=1.0, ei_value=1.0)

        assert state.converged is True
        assert state.reason == ConvergenceReason.MAX_ITERATIONS

    def test_patience_convergence(self):
        monitor = create_default_monitor(max_iterations=100, patience=3, ei_threshold=1e-10)
        state = None

        state = monitor.step(current_value=1.0, ei_value=0.1)
        state = monitor.step(current_value=1.5, ei_value=0.1)  # improvement
        state = monitor.step(current_value=1.4, ei_value=0.1)  # no improvement
        state = monitor.step(current_value=1.3, ei_value=0.1)  # no improvement
        state = monitor.step(current_value=1.2, ei_value=0.1)  # no improvement -> patience exhausted

        assert state.converged is True
        assert state.reason == ConvergenceReason.PATIENCE_EXHAUSTED

    def test_is_converged(self):
        monitor = create_default_monitor(max_iterations=2)
        assert monitor.is_converged() is False

        monitor.step(1.0, 1.0)
        assert monitor.is_converged() is False

        monitor.step(1.0, 1.0)
        assert monitor.is_converged() is True

    def test_get_reason(self):
        monitor = create_default_monitor(max_iterations=2)
        monitor.step(1.0, 1.0)
        monitor.step(1.0, 1.0)
        assert monitor.get_reason() == ConvergenceReason.MAX_ITERATIONS

    def test_describe(self):
        monitor = create_default_monitor(max_iterations=10, patience=5)
        desc = monitor.describe()
        assert "Max iterations" in desc
        assert "EI threshold" in desc
        assert "Patience" in desc


class TestConvergenceReason:
    """Tests for ConvergenceReason enum."""

    def test_all_reasons(self):
        reasons = [
            ConvergenceReason.MAX_ITERATIONS,
            ConvergenceReason.EI_THRESHOLD,
            ConvergenceReason.PATIENCE_EXHAUSTED,
            ConvergenceReason.TARGET_REACHED,
            ConvergenceReason.TIME_BUDGET,
            ConvergenceReason.MANUAL_STOP,
            ConvergenceReason.DIVERGED,
            ConvergenceReason.NO_IMPROVEMENT,
        ]
        for r in reasons:
            assert isinstance(r.value, str)