"""Tests for optimization history buffer."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from quantlab.optimization.history import (
    HistoryBuffer,
    OptimizationStep,
    load_history,
)


class TestOptimizationStep:
    """Tests for OptimizationStep dataclass."""

    def test_creation(self):
        step = OptimizationStep(
            step_id="test_1",
            parameters={"x": 0.5, "y": 10},
            objective_value=1.23,
            metadata={"source": "test"},
        )
        assert step.step_id == "test_1"
        assert step.parameters == {"x": 0.5, "y": 10}
        assert step.objective_value == 1.23
        assert step.metadata == {"source": "test"}

    def test_to_dict(self):
        step = OptimizationStep(
            step_id="test_1",
            parameters={"x": 0.5},
            objective_value=1.23,
            metadata={"source": "test"},
        )
        d = step.to_dict()
        assert d["step_id"] == "test_1"
        assert d["parameters"] == {"x": 0.5}
        assert d["objective_value"] == 1.23
        assert d["metadata"] == {"source": "test"}
        assert "timestamp" in d

    def test_from_dict(self):
        data = {
            "step_id": "test_1",
            "parameters": {"x": 0.5},
            "objective_value": 1.23,
            "metadata": {"source": "test"},
            "timestamp": "2024-01-01T00:00:00+00:00",
        }
        step = OptimizationStep.from_dict(data)
        assert step.step_id == "test_1"
        assert step.parameters == {"x": 0.5}
        assert step.objective_value == 1.23


class TestHistoryBuffer:
    """Tests for HistoryBuffer."""

    def test_add_and_get_best(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            buffer = HistoryBuffer("test_campaign", knowledge_lake_path=tmpdir)

            buffer.add({"x": 0.5}, 1.0)
            buffer.add({"x": 0.6}, 1.5)
            buffer.add({"x": 0.4}, 0.8)

            best_value, best_params = buffer.get_best()
            assert best_value == 1.5
            assert best_params == {"x": 0.6}

    def test_get_arrays(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            buffer = HistoryBuffer("test_campaign", knowledge_lake_path=tmpdir)

            buffer.add({"x": 0.5, "y": 10}, 1.0)
            buffer.add({"x": 0.6, "y": 20}, 1.5)

            X, y, names = buffer.get_arrays()
            assert X.shape == (2, 2)
            assert y.shape == (2,)
            assert names == ["x", "y"]
            assert X[0, 0] == 0.5
            assert X[0, 1] == 10
            assert X[1, 0] == 0.6
            assert X[1, 1] == 20
            assert y[0] == 1.0
            assert y[1] == 1.5

    def test_persist_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            buffer = HistoryBuffer("test_campaign", knowledge_lake_path=tmpdir)

            buffer.add({"x": 0.5}, 1.0, metadata={"source": "test"})
            buffer.add({"x": 0.6}, 1.5)
            buffer.persist()

            # Create new buffer and load
            buffer2 = HistoryBuffer("test_campaign", knowledge_lake_path=tmpdir)
            count = buffer2.load()

            assert count == 2
            best_value, best_params = buffer2.get_best()
            assert best_value == 1.5
            assert best_params == {"x": 0.6}

    def test_max_size_eviction(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            buffer = HistoryBuffer("test_campaign", knowledge_lake_path=tmpdir, max_size=2)

            buffer.add({"x": 0.5}, 1.0)
            buffer.add({"x": 0.6}, 1.5)
            buffer.add({"x": 0.7}, 2.0)  # Should evict first

            assert len(buffer) == 2
            best_value, best_params = buffer.get_best()
            assert best_value == 2.0
            assert best_params == {"x": 0.7}

            # Check persisted file has evicted step
            history_file = Path(tmpdir) / "structured" / "test_campaign" / "optimization" / "history.jsonl"
            lines = history_file.read_text().strip().split("\n")
            assert len(lines) == 1  # Only evicted step persisted

    def test_get_recent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            buffer = HistoryBuffer("test_campaign", knowledge_lake_path=tmpdir)

            buffer.add({"x": 0.5}, 1.0)
            buffer.add({"x": 0.6}, 1.5)
            buffer.add({"x": 0.7}, 2.0)

            recent = buffer.get_recent(2)
            assert len(recent) == 2
            assert recent[0].parameters["x"] == 0.6
            assert recent[1].parameters["x"] == 0.7

    def test_iter_and_len(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            buffer = HistoryBuffer("test_campaign", knowledge_lake_path=tmpdir)

            assert len(buffer) == 0

            buffer.add({"x": 0.5}, 1.0)
            buffer.add({"x": 0.6}, 1.5)

            assert len(buffer) == 2
            steps = list(buffer)
            assert len(steps) == 2

    def test_getitem(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            buffer = HistoryBuffer("test_campaign", knowledge_lake_path=tmpdir)

            buffer.add({"x": 0.5}, 1.0)
            buffer.add({"x": 0.6}, 1.5)

            step = buffer[0]
            assert step.parameters["x"] == 0.5
            assert step.objective_value == 1.0

    def test_load_history_function(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            buffer = HistoryBuffer("test_campaign", knowledge_lake_path=tmpdir)
            buffer.add({"x": 0.5}, 1.0)
            buffer.add({"x": 0.6}, 1.5)
            buffer.persist()

            loaded = load_history("test_campaign", knowledge_lake_path=tmpdir)
            assert len(loaded) == 2
            best_value, _ = loaded.get_best()
            assert best_value == 1.5


class TestHistoryWithExploration:
    """Tests for create_history_from_exploration."""

    def test_create_history_from_exploration(self):
        from quantlab.exploration.models import ExplorationDecision, BrokerCostSnapshot

        decision = ExplorationDecision(
            capital_usd=10000,
            market="EURUSD",
            timeframe="H1",
            leverage=30.0,
            capital_limits={"risk_per_trade_usd": 100, "max_drawdown_pct": 15.0, "max_concurrent_positions": 3},
            operational_restrictions={"trading_hours_start": 8, "trading_hours_end": 20},
            risk_management={"stop_loss_pips": 50, "take_profit_pips": 100, "trailing_stop_pips": 0},
            money_management={"position_sizing_method": "fixed_fractional", "fixed_fractional_pct": 1.0},
            statistical_edge={"expected_sharpe": 1.5},
            hypothesis="Test hypothesis for exploration",
            broker_info=BrokerCostSnapshot(),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            from quantlab.optimization.history import create_history_from_exploration
            buffer = create_history_from_exploration("test_campaign", decision, tmpdir)

            # Should have seeded with defaults
            assert len(buffer) >= 1
            best_value, best_params = buffer.get_best()
            assert best_value == 0.0  # Seeded with neutral value